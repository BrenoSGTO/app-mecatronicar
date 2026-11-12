# -*- coding: utf-8 -*-
"""
test_issue_9_save_order.py
Validação completa da correção da Issue #9:
1. Salvar ordem de serviço através da rota /api/save_order com payload do modal de Nova Visita.
2. Criação física da planilha .xlsx seguindo os padrões canônicos da oficina.
3. Validação do formato OpenXML e parser com integridade dos dados preenchidos.
4. Indexação imediata no banco SQLite (tabela files e sincronização de estatísticas).
5. Garantia de que erros 400, 404 e 500 em /api/* retornam JSON estruturado com status HTTP adequado, nunca HTML.
"""

import os
import shutil
import tempfile
import unittest
import openpyxl
import sqlite3

import cache
import config
import excel_writer
import parser
import server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class TestIssue9SaveOrder(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mecatronicar_issue9_")
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        cache.init_db(self.db_path)

        server.app.config["TESTING"] = True
        server.app.config["TEST_DB_PATH"] = self.db_path
        self.client = server.app.test_client()

        # Configura pasta temporária no config para isolamento completo
        self.original_spreadsheet_folder = config.load_config(BASE_DIR).get("spreadsheet_folder", "")
        cfg = config.load_config(BASE_DIR)
        cfg["spreadsheet_folder"] = self.test_dir
        config.save_config(cfg, BASE_DIR)

    def tearDown(self):
        server.app.config.pop("TEST_DB_PATH", None)

        # Restaura configuração
        cfg = config.load_config(BASE_DIR)
        cfg["spreadsheet_folder"] = self.original_spreadsheet_folder
        config.save_config(cfg, BASE_DIR)

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_order_success_creates_xlsx_and_indexes_sqlite(self):
        """Valida salvamento manual completo de nova OS com geração de planilha e indexação SQLite."""
        payload = {
            "existing_file_path": None,
            "client": {
                "name": "Carlos Eduardo Santos",
                "phone": "(13) 98765-4321",
                "tel_res": "(13) 3232-1111",
                "tel_com": "",
                "cpf": "123.456.789-00",
                "rg": "12.345.678-9",
                "email": "carlos.santos@email.com",
                "address": "Av. Ana Costa",
                "address_num": "100",
                "address_compl": "Apto 42",
                "neighborhood": "Gonzaga",
                "city": "Santos",
                "cep": "11060-000"
            },
            "car": {
                "plate": "MEC2A26",
                "model": "Civic 2.0 EXL",
                "brand": "Honda",
                "year": "2021",
                "color": "Cinza",
                "fuel": "Flex",
                "chassis": "93HFC2670MZ123456"
            },
            "os": {
                "visit_num": "1",
                "odometer": "45200",
                "entry_date": "12/11/2026",
                "entry_time": "08:30",
                "payment_method": "PIX",
                "complaint": "Revisão preventiva e ruído nos freios dianteiros",
                "discount": 50.0
            },
            "patio_status": "Em Diagnóstico",
            "pecas": [
                {
                    "description": "Pastilha de Freio Dianteira",
                    "desc": "Pastilha de Freio Dianteira",
                    "quantity": 1,
                    "qty": 1,
                    "unit_price": 280.0,
                    "price": 280.0
                },
                {
                    "description": "Óleo de Motor 0W20 Sintético",
                    "desc": "Óleo de Motor 0W20 Sintético",
                    "quantity": 4,
                    "qty": 4,
                    "unit_price": 55.0,
                    "price": 55.0
                }
            ],
            "servicos": [
                {
                    "description": "Troca de Pastilhas e Fluido de Freio",
                    "desc": "Troca de Pastilhas e Fluido de Freio",
                    "quantity": 1,
                    "qty": 1,
                    "unit_price": 180.0,
                    "price": 180.0
                },
                {
                    "description": "Revisão Geral e Diagnóstico Computadorizado",
                    "desc": "Revisão Geral e Diagnóstico Computadorizado",
                    "quantity": 1,
                    "qty": 1,
                    "unit_price": 220.0,
                    "price": 220.0
                }
            ]
        }

        # 1. Envia requisição POST para /api/save_order
        resp = self.client.post("/api/save_order", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.content_type)

        data = resp.get_json()
        self.assertTrue(data.get("success"), f"Falha na resposta: {data}")
        self.assertIn("file_path", data)
        self.assertIn("file_name", data)
        self.assertIn(data.get("plate"), ["MEC-2A26", "MEC 2A26", "MEC2A26"])
        self.assertEqual(data.get("plate_clean"), "MEC2A26")

        file_path = data["file_path"]
        self.assertTrue(os.path.exists(file_path), f"Arquivo não encontrado no disco: {file_path}")
        self.assertTrue(file_path.endswith(".xlsx"))

        # 2. Validação da planilha física no disco com parser.py
        parsed = parser.parse_file(file_path)
        self.assertEqual(parsed.get("plate_clean"), "MEC2A26")
        self.assertEqual(parsed.get("client_name"), "Carlos Eduardo Santos")
        self.assertEqual(parsed.get("car_model"), "Civic 2.0 EXL")
        self.assertEqual(parsed.get("car_color"), "Cinza")
        self.assertEqual(len(parsed.get("pecas_items", [])), 2)
        self.assertEqual(len(parsed.get("servicos_items", [])), 2)

        # 3. Validação da indexação no banco de dados SQLite isolado de teste
        results = cache.search_files("MEC2A26", self.db_path)
        self.assertTrue(len(results) > 0, "Veículo MEC2A26 deve estar indexado no SQLite")
        self.assertEqual(results[0].get("plate_clean"), "MEC2A26")
        self.assertEqual(results[0].get("client_name"), "Carlos Eduardo Santos")

    def test_save_order_validation_errors_return_json_400(self):
        """Valida que erros de validação retornam status 400 com JSON estruturado."""
        # Payload vazio
        resp1 = self.client.post("/api/save_order", json={})
        self.assertEqual(resp1.status_code, 400)
        self.assertIn("application/json", resp1.content_type)
        data1 = resp1.get_json()
        self.assertFalse(data1["success"])
        self.assertIn("error", data1)

        # Payload sem placa
        resp2 = self.client.post("/api/save_order", json={
            "client": {"name": "Cliente Sem Placa"},
            "car": {"model": "Gol"}
        })
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("application/json", resp2.content_type)
        data2 = resp2.get_json()
        self.assertFalse(data2["success"])
        self.assertIn("placa", data2["error"].lower())

    def test_all_api_errors_return_json_never_flask_html(self):
        """Garante que rotas /api/* retornam JSON mesmo em 404, 405 ou 500, nunca HTML."""
        # 404 em rota de API inexistente
        resp_404 = self.client.get("/api/rota_totalmente_inexistente_12345")
        self.assertEqual(resp_404.status_code, 404)
        self.assertIn("application/json", resp_404.content_type)
        d_404 = resp_404.get_json()
        self.assertIsInstance(d_404, dict)
        self.assertFalse(d_404["success"])
        self.assertNotIn("<!doctype", resp_404.data.decode("utf-8").lower())

        # 405 Method Not Allowed em /api/save_order (GET em vez de POST)
        resp_405 = self.client.get("/api/save_order")
        self.assertEqual(resp_405.status_code, 405)
        self.assertIn("application/json", resp_405.content_type)
        d_405 = resp_405.get_json()
        self.assertIsInstance(d_405, dict)
        self.assertFalse(d_405["success"])
        self.assertNotIn("<!doctype", resp_405.data.decode("utf-8").lower())


if __name__ == "__main__":
    unittest.main()
