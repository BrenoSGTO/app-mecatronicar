# -*- coding: utf-8 -*-
"""
Benchmark do backend do MecatroniCar (T4 da repaginação v3).

Gera (ou reaproveita) uma massa de ~2000 planilhas numa pasta temporária a partir
de `planilhas_exemplo/` (que por sua vez vem de `gerar_massa_dados.py`) e mede:

  * indexação a frio (até a UI ficar utilizável) e leitura completa do conteúdo
  * reindexação sem mudanças e incremental (arquivos alterados/novos/apagados)
  * /api/search, /api/car_history/<placa>, /api/patio (com e sem ETag), /api/analytics
  * tamanho das respostas (bruto x gzip)
  * vazão/latência por HTTP real com clientes concorrentes (TV + secretária)

Uso:
    python scripts/benchmark.py --label antes
    python scripts/benchmark.py --label depois
    python scripts/benchmark.py --compare scripts/benchmark_results/antes.json scripts/benchmark_results/depois.json
    python scripts/benchmark.py --profile          # grava cProfile em scripts/benchmark_results/

Nada aqui toca em `oficina_cache.db` nem na pasta configurada da oficina: tudo roda
numa pasta temporária, com `cache.get_db_path` redirecionado para um banco descartável.
"""
import argparse
import cProfile
import gzip
import http.client
import io
import json
import os
import pstats
import random
import re
import shutil
import socket
import statistics
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS_DIR = os.path.join(ROOT, "scripts", "benchmark_results")
PLATE_RE = re.compile(r"^([A-Z]{3}) ?-?(\d[A-Z0-9]\d{2})")


# ----------------------------------------------------------------------------
# Massa de dados
# ----------------------------------------------------------------------------

def _shift_letters(letters, k):
    return "".join(chr((ord(c) - 65 + k) % 26 + 65) for c in letters)


def _rewrite_xlsx(src, dst, old_plate, new_plate):
    """Copia um .xlsx trocando a placa dentro das planilhas XML (rápido, sem openpyxl)."""
    old_variants = [old_plate[:3] + " " + old_plate[3:], old_plate[:3] + "-" + old_plate[3:], old_plate]
    new_variants = [new_plate[:3] + " " + new_plate[3:], new_plate[:3] + "-" + new_plate[3:], new_plate]
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("xl/") and item.filename.endswith(".xml"):
                txt = data.decode("utf-8")
                for o, n in zip(old_variants, new_variants):
                    txt = txt.replace(o, n)
                data = txt.encode("utf-8")
            zout.writestr(item, data)


def build_dataset(total, fresh=False):
    """Replica planilhas_exemplo/ (gerada por gerar_massa_dados.py) até `total` arquivos."""
    base = os.path.join(tempfile.gettempdir(), "mecatronicar_bench", f"planilhas_{total}")
    if os.path.isdir(base) and not fresh and len(os.listdir(base)) >= total:
        return base
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)

    seed_dir = os.path.join(ROOT, "planilhas_exemplo")
    seeds = sorted(f for f in os.listdir(seed_dir) if f.lower().endswith((".xlsx", ".xls")))
    if len(seeds) < 20:
        import gerar_massa_dados
        seed_dir = os.path.join(base, "_seed")
        gerar_massa_dados.generate_mass_data(target_folder=seed_dir, db_file=os.path.join(base, "_seed.db"), target_total=200)
        seeds = sorted(f for f in os.listdir(seed_dir) if f.lower().endswith(".xlsx"))

    count = 0
    k = 0
    while count < total:
        for fname in seeds:
            if count >= total:
                break
            src = os.path.join(seed_dir, fname)
            m = PLATE_RE.match(fname)
            if k == 0 or not m:
                if k > 0:
                    continue
                shutil.copy2(src, os.path.join(base, fname))
            else:
                letters, rest = m.group(1), m.group(2)
                new_plate = _shift_letters(letters, k * 3) + rest
                new_name = f"{new_plate[:3]} {new_plate[3:]}" + fname[m.end():]
                dst = os.path.join(base, new_name)
                if fname.lower().endswith(".xlsx"):
                    _rewrite_xlsx(src, dst, letters + rest, new_plate)
                else:
                    shutil.copy2(src, dst)
            count += 1
        k += 1
    return base


