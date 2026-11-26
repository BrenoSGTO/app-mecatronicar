# -*- coding: utf-8 -*-
"""
Baixa da Tabela FIPE (veiculos.fipe.org.br) todas as marcas de carros vendidas no
Brasil e, para cada marca, os modelos (versões) existentes em cada ano/combustível.

Saída: JSON bruto  {"tabela": 339, "marcas": [{"codigo", "nome", "anos": {"2018-5": [labels...]}}]}
que o scripts/build_vehicle_catalog.py transforma no catálogo enxuto usado pela tela
(static/catalog/veiculos.json).

Uso (ferramenta de desenvolvimento, precisa de internet; leva alguns minutos):
    python scripts/fetch_fipe_catalog.py saida_fipe.json
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import os

BASE = "https://veiculos.fipe.org.br/api/veiculos/"
HEADERS = {
    "Referer": "https://veiculos.fipe.org.br/",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (catalogo-oficina)",
}
CARROS = 1
PACE = 1.2          # segundos entre requisições (a FIPE devolve 429 se apertar)
_last = [0.0]


def post(endpoint, data, tries=8):
    body = urllib.parse.urlencode(data).encode()
    delay = 8.0
    for attempt in range(tries):
        wait = PACE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(BASE + endpoint, data=body, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if isinstance(payload, dict) and payload.get("erro"):
                raise RuntimeError(payload.get("erro"))
            return payload
        except Exception as exc:  # throttling (429/5xx) ou rede: espera e tenta de novo
            if attempt == tries - 1:
                raise
            print(f"  retry {endpoint} {data.get('codigoMarca')} {data.get('ano', '')}: {exc}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main(out_path):
    tabela = post("ConsultarTabelaDeReferencia", {})[0]["Codigo"]
    marcas = post("ConsultarMarcas", {"codigoTabelaReferencia": tabela, "codigoTipoVeiculo": CARROS})
    print(f"Tabela {tabela}: {len(marcas)} marcas", flush=True)

    result = []
    if os.path.exists(out_path):  # retoma de onde parou
        with open(out_path, encoding="utf-8") as fh:
            result = json.load(fh).get("marcas", [])
    feitos = {m["codigo"] for m in result}
    for i, marca in enumerate(marcas, 1):
        codigo = marca["Value"]
        if codigo in feitos:
            continue
        info = post("ConsultarModelos", {
            "codigoTabelaReferencia": tabela, "codigoTipoVeiculo": CARROS, "codigoMarca": codigo,
        })
        anos = [a["Value"] for a in info.get("Anos", [])]

        def fetch(ano_value):
            ano, comb = ano_value.split("-")
            models = post("ConsultarModelosAtravesDoAno", {
                "codigoTabelaReferencia": tabela, "codigoTipoVeiculo": CARROS, "codigoMarca": codigo,
                "ano": ano_value, "codigoTipoCombustivel": comb, "anoModelo": ano,
            })
            return ano_value, [m["Label"] for m in models]

        por_ano = dict(fetch(a) for a in anos)
        result.append({
            "codigo": codigo,
            "nome": marca["Label"],
            "modelos": [m["Label"] for m in info.get("Modelos", [])],
            "anos": por_ano,
        })
        print(f"[{i}/{len(marcas)}] {marca['Label']}: {len(info.get('Modelos', []))} versões, {len(anos)} anos", flush=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"tabela": tabela, "marcas": result}, fh, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fipe_raw.json")
