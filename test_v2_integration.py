# -*- coding: utf-8 -*-
"""
Suíte de Testes Integrados Ponta a Ponta - MecatroniCar v2.0 (CP-08)
Validação de:
1. Leitura e parser de planilhas reais legadas (.xlsx e .xls)
2. Escrita bidirecional no Excel (excel_writer.py) e conferência de integridade
3. Rotas de PDF de Orçamento e Checklist com identidade visual MecatroniCar
4. Rotas e motor do Painel de TV (/tv e /api/patio) com os 7 status
5. Rotas de Criação e Edição de OS (/api/os/save e autocomplete)
6. Copiloto Fiscal (NFS-e Santos Item 14.01 e NF-e 55 Autopeças)
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
import openpyxl

import parser
import cache
import config
import excel_writer
import pdf_generator
import server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestMecatroniCarV2Integration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Cria pasta temporária isolada para os testes
        cls.test_dir = tempfile.mkdtemp(prefix="mecatronicar_test_")
        cls.db_path = os.path.join(cls.test_dir, "test_cache.db")
        cache.init_db(cls.db_path)
        
        # Inicia cliente de teste Flask
        server.app.config["TESTING"] = True
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        # Limpa pasta temporária
        try:
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_read_real_spreadsheets_xlsx_and_xls(self):
        """Valida leitura e integridade de planilhas reais da oficina (.xlsx e .xls)."""
        samples_dir = os.path.join(BASE_DIR, "planilhas_exemplo")
        self.assertTrue(os.path.isdir(samples_dir), "Pasta planilhas_exemplo deve existir")

        files = os.listdir(samples_dir)
        xlsx_found = False
        xls_found = False

        for fname in files:
            fpath = os.path.join(samples_dir, fname)
            ext = os.path.splitext(fname)[1].lower()

            if ext == ".xlsx":
                parsed = parser.parse_file(fpath)
                self.assertIsNotNone(parsed)
                self.assertTrue(len(parsed.get("plate", "")) >= 7)
                self.assertTrue(len(parsed.get("client_name", "")) > 0)
                self.assertIn("pecas_items", parsed)
                self.assertIn("servicos_items", parsed)
                xlsx_found = True

            elif ext == ".xls":
                parsed = parser.parse_file(fpath)
                self.assertIsNotNone(parsed)
                self.assertTrue(len(parsed.get("plate", "")) >= 7)
                self.assertTrue(len(parsed.get("client_name", "")) > 0)
                xls_found = True

        self.assertTrue(xlsx_found, "Deve ter validado ao menos uma planilha real .xlsx")
        self.assertTrue(xls_found, "Deve ter validado ao menos uma planilha real .xls")

    def test_02_excel_writer_bidirectional_and_integrity(self):
        """Valida geração de planilha .xlsx fiel ao modelo oficial e releitura imediata."""
        test_payload = {
            "client": {
                "name": "Natanael Pereira da Silva",
                "phone": "(13) 98888-7777",
                "cpf": "123.456.789-00",
                "address": "Av. Ana Costa",
                "address_num": "150",
                "address_compl": "Conj 42",
                "neighborhood": "Gonzaga",
                "city": "Santos"
            },
            "car": {
                "plate": "BRA2E19",
                "model": "Sentra 2.0 16V",
                "year": "2018",
                "color": "Prata",
                "brand": "Nissan"
            },
            "os": {
                "visit_num": "5",
                "odometer": "85400",
                "complaint": "Revisão periódica de freios e troca de fluidos",
                "payment_method": "Cartão de Crédito 3x",
                "discount": 50.0
            },
            "pecas": [
                {"desc": "Pastilha de freio dianteira cerâmica", "qty": 1, "unit_price": 280.0},
                {"desc": "Disco de freio ventilado dianteiro (par)", "qty": 1, "unit_price": 420.0},
                {"desc": "Fluido de freio DOT 4 500ml", "qty": 2, "unit_price": 45.0}
            ],
            "servicos": [
                {"desc": "Substituição de pastilhas e discos dianteiros", "qty": 1, "unit_price": 220.0},
                {"desc": "Sangria completa e substituição de fluido de freio", "qty": 1, "unit_price": 150.0}
            ],
            "patio_status": "Em Execução"
        }

        res = excel_writer.save_new_or_updated_os(test_payload, target_folder=self.test_dir, db_path=self.db_path)
        self.assertTrue(res.get("success"))
        file_path = res.get("file_path")
        self.assertTrue(os.path.exists(file_path), f"Arquivo gerado deve existir em disco: {file_path}")

        # Valida abertura pelo openpyxl e fórmulas
        wb = openpyxl.load_workbook(file_path, data_only=False)
        ws = wb.active
        self.assertIn("BRA2E19", str(ws["B18"].value))
        self.assertEqual(ws["I44"].value, "=SUM(I30:I43)")
        self.assertEqual(ws["G51"].value, "=I44+I51")
        self.assertEqual(ws["G53"].value, "=I44+I51-G52")
        wb.close()

        # Valida releitura pelo parser.py
        parsed = parser.parse_file(file_path)
        self.assertEqual(parsed.get("plate_clean"), "BRA2E19")
        self.assertIn("Natanael", parsed.get("client_name"))
        self.assertEqual(len(parsed.get("pecas_items")), 3)
        self.assertEqual(len(parsed.get("servicos_items")), 2)

    def test_03_pdf_routes_orcamento_and_checklist(self):
        """Valida geração de PDF/HTML de Orçamento Profissional e Checklist de Para-brisa."""
        sample_xlsx = os.path.join(BASE_DIR, "planilhas_exemplo", "FNB 1A77 -7 -  Danilo Pereira - VW Fox - Prata.xlsx")
        self.assertTrue(os.path.exists(sample_xlsx))

        # Orçamento PDF
        resp_orc = self.client.get(f"/api/orcamento_pdf?file_path={sample_xlsx}")
        self.assertEqual(resp_orc.status_code, 200)
        content_orc = resp_orc.data.decode("utf-8")
        self.assertIn("MecatroniCar", content_orc)
        self.assertIn("05.961.672/0001-87", content_orc)
        self.assertIn("FNB 1A77", content_orc)

        # Checklist de Para-brisa (Sem Valores)
        resp_chk = self.client.get(f"/api/checklist_pdf?file_path={sample_xlsx}")
        self.assertEqual(resp_chk.status_code, 200)
        content_chk = resp_chk.data.decode("utf-8")
        self.assertIn("CHECKLIST DE PARA-BRISA", content_chk)
        self.assertIn("FOLHA DE CHÃO DE OFICINA", content_chk)
        self.assertNotIn("R$ 724,00", content_chk, "Não deve conter valores monetários individuais")

    def test_04_tv_panel_routes_and_patio_flow(self):
        """Valida rota /tv, consulta /api/patio e fluxo de movimentação dos 7 status."""
        # Acesso à página da TV
        resp_tv = self.client.get("/tv")
        self.assertEqual(resp_tv.status_code, 200)
        self.assertIn("tv-body", resp_tv.data.decode("utf-8"))

        # Cadastro de veículo no pátio
        car_data = {
            "plate": "ABC1D23",
            "client_name": "Marcos Teste",
            "car_model": "Honda Civic",
            "car_color": "Preto",
            "status": "Em Diagnóstico",
            "box_mecanico": "Elevador 2",
            "notes": "Testando barulho na suspensão"
        }
        resp_save = self.client.post("/api/patio", json=car_data)
        self.assertEqual(resp_save.status_code, 200)
        saved_car = resp_save.get_json().get("car")
        car_id = saved_car["id"]

        # Atualização para status de Retirada por Terceiro com documento
        resp_status = self.client.post("/api/patio/status", json={
            "id": car_id,
            "status": "Liberado p/ Retirada por Terceiro",
            "authorized_name": "Carlos Irmão do Marcos",
            "authorized_doc": "44.555.666-7",
            "authorized_phone": "(13) 97777-6666"
        })
        self.assertEqual(resp_status.status_code, 200)
        updated_car = resp_status.get_json().get("car")
        self.assertEqual(updated_car["status"], "Liberado p/ Retirada por Terceiro")
        self.assertEqual(updated_car["authorized_name"], "Carlos Irmão do Marcos")

        # Consulta sumário
        resp_patio = self.client.get("/api/patio")
        self.assertEqual(resp_patio.status_code, 200)
        p_json = resp_patio.get_json()
        self.assertTrue(p_json["success"])
        self.assertIn("tv_url", p_json)

    def test_05_os_creation_and_autocomplete_api(self):
        """Valida rotas de autocompletar e salvamento de OS via API."""
        # Autocomplete
        resp_ac = self.client.get("/api/os/autocomplete?q=Danilo")
        self.assertEqual(resp_ac.status_code, 200)
        ac_data = resp_ac.get_json()
        self.assertTrue(ac_data["success"])

        # Próxima visita de placa existente
        resp_next = self.client.get("/api/os/next_visit/FNB1A77")
        self.assertEqual(resp_next.status_code, 200)
        next_data = resp_next.get_json()
        self.assertTrue(next_data["success"])
        self.assertTrue(int(next_data["next_visit_num"]) >= 1)

        # Salvamento de OS via API
        os_payload = {
            "client": {"name": "Cliente API Teste", "phone": "1399999999"},
            "car": {"plate": "TST9999", "model": "Gol G6", "year": "2016", "color": "Branco"},
            "os": {"visit_num": "1", "odometer": "50000", "complaint": "Troca de óleo de motor"},
            "pecas": [{"desc": "Óleo 5W40 Sintético 4L", "qty": 1, "unit_price": 180.0}],
            "servicos": [{"desc": "Mão de obra troca de óleo e filtro", "qty": 1, "unit_price": 60.0}]
        }
        resp_save = self.client.post("/api/os/save", json=os_payload)
        self.assertEqual(resp_save.status_code, 200)
        res_json = resp_save.get_json()
        self.assertTrue(res_json["success"])
        self.assertEqual(res_json["plate"], "TST9999")

    def test_06_copiloto_fiscal_nfs_and_nfe(self):
        """Valida separação de serviços (NFS-e Santos) vs peças (NF-e 55) e controle de pendências."""
        # Consulta dados fiscais da placa FNB 1A77
        resp_nf = self.client.get("/api/nf/data/FNB1A77")
        self.assertEqual(resp_nf.status_code, 200)
        nf_data = resp_nf.get_json()
        self.assertTrue(nf_data["success"])
        self.assertIn("14.01", nf_data["discriminacao_nfse"])
        self.assertIn("SANTOS/SP", nf_data["discriminacao_nfse"])
        self.assertTrue(len(nf_data["pecas_nfe"]) > 0)
        self.assertEqual(nf_data["pecas_nfe"][0]["cfop"], "5405")

        # Atualiza status fiscal
        resp_up = self.client.post("/api/nf/status", json={
            "plate": "FNB1A77",
            "status_servico": "emitida",
            "nf_servico_num": "000123",
            "status_pecas": "pendente"
        })
        self.assertEqual(resp_up.status_code, 200)
        up_data = resp_up.get_json()
        self.assertEqual(up_data["nf"]["status_servico"], "emitida")

        # Consulta fila de pendentes
        resp_pend = self.client.get("/api/nf/pending")
        self.assertEqual(resp_pend.status_code, 200)
        pend_json = resp_pend.get_json()
        self.assertTrue(pend_json["success"])

if __name__ == "__main__":
    unittest.main()