# ----------------------------------------------------------------------------
# Utilidades de medição
# ----------------------------------------------------------------------------

def timed(fn, *a, **kw):
    t0 = time.perf_counter()
    res = fn(*a, **kw)
    return (time.perf_counter() - t0) * 1000.0, res


def bench_get(client, url, runs=15, headers=None):
    """Retorna dict com 1ª chamada, mediana das seguintes, status e tamanhos."""
    first_ms, resp = timed(client.get, url, headers=headers or {})
    times = []
    for _ in range(runs):
        ms, resp = timed(client.get, url, headers=headers or {})
        times.append(ms)
    raw = resp.get_data()
    enc = resp.headers.get("Content-Encoding", "")
    body = gzip.decompress(raw) if enc == "gzip" else raw
    # Mesmo pedido feito por um aparelho da rede (TV) aceitando gzip: bytes no fio.
    lan = client.get(url, headers={**(headers or {}), "Accept-Encoding": "gzip"},
                     environ_base={"REMOTE_ADDR": "192.168.0.50"})
    wire_lan = len(lan.get_data())
    lan.close()
    return {
        "wire_bytes_lan": wire_lan,
        "first_ms": round(first_ms, 2),
        "median_ms": round(statistics.median(times), 2),
        "p95_ms": round(sorted(times)[max(0, int(len(times) * 0.95) - 1)], 2),
        "status": resp.status_code,
        "bytes": len(body),
        "bytes_gzip": len(gzip.compress(body)) if enc != "gzip" else len(raw),
        "served_gzip": enc == "gzip",
        "etag": resp.headers.get("ETag"),
    }


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_http_server(server_mod, port):
    """Sobe o servidor real (waitress se existir no código novo, senão o dev server)."""
    if hasattr(server_mod, "create_http_server"):
        srv = server_mod.create_http_server(host="127.0.0.1", port=port)
        th = threading.Thread(target=srv.run, daemon=True)
        th.start()
        kind = type(srv).__module__.split(".")[0]
        return kind, srv.close
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", port, server_mod.app, threaded=True)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return "werkzeug", srv.shutdown


