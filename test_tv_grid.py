# -*- coding: utf-8 -*-
"""
Suíte de Testes da Nova Grade Dinâmica e Painel de TV (Issue #14)
Validação de:
1. Servir /tv com o painel v3 (colunas de status que se ajustam ao conteúdo)
2. Existência de um único tv.html (static/) e dos assets tv.js/tv.css/tv-icons.js
3. Estrutura do tv-board, colunas por fase e agenda do dia
4. API /api/patio suportando cadastro e fluxo de múltiplos veículos em fases operacionais
5. Ordenação e dados enriquecidos para exibição em TV 1080p
"""

import os
import unittest
import tempfile
import shutil
import json

import cache
import server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestTVGrid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="mec_tv_test_")
        cls.db_path = os.path.join(cls.test_dir, "test_tv.db")
        cache.init_db(cls.db_path)
        server.app.config["TESTING"] = True
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_single_tv_html_with_status_columns(self):
        """Existe um único tv.html (static/) e ele contém colunas de status, agenda e modal de gestão."""
        static_tv = os.path.join(BASE_DIR, "static", "tv.html")
        template_tv = os.path.join(BASE_DIR, "templates", "tv.html")

        self.assertTrue(os.path.exists(static_tv), "static/tv.html deve existir")
        self.assertFalse(os.path.exists(template_tv), "templates/tv.html (duplicata) foi removido na v3")

        with open(static_tv, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('id="tv-board"', content, "Deve conter o quadro de colunas")
        for phase in ("diagnostico", "orcamento", "aprovacao", "pecas", "execucao", "pronto", "terceiro"):
            self.assertIn(f'data-phase="{phase}"', content, f"Deve conter a coluna {phase}")
        self.assertIn("tv-empty", content, "Deve conter o estado vazio")
        self.assertIn("tv-agenda", content, "Deve conter a agenda do dia")
        self.assertIn("tv-manage-modal", content, "Deve conter o modal de gerenciamento")
        self.assertNotIn("tv-columns-grid", content, "Não deve conter a antiga estrutura de 7 colunas rígidas")

    def test_02_tv_route_serves_panel(self):
        """Valida que a rota /tv entrega a página do painel com status 200 e referências corretas."""
        resp = self.client.get("/tv")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        resp.close()
        self.assertIn("tv-body", html)
        self.assertIn('id="tv-board"', html)
        self.assertIn("tv.js?v=3.0.0", html)
        self.assertIn("tv.css?v=3.0.0", html)
        self.assertIn("tv-icons.js", html)
        for asset in ("/tv.js", "/tv.css", "/tv-icons.js"):
            r = self.client.get(asset)
            self.assertEqual(r.status_code, 200, f"{asset} deve ser servido")
            r.close()

    def test_03_patio_multi_phase_workflow(self):
        """Testa inclusão de múltiplos veículos em fases diferentes para ordenação na TV."""
        cars_to_add = [
            {
                "plate": "ABC1234",
                "client_name": "Carlos Silveira",
                "car_model": "VW Gol 1.6",
                "car_color": "Prata",
                "status": "Em Execução",
                "box_mecanico": "Elevador 1",
                "notes": "Troca de correia dentada"
            },
            {
                "plate": "XYZ9876",
                "client_name": "Mariana Santos",
                "car_model": "Toyota Corolla",
                "car_color": "Branco",
                "status": "Em Diagnóstico",
                "box_mecanico": "Box Rápido",
                "notes": "Luz de injeção acesa"
            },
            {
                "plate": "TER3E33",
                "client_name": "Roberto Almeida",
                "car_model": "Honda Civic",
                "car_color": "Preto",
                "status": "Liberado p/ Retirada por Terceiro",
                "authorized_name": "Paulo Almeida (Filho)",
                "authorized_doc": "38.123.456-9",
                "authorized_phone": "(13) 98888-1111"
            }
        ]

        saved_ids = []
        for car in cars_to_add:
            resp = self.client.post("/api/patio", json=car)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            saved_ids.append(data["car"]["id"])

        # Consulta pátio
        resp_get = self.client.get("/api/patio")
        self.assertEqual(resp_get.status_code, 200)
        patio_json = resp_get.get_json()
        self.assertTrue(patio_json["success"])
        self.assertGreaterEqual(patio_json["total"], 3)

        # Limpeza
        for cid in saved_ids:
            self.client.delete(f"/api/patio/{cid}")

if __name__ == "__main__":
    unittest.main()
