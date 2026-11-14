# -*- coding: utf-8 -*-
"""
Testes da T4 (repaginação v3) — backend: desempenho e robustez.

- indexação incremental por mtime/tamanho, remoção de planilhas apagadas
- leitura do conteúdo em segundo plano com progresso consultável
- planilha bloqueada pelo Excel durante a indexação
- ETag/304 em /api/patio e /api/agendamentos
- /api/open_file só abre planilhas da pasta, só para a própria máquina
- gzip para clientes da rede, MIME correto de .js, erros JSON uniformes
"""
import gzip
import json
import mimetypes
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

import cache
import parser
import server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(BASE_DIR, "planilhas_exemplo")
LAN = {"REMOTE_ADDR": "192.168.0.77"}


def _sample_xlsx(n):
    names = sorted(f for f in os.listdir(SAMPLES) if f.endswith(".xlsx"))
    return [os.path.join(SAMPLES, f) for f in names[:n]]


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class _TempDbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mecatronicar_t4_")
        self.folder = os.path.join(self.tmp, "planilhas")
        os.makedirs(self.folder)
        self.db_path = os.path.join(self.tmp, "cache.db")

    def tearDown(self):
        cache.wait_for_background_index(timeout=30)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy_samples(self, n):
        out = []
        for src in _sample_xlsx(n):
            dst = os.path.join(self.folder, os.path.basename(src))
            shutil.copy2(src, dst)
            out.append(dst)
        return out


class TestIncrementalIndexing(_TempDbCase):

    def test_only_new_or_changed_files_are_reread(self):
        files = self.copy_samples(3)
        res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(res["indexed"], 3)
        self.assertFalse(res["fast_mode"])
        self.assertEqual(res["pending_parse"], 0)

        # Nada mudou: nada é relido.
        res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(res["indexed"], 0)

        # Só o mtime mudou (ex.: salvou sem alterar): relê só aquela.
        st = os.stat(files[0])
        os.utime(files[0], (st.st_atime, st.st_mtime + 60))
        with mock.patch.object(cache, "parse_file", wraps=cache.parse_file) as spy:
            res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(res["indexed"], 1)
        self.assertEqual(spy.call_count, 1)

        # Mesmo mtime mas tamanho diferente também conta como alterada.
        mtime = os.stat(files[1]).st_mtime
        with open(files[1], "ab") as f:
            f.write(b"\0")
        os.utime(files[1], (mtime, mtime))
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE files SET file_mtime = ? WHERE file_path = ?", (mtime, files[1]))
        conn.commit()
        conn.close()
        res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(res["indexed"], 1)

        # Apagada: sai do índice.
        os.remove(files[2])
        res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(res["removed"], 1)
        self.assertEqual(cache.get_stats(self.db_path)["total_files"], 2)

    def test_many_new_files_enter_by_name_then_content_is_parsed(self):
        self.copy_samples(cache.FAST_INDEX_THRESHOLD + 5)
        t0 = time.perf_counter()
        res = cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertTrue(res["fast_mode"])
        self.assertEqual(res["pending_parse"], cache.FAST_INDEX_THRESHOLD + 5)
        self.assertLess(time.perf_counter() - t0, 5.0)

        # A busca já funciona pelo nome do arquivo antes do conteúdo ser lido.
        plate = _rows(self.db_path, "SELECT plate_clean FROM files LIMIT 1")[0][0]
        self.assertTrue(cache.search_files(plate, self.db_path))

        out = cache.parse_pending_rows(self.db_path)
        self.assertEqual(out["errors"], [])
        pending = _rows(self.db_path, "SELECT COUNT(*) FROM files WHERE data_json IS NULL OR data_json = ''")[0][0]
        self.assertEqual(pending, 0)
        # Conteúdo lido de verdade (datas de entrada vêm de dentro da planilha).
        dated = _rows(self.db_path, "SELECT COUNT(*) FROM files WHERE entry_date_sort != '0000-00-00'")[0][0]
        self.assertGreater(dated, 0)

    def test_background_index_reports_progress_and_finishes(self):
        self.copy_samples(cache.FAST_INDEX_THRESHOLD + 3)
        status = cache.start_background_index(self.folder, self.db_path, scan=True)
        self.assertIn(status["phase"], ("scan", "parse", "done"))
        final = cache.wait_for_background_index(timeout=60)
        self.assertFalse(final["running"])
        self.assertEqual(final["phase"], "done")
        self.assertEqual(final["percent"], 100.0)
        self.assertEqual(final["parse_result"]["parsed"], cache.FAST_INDEX_THRESHOLD + 3)

    def test_search_ignores_accents_and_plate_format(self):
        files = self.copy_samples(1)
        cache.scan_and_index_folder(self.folder, self.db_path)
        row = _rows(self.db_path, "SELECT plate_clean, client_name FROM files")[0]
        plate, client = row
        self.assertEqual(len(cache.search_files(f"{plate[:3]}-{plate[3:]}", self.db_path)), 1)
        self.assertEqual(len(cache.search_files(plate.lower(), self.db_path)), 1)
        word = client.split()[0]
        self.assertEqual(len(cache.search_files(parser.remove_accents(word).upper(), self.db_path)), 1)

        # Campo alterado por código externo: o trigger invalida o search_text e a busca
        # cai no filtro antigo (campo a campo) até o backfill recalcular.
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE files SET complaint = 'Barulho no câmbio' WHERE file_path = ?", (files[0],))
        conn.commit()
        conn.close()
        self.assertIsNone(_rows(self.db_path, "SELECT search_text FROM files")[0][0])
        self.assertEqual(len(cache.search_files("barulho", self.db_path)), 1)
        cache.scan_and_index_folder(self.folder, self.db_path)  # backfill do search_text
        self.assertEqual(len(cache.search_files("cambio", self.db_path)), 1)
        self.assertEqual(len(cache.search_files("CÂMBIO", self.db_path)), 1)

    def test_like_wildcards_in_query_are_literal(self):
        self.copy_samples(2)
        cache.scan_and_index_folder(self.folder, self.db_path)
        self.assertEqual(cache.search_files("%", self.db_path), [])
        self.assertEqual(cache.search_files("_", self.db_path), [])