def http_load(port, paths, clients=6, per_client=40, gzip_ok=True):
    lat = []
    errors = [0]
    lock = threading.Lock()

    def worker(seed):
        rnd = random.Random(seed)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        etags = {}
        for _ in range(per_client):
            p = rnd.choice(paths)
            hdrs = {"Accept-Encoding": "gzip"} if gzip_ok else {}
            if p in etags:
                hdrs["If-None-Match"] = etags[p]
            t0 = time.perf_counter()
            try:
                conn.request("GET", p, headers=hdrs)
                r = conn.getresponse()
                r.read()
                if r.getheader("ETag"):
                    etags[p] = r.getheader("ETag")
                if r.status >= 400:
                    errors[0] += 1
                if (r.getheader("Connection") or "").lower() == "close":
                    conn.close()
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            except Exception:
                errors[0] += 1
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            with lock:
                lat.append((time.perf_counter() - t0) * 1000.0)
        conn.close()

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    lat.sort()
    return {
        "requests": len(lat),
        "errors": errors[0],
        "rps": round(len(lat) / wall, 1),
        "p50_ms": round(lat[len(lat) // 2], 2),
        "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 2),
    }


# ----------------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------------

def full_content_parse(cache_mod, db_path, folder):
    """Leva o índice ao estado 'conteúdo de todas as planilhas lido'."""
    if hasattr(cache_mod, "parse_pending_rows"):
        return cache_mod.parse_pending_rows(db_path)
    # Código antigo: o conteúdo só era lido sob demanda pelo histórico/busca.
    import sqlite3
    conn = sqlite3.connect(db_path)
    plates = [r[0] for r in conn.execute("SELECT DISTINCT plate_clean FROM files WHERE plate_clean != ''")]
    conn.close()
    for p in plates:
        cache_mod.get_car_history(p, db_path)
    return {"plates": len(plates)}


def pick_queries(folder):
    names = sorted(os.listdir(folder))
    plate_count = {}
    accented = None
    for n in names:
        m = PLATE_RE.match(n)
        if m:
            plate_count[m.group(1) + m.group(2)] = plate_count.get(m.group(1) + m.group(2), 0) + 1
        if accented is None:
            parts = [p.strip() for p in n.split(" - ")]
            if len(parts) >= 3 and re.search(r"[áéíóúãõçâêô]", parts[2], re.I):
                accented = parts[2]
    top_plate = max(plate_count, key=plate_count.get)
    import unicodedata
    if accented:
        word = next(w for w in accented.split() if re.search(r"[áéíóúãõçâêô]", w, re.I))
        noacc = "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c)).lower()
    else:
        noacc = "silva"
    return {
        "plate": top_plate,
        "plate_visits": plate_count[top_plate],
        "plate_partial": top_plate[:3] + " " + top_plate[3:5],
        "name_noaccent": noacc,
        "model": "civic",
    }


def run(args):
    import cache
    import server

    folder_src = build_dataset(args.total, fresh=args.fresh)
    work = tempfile.mkdtemp(prefix="mecatronicar_bench_run_")
    folder = os.path.join(work, "planilhas")
    shutil.copytree(folder_src, folder)
    # Pré-leitura: o antivírus do Windows escaneia cada arquivo novo no primeiro open
    # (dezenas de ms por planilha e muito variável). Lendo tudo antes, as medições
    # comparam o código, não o antivírus.
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), "rb") as fh:
            fh.read()
    db_path = os.path.join(work, "bench.db")
    cache.get_db_path = lambda base_dir=None: db_path  # isola do banco oficial
    if hasattr(cache, "enable_connection_pool"):
        cache.enable_connection_pool(db_path)  # como o servidor faz com o banco do app
    server.app.config["TESTING"] = False
    client = server.app.test_client()
    n_files = len(os.listdir(folder))
    q = pick_queries(folder)
    print(f"Massa: {n_files} planilhas em {folder}")
    print(f"Consultas: {q}")

    prof = cProfile.Profile() if args.profile else None
    if prof:
        prof.enable()

    out = {"label": args.label, "files": n_files, "queries": q, "python": sys.version.split()[0]}

    # 1) Indexação a frio
    ms, res = timed(cache.scan_and_index_folder, folder, db_path)
    out["index_cold_ms"] = round(ms, 1)
    out["index_cold_mode"] = "rápido (nome do arquivo)" if res.get("fast_mode") else "completo"
    # primeira busca logo após a indexação a frio (antes do conteúdo ser lido)
    out["search_first_after_cold"] = bench_get(client, f"/api/search?q={q['plate_partial']}", runs=1)
    out["history_first_after_cold"] = bench_get(client, f"/api/car_history/{q['plate']}", runs=1)
    ms, _ = timed(full_content_parse, cache, db_path, folder)
    out["full_content_parse_ms"] = round(ms, 1)

    # 2) Reindexação
    ms, _ = timed(cache.scan_and_index_folder, folder, db_path)
    out["reindex_noop_ms"] = round(ms, 1)
    files = sorted(os.listdir(folder))
    rnd = random.Random(7)
    touched = rnd.sample([f for f in files if f.endswith(".xlsx")], 20)
    for f in touched:
        p = os.path.join(folder, f)
        st = os.stat(p)
        os.utime(p, (st.st_atime, st.st_mtime + 120))
    removed = rnd.sample([f for f in files if f not in touched], 10)
    for f in removed:
        os.remove(os.path.join(folder, f))
    for i, f in enumerate(rnd.sample([f for f in files if f.endswith(".xlsx") and f not in removed], 10)):
        m = PLATE_RE.match(f)
        if not m:
            continue
        new_plate = "ZZ" + chr(65 + i) + m.group(2)
        _rewrite_xlsx(os.path.join(folder, f), os.path.join(folder, f"{new_plate[:3]} {new_plate[3:]}" + f[m.end():]),
                      m.group(1) + m.group(2), new_plate)
    ms, res = timed(cache.scan_and_index_folder, folder, db_path)
    out["reindex_incremental_ms"] = round(ms, 1)
    out["reindex_incremental_indexed"] = res.get("indexed")
    full_content_parse(cache, db_path, folder)

    # 3) Endpoints (com conteúdo já lido)
    ep = {}
    ep["search_plate"] = bench_get(client, f"/api/search?q={q['plate_partial']}")
    ep["search_name_sem_acento"] = bench_get(client, f"/api/search?q={q['name_noaccent']}")
    ep["search_model"] = bench_get(client, f"/api/search?q={q['model']}")
    ep["car_history"] = bench_get(client, f"/api/car_history/{q['plate']}")
    ep["patio"] = bench_get(client, "/api/patio")
    if ep["patio"]["etag"]:
        ep["patio_304"] = bench_get(client, "/api/patio", headers={"If-None-Match": ep["patio"]["etag"]})
    ep["analytics_all"] = bench_get(client, "/api/analytics?period=all")
    ep["analytics_30"] = bench_get(client, "/api/analytics?period=30")
    ep["nf_queue"] = bench_get(client, "/api/nf/queue?filter=pending", runs=5)
    ep["static_app_js"] = bench_get(client, "/app.js", runs=5)
    out["endpoints"] = ep

    if prof:
        prof.disable()
        os.makedirs(RESULTS_DIR, exist_ok=True)
        pfile = os.path.join(RESULTS_DIR, f"profile_{args.label}.txt")
        s = io.StringIO()
        st = pstats.Stats(prof, stream=s).strip_dirs().sort_stats("cumulative")
        st.print_stats(45)
        s.write("\n\n==== tottime ====\n")
        st.sort_stats("tottime").print_stats(30)
        with open(pfile, "w", encoding="utf-8") as f:
            f.write(s.getvalue())
        print(f"Perfil gravado em {pfile}")

    # 4) HTTP real com concorrência (TV polling + secretária buscando)
    port = free_port()
    kind, stop = start_http_server(server, port)
    time.sleep(0.3)
    paths = ["/api/patio", "/api/patio", "/api/patio",
             "/api/search?q=" + urllib.parse.quote(q["plate_partial"]), f"/api/car_history/{q['plate']}",
             "/api/analytics?period=30"]
    out["http_server"] = kind
    out["http_mixed"] = http_load(port, paths, clients=6, per_client=40)
    out["http_patio_only"] = http_load(port, ["/api/patio"], clients=8, per_client=50)
    stop()

    shutil.rmtree(work, ignore_errors=True)
    return out


