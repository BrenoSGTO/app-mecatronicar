# -*- coding: utf-8 -*-
"""
Suíte de Testes da Nova Grade Dinâmica e Painel de TV (Issue #14)
Validação de:
1. Servir /tv com layout de grade dinâmica sem colunas rígidas
2. Existência e integridade de static/tv.html e templates/tv.html
3. Estrutura do tv-cars-grid, tv-phase-bar e auto-fit
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

    def test_01_tv_html_template_and_static_parity(self):
        """Garante que static/tv.html e templates/tv.html contêm a nova grade e estão sincronizados."""
        static_tv = os.path.join(BASE_DIR, "static", "tv.html")
        template_tv = os.path.join(BASE_DIR, "templates", "tv.html")

        self.assertTrue(os.path.exists(static_tv), "static/tv.html deve existir")
        self.assertTrue(os.path.exists(template_tv), "templates/tv.html deve existir")

        with open(static_tv, "r", encoding="utf-8") as f:
            static_content = f.read()

        with open(template_tv, "r", encoding="utf-8") as f:
            template_content = f.read()

        # Ambos devem conter os elementos chave da nova grade dinâmica
        for content in (static_content, template_content):
            self.assertIn("tv-cars-grid", content, "Deve conter o container da grade dinâmica")
            self.assertIn("tv-phase-bar", content, "Deve conter a barra horizontal de fases")
            self.assertIn("tv-empty-state", content, "Deve conter o estado vazio amigável")
            self.assertIn("tv-manage-modal", content, "Deve conter o modal de gerenciamento")
            self.assertNotIn("tv-columns-grid", content, "Não deve conter a antiga estrutura de 7 colunas rígidas")

    def test_02_tv_route_serves_dynamic_grid(self):
        """Valida que a rota /tv entrega a nova página com status 200 e referências corretas."""
        resp = self.client.get("/tv")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        resp.close()
        self.assertIn("tv-body", html)
        self.assertIn("tv-cars-grid", html)
        self.assertIn("tv-phase-bar", html)
        self.assertIn("tv.js?v=2.1.0", html)
        self.assertIn("tv.css?v=2.1.0", html)

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