@unittest.skipUnless(sys.platform == "win32", "bloqueio exclusivo de arquivo só no Windows")
class TestLockedSpreadsheet(_TempDbCase):
    """Simula a planilha aberta/sendo salva pelo Excel (handle sem compartilhamento)."""

    def _lock(self, path):
        import ctypes
        from ctypes import wintypes
        CreateFileW = ctypes.windll.kernel32.CreateFileW
        CreateFileW.restype = wintypes.HANDLE
        GENERIC_READ = 0x80000000
        OPEN_EXISTING = 3
        h = CreateFileW(path, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        self.assertNotEqual(h, wintypes.HANDLE(-1).value)
        return h

    def _unlock(self, h):
        import ctypes
        ctypes.windll.kernel32.CloseHandle(h)

    def test_locked_file_is_indexed_by_name_and_parsed_later(self):
        files = self.copy_samples(2)
        h = self._lock(files[0])
        try:
            res = cache.scan_and_index_folder(self.folder, self.db_path)
            self.assertEqual(res["indexed"], 2)
            self.assertTrue(any("em uso" in e for e in res["errors"]))
            self.assertEqual(res["pending_parse"], 1)
            # A leitura em lote não trava nem perde a planilha.
            out = cache.parse_pending_rows(self.db_path, retries=0)
            self.assertEqual(out["busy"], 1)
            # Busca/histórico continuam respondendo enquanto ela está bloqueada.
            plate = _rows(self.db_path, "SELECT plate_clean FROM files WHERE file_path = ?", (files[0],))[0][0]
            hist = cache.get_car_history(plate, self.db_path)
            self.assertTrue(any(v["file_path"] == files[0] for v in hist))
        finally:
            self._unlock(h)
        out = cache.parse_pending_rows(self.db_path)
        self.assertEqual(out["parsed"], 1)
        self.assertEqual(cache.scan_and_index_folder(self.folder, self.db_path)["pending_parse"], 0)


class _ServerCase(_TempDbCase):
    def setUp(self):
        super().setUp()
        self._patch = mock.patch.object(cache, "get_db_path", lambda base_dir=None: self.db_path)
        self._patch.start()
        cache.init_db(self.db_path)
        self._testing = server.app.config.get("TESTING")
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()

    def tearDown(self):
        server.app.config["TESTING"] = self._testing
        self._patch.stop()
        super().tearDown()


class TestPatioEtag(_ServerCase):

    def test_patio_returns_304_until_something_changes(self):
        r1 = self.client.get("/api/patio")
        self.assertEqual(r1.status_code, 200)
        etag = r1.headers.get("ETag")
        self.assertTrue(etag)
        self.assertEqual(r1.headers.get("Cache-Control"), "no-cache")

        time.sleep(1.1)  # server_time muda, mas não entra no ETag
        r2 = self.client.get("/api/patio", headers={"If-None-Match": etag})
        self.assertEqual(r2.status_code, 304)
        self.assertEqual(r2.data, b"")

        car = r1.get_json()["cars"][0]
        new_status = "Em Execucao" if car["status"] != "Em Execucao" else "Esperando Pecas"
        up = self.client.post("/api/patio/status", json={"car_id": car["id"], "status": new_status})
        self.assertEqual(up.status_code, 200)
        r3 = self.client.get("/api/patio", headers={"If-None-Match": etag})
        self.assertEqual(r3.status_code, 200)
        self.assertNotEqual(r3.headers.get("ETag"), etag)

    def test_patio_etag_survives_gzip_for_lan_clients(self):
        hdrs = {"Accept-Encoding": "gzip"}
        r1 = self.client.get("/api/patio", headers=hdrs, environ_base=LAN)
        self.assertEqual(r1.headers.get("Content-Encoding"), "gzip")
        body = json.loads(gzip.decompress(r1.data))
        self.assertTrue(body["success"])
        r2 = self.client.get("/api/patio", headers={**hdrs, "If-None-Match": r1.headers["ETag"]}, environ_base=LAN)
        self.assertEqual(r2.status_code, 304)

    def test_agendamentos_supports_304(self):
        r1 = self.client.get("/api/agendamentos")
        etag = r1.headers.get("ETag")
        self.assertTrue(etag)
        r2 = self.client.get("/api/agendamentos", headers={"If-None-Match": etag})
        self.assertEqual(r2.status_code, 304)

    def test_patio_validation(self):
        r = self.client.post("/api/patio/status", json={"car_id": "abc", "status": "Em Execucao"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["success"])
        r = self.client.post("/api/patio", json={"plate": "ABC1D23", "status": "Voando"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/patio", json={})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/patio", data="{nao e json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())
        r = self.client.post("/api/patio", json=["lista"])
        self.assertEqual(r.status_code, 400)


class TestOpenFileSecurity(_ServerCase):

    def setUp(self):
        super().setUp()
        self.files = self.copy_samples(1)
        cfg_patch = mock.patch.object(server.config, "load_config",
                                      lambda base_dir=None: {"spreadsheet_folder": self.folder})
        cfg_patch.start()
        self.addCleanup(cfg_patch.stop)
        self.started = []
        sf = mock.patch.object(server.os, "startfile", lambda p: self.started.append(p), create=True)
        sf.start()
        self.addCleanup(sf.stop)

    def test_opens_spreadsheet_inside_folder(self):
        r = self.client.post("/api/open_file", json={"file_path": self.files[0]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.started, [self.files[0]])

    def test_refuses_files_outside_folder_or_not_spreadsheets(self):
        outside = os.path.join(self.tmp, "fora.xlsx")
        shutil.copy2(self.files[0], outside)
        exe = os.path.join(self.folder, "malicioso.bat")
        with open(exe, "w") as f:
            f.write("echo oi")
        traversal = os.path.join(self.folder, "..", "fora.xlsx")
        for p in (outside, exe, traversal, sys.executable):
            r = self.client.post("/api/open_file", json={"file_path": p})
            self.assertEqual(r.status_code, 403, p)
            self.assertFalse(r.get_json()["success"])
        self.assertEqual(self.started, [])

    def test_refuses_requests_from_the_lan(self):
        r = self.client.post("/api/open_file", json={"file_path": self.files[0]}, environ_base=LAN)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.started, [])

    def test_missing_file_is_404(self):
        r = self.client.post("/api/open_file", json={"file_path": os.path.join(self.folder, "nao_existe.xlsx")})
        self.assertEqual(r.status_code, 404)

    def test_apply_update_only_local_and_github(self):
        r = self.client.post("/api/apply_update", json={"download_url": "https://github.com/x/y.zip"}, environ_base=LAN)
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/apply_update", json={"download_url": "http://evil.example/upd.zip"})
        self.assertEqual(r.status_code, 400)


class TestHttpLayer(_ServerCase):

    def test_js_mime_type_is_text_javascript(self):
        self.assertEqual(mimetypes.guess_type("x.js")[0], "text/javascript")
        self.assertEqual(mimetypes.guess_type("x.mjs")[0], "text/javascript")
        for url in ("/js/main.js", "/static/js/main.js"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertEqual(r.mimetype, "text/javascript", url)
            self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
            r.close()

    def test_static_files_revalidate_with_304(self):
        r = self.client.get("/js/main.js")
        etag = r.headers["ETag"]
        r.close()
        self.assertIn("no-cache", r.headers.get("Cache-Control", ""))
        r2 = self.client.get("/js/main.js", headers={"If-None-Match": etag})
        self.assertEqual(r2.status_code, 304)

    def test_gzip_only_for_lan_clients(self):
        r = self.client.get("/js/main.js", headers={"Accept-Encoding": "gzip"}, environ_base=LAN)
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")
        self.assertIn("Accept-Encoding", r.headers.get("Vary", ""))
        raw = gzip.decompress(r.data)
        with open(os.path.join(BASE_DIR, "static", "js", "main.js"), "rb") as f:
            self.assertEqual(raw, f.read())
        # Revalidação com o ETag da versão comprimida.
        r2 = self.client.get("/js/main.js", headers={"Accept-Encoding": "gzip", "If-None-Match": r.headers["ETag"]},
                             environ_base=LAN)
        self.assertEqual(r2.status_code, 304)
        # Na própria máquina (Edge da secretária) não comprime: não há rede para economizar.
        r3 = self.client.get("/js/main.js", headers={"Accept-Encoding": "gzip"})
        self.assertIsNone(r3.headers.get("Content-Encoding"))
        r3.close()

    def test_api_errors_are_uniform_json_and_logged(self):
        r = self.client.get("/api/nao_existe")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["success"], False)
        r = self.client.delete("/api/config")
        self.assertEqual(r.status_code, 405)
        self.assertIn("error", r.get_json())
        with mock.patch.object(cache, "get_stats", side_effect=RuntimeError("falha simulada")), \
                self.assertLogs("mecatronicar.server", level="ERROR") as logs:
            r = self.client.get("/api/config")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json(), {"success": False, "error": "falha simulada"})
        self.assertTrue(any("Traceback" in line or "falha simulada" in line for line in logs.output))

    def test_db_path_from_client_only_in_tests(self):
        server.app.config["TESTING"] = False
        other = os.path.join(self.tmp, "outro.db")
        r = self.client.get(f"/api/analytics?period=all&db_path={other}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(os.path.exists(other))

    def test_index_status_endpoint(self):
        r = self.client.get("/api/index_status")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        for key in ("running", "phase", "total", "done", "percent"):
            self.assertIn(key, data)

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["success"])


class TestWaitressServer(unittest.TestCase):

    def test_serves_requests_over_http(self):
        import socket
        import threading
        import urllib.request
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        srv = server.create_http_server(host="127.0.0.1", port=port, threads=2)
        th = threading.Thread(target=srv.run, daemon=True)
        th.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(json.loads(resp.read())["success"], True)
                self.assertIn("MecatroniCar", resp.headers.get("Server", ""))
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main()
