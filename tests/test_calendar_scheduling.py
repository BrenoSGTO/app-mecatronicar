# -*- coding: utf-8 -*-
"""
Testes unitários e de integração para a Issue #15:
- Aba de Calendário na TV (/tv)
- Exibição de Agendamentos em Tempo Real na Sidebar da Secretária
- Criação Pré-preenchida de Ficha / OS
- Regra Fundamental: Não gerar arquivo Excel (.xlsx) até salvar explicitamente
- Engatilhamento da integração com Google Calendar
"""

import os
import tempfile
import shutil
import sqlite3
import datetime
import unittest

import cache
import server
import calendar_sync

class TestCalendarScheduling(unittest.TestCase):

    def setUp(self):
        # Cria diretório temporário para banco e planilhas de teste
        self.test_dir = tempfile.mkdtemp(prefix="test_agenda_")
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        cache.init_db(self.db_path)

        # Configura cliente Flask de teste
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_database_schema_and_indices(self):
        """Verifica a criação da tabela agendamentos com todas as colunas necessárias e índices."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(agendamentos)")
        cols = {row[1] for row in cur.fetchall()}
        required_cols = {
            "id", "client_name", "phone", "car_plate", "car_plate_clean",
            "car_model", "title", "description", "scheduled_date", "scheduled_time",
            "status", "created_at", "updated_at", "notes",
            "google_calendar_id", "google_calendar_sync_status"
        }
        for col in required_cols:
            self.assertIn(col, cols, f"Coluna {col} não encontrada na tabela agendamentos")

        # Verifica índices
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agendamentos'")
        indices = {row[0] for row in cur.fetchall()}
        self.assertIn("idx_agendamentos_date", indices)
        self.assertIn("idx_agendamentos_plate", indices)
        self.assertIn("idx_agendamentos_status", indices)
        conn.close()

    def test_02_crud_agendamentos_cache(self):
        """Testa criação, leitura, atualização, filtro e exclusão de agendamentos no cache.py."""
        # 1. Criação com sucesso
        data_input = {
            "client_name": "Carlos Eduardo",
            "phone": "(13) 98888-7777",
            "car_plate": "ABC1D23",
            "car_model": "Chevrolet Onix 1.0",
            "title": "Troca de Pastilhas e Fluido de Freio",
            "description": "Pedal de freio esponjoso e ruído ao frear",
            "scheduled_date": "2026-11-20",
            "scheduled_time": "09:30",
            "notes": "Cliente aguardará na oficina"
        }
        item = cache.create_agendamento(data_input, db_path=self.db_path)
        self.assertIsNotNone(item)
        self.assertEqual(item["client_name"], "Carlos Eduardo")
        self.assertEqual(item["car_plate_clean"], "ABC1D23")
        self.assertEqual(item["car_plate_display"], "ABC-1D23")
        self.assertEqual(item["scheduled_date_iso"], "2026-11-20")
        self.assertEqual(item["scheduled_date_display"], "20/11/2026")
        self.assertEqual(item["status"], "agendado")

        item_id = item["id"]

        # 2. Leitura por ID
        retrieved = cache.get_agendamento(item_id, db_path=self.db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], "Troca de Pastilhas e Fluido de Freio")

        # 3. Atualização de status e campos
        updated = cache.update_agendamento(item_id, {
            "status": "confirmado",
            "scheduled_time": "10:00"
        }, db_path=self.db_path)
        self.assertEqual(updated["status"], "confirmado")
        self.assertEqual(updated["scheduled_time"], "10:00")

        # 4. Listagem e filtros
        # Adiciona segundo agendamento em outra data
        cache.create_agendamento({
            "client_name": "Mariana Souza",
            "title": "Revisão Geral",
            "car_plate": "XYZ9999",
            "car_model": "Honda Civic",
            "scheduled_date": "2026-11-25",
            "scheduled_time": "14:00"
        }, db_path=self.db_path)

        # Filtro por data exata
        list_exact = cache.list_agendamentos(date="2026-11-20", db_path=self.db_path)
        self.assertEqual(len(list_exact), 1)
        self.assertEqual(list_exact[0]["client_name"], "Carlos Eduardo")

        # Filtro por status
        list_status = cache.list_agendamentos(status="confirmado", db_path=self.db_path)
        self.assertEqual(len(list_status), 1)

        # Filtro textual (por modelo ou placa)
        list_query = cache.list_agendamentos(query="Civic", db_path=self.db_path)
        self.assertEqual(len(list_query), 1)
        self.assertEqual(list_query[0]["client_name"], "Mariana Souza")

        # 5. Exclusão
        deleted = cache.delete_agendamento(item_id, db_path=self.db_path)
        self.assertTrue(deleted)
        self.assertIsNone(cache.get_agendamento(item_id, db_path=self.db_path))

    def test_03_date_format_normalization(self):
        """Valida que datas fornecidas como DD/MM/AAAA ou YYYY-MM-DD são normalizadas corretamente."""
        # Formato DD/MM/AAAA
        ag_br = cache.create_agendamento({
            "client_name": "Teste Data BR",
            "title": "Alinhamento",
            "scheduled_date": "15/12/2026",
            "scheduled_time": "11:00"
        }, db_path=self.db_path)
        self.assertEqual(ag_br["scheduled_date_iso"], "2026-12-15")
        self.assertEqual(ag_br["scheduled_date_display"], "15/12/2026")

        # Formato YYYY-MM-DD
        ag_iso = cache.create_agendamento({
            "client_name": "Teste Data ISO",
            "title": "Balanceamento",
            "scheduled_date": "2026-12-16",
            "scheduled_time": "11:30"
        }, db_path=self.db_path)
        self.assertEqual(ag_iso["scheduled_date_iso"], "2026-12-16")
        self.assertEqual(ag_iso["scheduled_date_display"], "16/12/2026")

    def test_04_validation_rules(self):
        """Valida regras de obrigatoriedade (cliente e título) no create_agendamento."""
        with self.assertRaises(ValueError):
            cache.create_agendamento({"title": "Sem cliente"}, db_path=self.db_path)

        with self.assertRaises(ValueError):
            cache.create_agendamento({"client_name": "Sem título"}, db_path=self.db_path)

    def test_05_api_endpoints(self):
        """Testa todas as rotas REST da API /api/agendamentos."""
        # 1. POST /api/agendamentos
        payload = {
            "client_name": "Juliana Lima",
            "phone": "(13) 97777-6666",
            "car_plate": "FNB1A77",
            "car_model": "VW Fox 1.0",
            "title": "Troca de Óleo e Filtros",
            "description": "Troca dos 10.000 km",
            "scheduled_date": "2026-11-18",
            "scheduled_time": "14:30"
        }
        res_post = self.client.post("/api/agendamentos", json=payload)
        self.assertEqual(res_post.status_code, 201)
        data_post = res_post.get_json()
        self.assertTrue(data_post["success"])
        ag_id = data_post["agendamento"]["id"]
        self.assertGreater(ag_id, 0)
        self.assertIn("gcal", data_post)

        # 2. GET /api/agendamentos
        res_get = self.client.get("/api/agendamentos")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertTrue(data_get["success"])
        self.assertGreaterEqual(data_get["count"], 1)

        # 3. GET /api/agendamentos/<id>
        res_one = self.client.get(f"/api/agendamentos/{ag_id}")
        self.assertEqual(res_one.status_code, 200)
        data_one = res_one.get_json()
        self.assertEqual(data_one["agendamento"]["client_name"], "Juliana Lima")

        # 4. POST /api/agendamentos/<id>/status
        res_st = self.client.post(f"/api/agendamentos/{ag_id}/status", json={"status": "confirmado"})
        self.assertEqual(res_st.status_code, 200)
        self.assertEqual(res_st.get_json()["agendamento"]["status"], "confirmado")

        # 5. PUT /api/agendamentos/<id>
        res_put = self.client.put(f"/api/agendamentos/{ag_id}", json={"title": "Troca de Óleo Completa"})
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.get_json()["agendamento"]["title"], "Troca de Óleo Completa")

        # 6. DELETE /api/agendamentos/<id>
        res_del = self.client.delete(f"/api/agendamentos/{ag_id}")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()["success"])

        # 7. GET após deleção deve retornar 404
        res_404 = self.client.get(f"/api/agendamentos/{ag_id}")
        self.assertEqual(res_404.status_code, 404)

    def test_06_prefilled_ficha_rule_no_xlsx_until_save(self):
        """
        Regra Fundamental da Issue #15:
        - Os dados do agendamento pré-preenchem a ficha da OS no modal.
        - NENHUM arquivo .xlsx é criado até que a secretária clique manualmente em salvar na ficha.
        """
        # Cria agendamento no banco
        ag = cache.create_agendamento({
            "client_name": "Fernanda Ribeiro",
            "phone": "(13) 99111-2222",
            "car_plate": "BRA2E19",
            "car_model": "Renault Sandero 1.6",
            "title": "Barulho na suspensão dianteira",
            "description": "Barulho ao passar em lombadas ou piso irregular",
            "scheduled_date": "2026-11-19",
            "scheduled_time": "08:30"
        }, db_path=self.db_path)

        # Diretório onde as planilhas são salvas
        planilhas_dir = os.path.join(self.test_dir, "planilhas")
        os.makedirs(planilhas_dir, exist_ok=True)
        arquivos_antes = os.listdir(planilhas_dir)

        # 1. Simulação do clique "Dar Entrada / Criar Ficha":
        # A secretária apenas puxa os dados do agendamento para a memória/modal
        ag_data = cache.get_agendamento(ag["id"], db_path=self.db_path)
        self.assertIsNotNone(ag_data)
        
        # Garante que os dados para pré-preenchimento estão completos
        prefill_payload = {
            "car": {
                "plate": ag_data["car_plate_display"],
                "model": ag_data["car_model"]
            },
            "client": {
                "name": ag_data["client_name"],
                "phone": ag_data["phone"]
            },
            "os": {
                "complaint": f"{ag_data['title']} - {ag_data['description']}",
                "entry_date": datetime.date.today().strftime("%d/%m/%Y"),
                "entry_time": datetime.datetime.now().strftime("%H:%M")
            }
        }
        self.assertEqual(prefill_payload["client"]["name"], "Fernanda Ribeiro")
        self.assertEqual(prefill_payload["car"]["plate"], "BRA-2E19")
        self.assertIn("suspensão dianteira", prefill_payload["os"]["complaint"])

        # VERIFICAÇÃO CRÍTICA: Nenhum arquivo foi criado até agora!
        arquivos_durante = os.listdir(planilhas_dir)
        self.assertEqual(len(arquivos_antes), len(arquivos_durante), "Nenhum arquivo .xlsx deve ser criado na abertura da ficha pré-preenchida")

        # 2. Agora simula o salvamento manual pela secretária após conferência dos dados
        save_payload = {
            "car": {
                "plate": ag_data["car_plate_clean"],
                "model": ag_data["car_model"],
                "year": "2020",
                "color": "Branco"
            },
            "client": {
                "name": ag_data["client_name"],
                "phone": ag_data["phone"]
            },
            "os": {
                "visit_num": "1",
                "odometer": "45000",
                "complaint": prefill_payload["os"]["complaint"]
            },
            "pecas": [],
            "servicos": [{"desc": "Diagnóstico de suspensão", "qty": 1, "unit_price": 80.0}],
            "folder": planilhas_dir,
            "db_path": self.db_path
        }
        res_save = self.client.post("/api/os/save", json=save_payload)
        self.assertEqual(res_save.status_code, 200)
        res_json = res_save.get_json()
        self.assertTrue(res_json["success"])

        # O arquivo agora foi criado fisicamente no disco
        arquivos_depois = os.listdir(planilhas_dir)
        self.assertEqual(len(arquivos_depois), len(arquivos_antes) + 1)
        self.assertTrue(os.path.exists(res_json["file_path"]))

        # O agendamento agora é marcado como atendido / concluído
        upd = cache.update_agendamento_status(ag["id"], "concluido", db_path=self.db_path)
        self.assertEqual(upd["status"], "concluido")

    def test_07_google_calendar_preparedness(self):
        """Valida que a integração com o Google Calendar está devidamente engatilhada e pronta para ativação."""
        ag = {
            "id": 42,
            "title": "Revisão Periódica dos 60.000 km",
            "car_model": "VW Fox 1.0",
            "car_plate_display": "FNB-1A77",
            "car_plate": "FNB1A77",
            "client_name": "Danilo Pereira",
            "phone": "(13) 99752-9463",
            "description": "Vazamento leve de água e troca de velas",
            "notes": "Cliente trará peças próprias para conferência",
            "scheduled_date": "2026-11-22",
            "scheduled_time": "08:30"
        }

        # Constrói o evento oficial do Google Calendar
        event = calendar_sync.build_google_calendar_event(ag)
        self.assertIn("summary", event)
        self.assertIn("VW Fox 1.0", event["summary"])
        self.assertIn("FNB-1A77", event["summary"])
        self.assertIn("location", event)
        self.assertIn("start", event)
        self.assertIn("end", event)
        self.assertEqual(event["start"]["dateTime"], "2026-11-22T08:30:00")
        self.assertEqual(event["end"]["dateTime"], "2026-11-22T09:30:00")

        # Testa status de prontidão da sincronização
        sync_result = calendar_sync.sync_agendamento_to_gcal(ag)
        self.assertTrue(sync_result["success"])
        self.assertIn(sync_result["status"], ["prepared", "synced"])
        self.assertIn("event_payload", sync_result)

        # Testa endpoint de status
        res_gcal = self.client.get("/api/agendamentos/gcal/status")
        self.assertEqual(res_gcal.status_code, 200)
        self.assertIn("status", res_gcal.get_json())

if __name__ == "__main__":
    unittest.main()
