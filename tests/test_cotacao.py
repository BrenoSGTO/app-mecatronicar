# -*- coding: utf-8 -*-
"""
Cotação de peças (aba interna da OS) e catálogo de autopeças.

1. CRUD do catálogo de autopeças (nome, atendente, desconto fixo) com validação.
2. A cotação é gravada só no banco local: nunca entra na planilha da OS.
3. A cotação segue a planilha quando a OS é salva (nova ou editada) e pode ser salva sozinha.
4. Carro que entrou no pátio sem ficha: a OS criada depois fica ligada ao mesmo card.
"""

import os
import shutil
import tempfile
import unittest

import openpyxl

import cache
import config
import server

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _order(plate="COT1A23", visit="1", cotacao=None, existing=None):
    payload = {
        "existing_file_path": existing,
        "client": {"name": "Cliente Cotação", "phone": "(13) 99999-0000", "city": "Santos"},
        "car": {"plate": plate, "model": "Gol 1.6", "brand": "VW", "year": "2015", "color": "Prata"},
        "os": {"visit_num": visit, "odometer": "120000", "entry_date": "14/11/2026", "entry_time": "09:00",
               "payment_method": "Pix", "complaint": "Barulho na suspensão", "discount": 0},
        "pecas": [{"description": "Amortecedor dianteiro", "quantity": 2, "unit_price": 350.0}],
        "servicos": [{"description": "Troca de amortecedores", "quantity": 1, "unit_price": 300.0}],
    }
    if cotacao is not None:
        payload["cotacao"] = cotacao
    return payload


