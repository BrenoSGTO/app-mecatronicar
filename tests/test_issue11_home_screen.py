# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
import json
import cache
import server

class TestIssue11HomeScreen(unittest.TestCase):
    def setUp(self):
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        cache.init_db(self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_agenda_crud_and_status(self):
        """Testa criação, listagem, atualização de status e exclusão de agendamentos."""
        ev = cache.save_agenda_event({
            "title": "Troca de Óleo Fox",
            "client_name": "Danilo Pereira Silva",
            "plate": "FNB-1A77",
            "car_model": "VW Fox",
            "service_type": "Troca de Óleo",
            "event_date": "2026-11-15",
            "event_time": "14:00",
            "notes": "Cliente trará o filtro",
            "status": "Agendado"
        }, db_path=self.temp_db_path)

        self.assertIsNotNone(ev)
        self.assertEqual(ev["plate_clean"], "FNB1A77")
        self.assertEqual(ev["status"], "Agendado")

        events = cache.list_agenda_events(start_date="2026-11-15", db_path=self.temp_db_path)
        self.assertEqual(len(events), 1)

        # Atualiza status
        up = cache.update_agenda_event_status(ev["id"], "Confirmado", db_path=self.temp_db_path)
        self.assertEqual(up["status"], "Confirmado")

        # Exclui
        deleted = cache.delete_agenda_event(ev["id"], db_path=self.temp_db_path)
        self.assertTrue(deleted)
        self.assertEqual(len(cache.list_agenda_events(db_path=self.temp_db_path)), 0)

    def test_patio_entregue_status(self):
        """Testa marcação de veículo como Entregue no pátio."""
        car = cache.update_patio_status(
            plate="FQE-5724",
            client_name="Natanael Santos",
            car_model="Nissan Sentra",
            status="Em Diagnóstico",
            db_path=self.temp_db_path
        )
        self.assertEqual(car["status"], "Em Diagnostico")

        # Muda para Entregue
        updated = cache.update_patio_status(
            record_id=car["id"],
            status="Entregue",
            db_path=self.temp_db_path
        )
        self.assertEqual(updated["status"], "Entregue")
        self.assertEqual(updated["status_display"], "Entregue")

    def test_agenda_and_patio_api_endpoints(self):
        """Testa endpoints da API para pátio e agendamento."""
        # Consulta /api/agenda
        resp_ag = self.client.get("/api/agenda")
        self.assertEqual(resp_ag.status_code, 200)
        ag_data = resp_ag.get_json()
        self.assertTrue(ag_data["success"])
        self.assertIn("events", ag_data)
        self.assertGreater(len(ag_data["events"]), 0)

        # Cria agendamento via API
        resp_new = self.client.post("/api/agenda", json={
            "title": "Revisão Freio",
            "client_name": "Juliana Lima",
            "plate": "EVI-2484",
            "car_model": "Sentra",
            "service_type": "Freios",
            "event_date": "2026-11-20",
            "event_time": "10:00"
        })
        self.assertEqual(resp_new.status_code, 200)
        new_ev = resp_new.get_json()["event"]
        ev_id = new_ev["id"]

        # Envia agendamento para o pátio
        resp_to_patio = self.client.post(f"/api/agenda/{ev_id}/to_patio", json={
            "status": "Em Diagnóstico"
        })
        self.assertEqual(resp_to_patio.status_code, 200)
        to_p_data = resp_to_patio.get_json()
        self.assertTrue(to_p_data["success"])
        self.assertEqual(to_p_data["car"]["plate_clean"], "EVI2484")

        # Consulta /api/patio e valida separação de ativos e entregues
        resp_p = self.client.get("/api/patio")
        self.assertEqual(resp_p.status_code, 200)
        p_data = resp_p.get_json()
        self.assertTrue(p_data["success"])
        self.assertIn("active_cars", p_data)
        self.assertIn("delivered_cars", p_data)

if __name__ == "__main__":
    unittest.main()