ROWS = [
    ("Indexação a frio (até UI utilizável)", lambda r: r["index_cold_ms"], "ms"),
    ("Leitura completa do conteúdo (todas as planilhas)", lambda r: r["full_content_parse_ms"], "ms"),
    ("1ª busca logo após indexação a frio", lambda r: r["search_first_after_cold"]["first_ms"], "ms"),
    ("1º histórico logo após indexação a frio", lambda r: r["history_first_after_cold"]["first_ms"], "ms"),
    ("Reindexação sem mudanças", lambda r: r["reindex_noop_ms"], "ms"),
    ("Reindexação incremental (20 alt. + 10 novas + 10 apagadas)", lambda r: r["reindex_incremental_ms"], "ms"),
    ("/api/search placa parcial (mediana)", lambda r: r["endpoints"]["search_plate"]["median_ms"], "ms"),
    ("/api/search nome sem acento (mediana)", lambda r: r["endpoints"]["search_name_sem_acento"]["median_ms"], "ms"),
    ("/api/search modelo (mediana)", lambda r: r["endpoints"]["search_model"]["median_ms"], "ms"),
    ("/api/car_history/<placa> (mediana)", lambda r: r["endpoints"]["car_history"]["median_ms"], "ms"),
    ("/api/patio (mediana)", lambda r: r["endpoints"]["patio"]["median_ms"], "ms"),
    ("/api/patio com If-None-Match (304)", lambda r: r["endpoints"].get("patio_304", {}).get("median_ms"), "ms"),
    ("/api/analytics?period=all (mediana)", lambda r: r["endpoints"]["analytics_all"]["median_ms"], "ms"),
    ("/api/analytics?period=30 (mediana)", lambda r: r["endpoints"]["analytics_30"]["median_ms"], "ms"),
    ("/api/nf/queue (mediana)", lambda r: r["endpoints"]["nf_queue"]["median_ms"], "ms"),
    ("Bytes p/ cliente da rede: /api/search placa", lambda r: _wire(r["endpoints"]["search_plate"]), "B"),
    ("Bytes p/ cliente da rede: /api/car_history", lambda r: _wire(r["endpoints"]["car_history"]), "B"),
    ("Bytes p/ cliente da rede: /api/patio", lambda r: _wire(r["endpoints"]["patio"]), "B"),
    ("Bytes p/ cliente da rede: /app.js", lambda r: _wire(r["endpoints"]["static_app_js"]), "B"),
    ("HTTP misto 6 clientes: req/s", lambda r: r["http_mixed"]["rps"], "req/s"),
    ("HTTP misto 6 clientes: p95", lambda r: r["http_mixed"]["p95_ms"], "ms"),
    ("HTTP só /api/patio 8 clientes: req/s", lambda r: r["http_patio_only"]["rps"], "req/s"),
    ("HTTP só /api/patio 8 clientes: p95", lambda r: r["http_patio_only"]["p95_ms"], "ms"),
]