class TestCotacao(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mec_cotacao_")
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        cache.init_db(self.db_path)
        server.app.config["TESTING"] = True
        server.app.config["TEST_DB_PATH"] = self.db_path
        self.client = server.app.test_client()
        cfg = config.load_config(BASE_DIR)
        self.original_folder = cfg.get("spreadsheet_folder", "")
        cfg["spreadsheet_folder"] = self.test_dir
        config.save_config(cfg, BASE_DIR)

    def tearDown(self):
        server.app.config.pop("TEST_DB_PATH", None)
        cfg = config.load_config(BASE_DIR)
        cfg["spreadsheet_folder"] = self.original_folder
        config.save_config(cfg, BASE_DIR)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    def test_autopecas_crud_and_validation(self):
        r = self.client.post("/api/autopecas", json={"name": "Central", "attendant": "Marcos", "discount_pct": "12,5", "db_path": self.db_path})
        self.assertEqual(r.status_code, 200, r.get_json())
        a = r.get_json()["autopeca"]
        self.assertEqual(a["discount_pct"], 12.5)
        self.assertEqual(a["attendant"], "Marcos")

        # nome repetido (sem diferenciar maiúsculas) e desconto fora da faixa são recusados
        self.assertEqual(self.client.post("/api/autopecas", json={"name": "central", "db_path": self.db_path}).status_code, 400)
        self.assertEqual(self.client.post("/api/autopecas", json={"name": "Outra", "discount_pct": 150, "db_path": self.db_path}).status_code, 400)
        self.assertEqual(self.client.post("/api/autopecas", json={"name": "  ", "db_path": self.db_path}).status_code, 400)

        r = self.client.post("/api/autopecas", json={"id": a["id"], "name": "Central Peças", "attendant": "Ana", "discount_pct": 10, "db_path": self.db_path})
        self.assertEqual(r.get_json()["autopeca"]["name"], "Central Peças")

        lst = self.client.get(f"/api/autopecas?db_path={self.db_path}").get_json()["autopecas"]
        self.assertEqual([x["name"] for x in lst], ["Central Peças"])

        self.assertEqual(self.client.delete(f"/api/autopecas/{a['id']}?db_path={self.db_path}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/autopecas/{a['id']}?db_path={self.db_path}").status_code, 404)

    def test_cotacao_saved_with_os_but_never_written_to_spreadsheet(self):
        cot = {
            "suppliers": [{"id": "1", "name": "Central", "attendant": "Marcos", "discount_pct": 10},
                          {"id": "2", "name": "Rápida", "attendant": "", "discount_pct": 0}],
            "parts": [{"desc": "Amortecedor dianteiro", "qty": 2, "prices": {"1": 400, "2": "370,00", "99": 1}},
                      {"desc": "", "qty": 1, "prices": {}}],
        }
        r = self.client.post("/api/save_order", json=_order(cotacao=cot))
        self.assertEqual(r.status_code, 200, r.get_json())
        data = r.get_json()
        self.assertTrue(data["cotacao_saved"])
        fpath = data["file_path"]

        # Nada da cotação vai para a planilha da OS
        wb = openpyxl.load_workbook(fpath)
        texts = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None)
        wb.close()
        self.assertNotIn("Central", texts)
        self.assertNotIn("Rápida", texts)
        self.assertNotIn("370", texts)

        saved = self.client.get("/api/cotacao", query_string={"file_path": fpath}).get_json()["cotacao"]
        self.assertEqual([s["name"] for s in saved["suppliers"]], ["Central", "Rápida"])
        self.assertEqual(len(saved["parts"]), 1, "linha vazia é descartada")
        self.assertEqual(saved["parts"][0]["prices"], {"1": 400.0, "2": 370.0}, "preço de coluna inexistente é descartado")
        self.assertEqual(saved["parts"][0]["qty"], 2.0)

    def test_cotacao_autosave_and_follows_renamed_spreadsheet(self):
        r = self.client.post("/api/save_order", json=_order())
        fpath = r.get_json()["file_path"]
        self.assertEqual(self.client.get("/api/cotacao", query_string={"file_path": fpath}).get_json()["cotacao"]["parts"], [])

        cot = {"suppliers": [{"id": "5", "name": "Central", "discount_pct": 8}],
               "parts": [{"desc": "Pastilha", "qty": 1, "prices": {"5": 199.9}}]}
        r = self.client.put("/api/cotacao", json={"file_path": fpath, "cotacao": cot})
        self.assertEqual(r.status_code, 200, r.get_json())

        # Editar a OS sem renomear mantém a cotação
        r = self.client.post("/api/save_order", json=_order(existing=fpath))
        self.assertEqual(r.get_json()["file_path"], fpath)
        self.assertEqual(cache.get_cotacao(fpath, self.db_path)["parts"][0]["desc"], "Pastilha")

        # Planilha renomeada (reindexada com old_fpath): cotação e card do pátio vão junto
        cache.save_patio_car({"plate": "COT1A23", "status": "Em Execução", "file_path": fpath}, self.db_path)
        new_path = os.path.join(self.test_dir, "COT 1A23 - 1 - Outro Cliente - Gol 1.6 - Prata.xlsx")
        shutil.copy(fpath, new_path)
        os.remove(fpath)
        cache.index_single_file(new_path, self.db_path, old_fpath=fpath)
        moved = self.client.get("/api/cotacao", query_string={"file_path": new_path}).get_json()["cotacao"]
        self.assertEqual(moved["parts"][0]["desc"], "Pastilha")
        self.assertIsNone(cache.get_cotacao(fpath, self.db_path))
        self.assertEqual(cache.get_patio_status(plate="COT1A23", db_path=self.db_path)["file_path"], new_path)

        # Cotação esvaziada é apagada
        self.client.put("/api/cotacao", json={"file_path": new_path, "cotacao": {"suppliers": [], "parts": []}})
        self.assertIsNone(cache.get_cotacao(new_path, self.db_path))

    def test_cotacao_rejects_unknown_file_and_bad_values(self):
        outside = os.path.join(tempfile.gettempdir(), "nao_e_da_oficina.xlsx")
        self.assertEqual(self.client.get("/api/cotacao", query_string={"file_path": outside}).status_code, 400)
        self.assertEqual(self.client.put("/api/cotacao", json={"file_path": "", "cotacao": {}}).status_code, 400)
        fpath = self.client.post("/api/save_order", json=_order()).get_json()["file_path"]
        bad = {"suppliers": [{"id": "1", "name": "X", "discount_pct": -5}], "parts": []}
        self.assertEqual(self.client.put("/api/cotacao", json={"file_path": fpath, "cotacao": bad}).status_code, 400)
        neg = {"suppliers": [{"id": "1", "name": "X"}], "parts": [{"desc": "a", "prices": {"1": -3}}]}
        self.assertEqual(self.client.put("/api/cotacao", json={"file_path": fpath, "cotacao": neg}).status_code, 400)

    def test_os_for_car_already_in_patio_links_to_same_card(self):
        car = cache.save_patio_car({"plate": "PAT1O23", "status": "Em Diagnóstico", "notes": "entrou sem ficha"}, self.db_path)
        self.assertFalse(car.get("file_path"))
        payload = _order(plate="PAT1O23")
        payload["patio_status"] = "Em Execução"
        fpath = self.client.post("/api/save_order", json=payload).get_json()["file_path"]

        rows = [c for c in cache.list_patio_status(db_path=self.db_path) if c.get("plate_clean") == "PAT1O23"]
        self.assertEqual(len(rows), 1, "não pode criar um segundo card para o mesmo carro")
        self.assertEqual(rows[0]["id"], car["id"])
        self.assertEqual(rows[0]["file_path"], fpath)
        self.assertEqual(cache.normalize_patio_status(rows[0]["status"]), cache.normalize_patio_status("Em Execução"))

    def test_delivered_car_gets_new_card_on_new_visit(self):
        old = cache.save_patio_car({"plate": "ENT1R23", "status": "Entregue"}, self.db_path)
        payload = _order(plate="ENT1R23", visit="2")
        payload["patio_status"] = "Em Diagnóstico"
        self.client.post("/api/save_order", json=payload)
        rows = [c for c in cache.list_patio_status(db_path=self.db_path) if c.get("plate_clean") == "ENT1R23"]
        self.assertEqual(len(rows), 2)
        self.assertIn(old["id"], [r["id"] for r in rows])


if __name__ == "__main__":
    unittest.main()