def _wire(e):
    if "wire_bytes_lan" in e:
        return e["wire_bytes_lan"]
    return e["bytes_gzip"] if e.get("served_gzip") else e["bytes"]


def _fmt(v, unit):
    if v is None:
        return "—"
    if unit == "B":
        return f"{v/1024:.1f} KB"
    if unit == "req/s":
        return f"{v:.0f}"
    return f"{v:,.1f} ms".replace(",", "X").replace(".", ",").replace("X", ".")


def _median_of(runs, getter):
    vals = []
    for r in runs:
        try:
            v = getter(r)
        except Exception:
            v = None
        if v is not None:
            vals.append(v)
    return statistics.median(vals) if vals else None


def _load_runs(pattern):
    import glob
    paths = sorted(glob.glob(pattern)) or [pattern]
    return [json.load(open(p, encoding="utf-8")) for p in paths]


def compare(a_path, b_path):
    """Compara execuções; aceita padrões (ex.: 'antes*.json') e usa a mediana de cada medida."""
    a_runs, b_runs = _load_runs(a_path), _load_runs(b_path)
    a, b = a_runs[0], b_runs[0]
    print(f"Massa: {a['files']} planilhas. Execuções: {len(a_runs)} (antes) / {len(b_runs)} (depois), "
          f"mediana de cada medida. Servidor HTTP: {a.get('http_server')} → {b.get('http_server')}\n")
    print("| Medida | antes | depois | Ganho |")
    print("|---|---:|---:|---:|")
    for name, get, unit in ROWS:
        va = _median_of(a_runs, get)
        vb = _median_of(b_runs, get)
        gain = ""
        if va and vb:
            gain = f"{(vb / va):.1f}×" if unit == "req/s" else f"{(va / vb):.1f}×"
        print(f"| {name} | {_fmt(va, unit)} | {_fmt(vb, unit)} | {gain} |")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # console do Windows em cp1252
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--total", type=int, default=2000)
    ap.add_argument("--label", default="atual")
    ap.add_argument("--fresh", action="store_true", help="regera a massa de planilhas")
    ap.add_argument("--profile", action="store_true", help="grava cProfile das fases de indexação e endpoints")
    ap.add_argument("--compare", nargs=2, metavar=("ANTES.json", "DEPOIS.json"))
    args = ap.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    out = run(args)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{args.label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nResultados gravados em {path}")


if __name__ == "__main__":
    main()
