# -*- coding: utf-8 -*-
"""
Testes unitários e de integração para a Issue #13:
1. Customização Interativa do Checklist de Vidro:
   - Janela/Opção de configuração antes da impressão
   - Seleção de quais itens da visita vão aparecer e/ou itens manuais
   - Toggle de inclusão/exclusão de códigos de falha do scanner OBD2
   - Remoção de notas longas, assinatura do mecânico, conferência final e teste de rodagem
2. Seleção Prévia de Visitas para Impressão:
   - Janela prévia para selecionar quais visitas imprimir
   - Geração de impressão consolidando apenas as visitas selecionadas (com ou sem preços)
"""

import os
import json
import unittest
import pdf_generator
import server
import parser
import cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class TestIssue13ChecklistAndVisitsSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        server.app.config["TESTING"] = True
        cls.client = server.app.test_client()
        cls.sample_xlsx = os.path.join(BASE_DIR, "planilhas_exemplo", "FNB 1A77 -7 -  Danilo Pereira - VW Fox - Prata.xlsx")
        
        # Garante banco indexado para testes
        db_path = cache.get_db_path(BASE_DIR)
        cache.scan_and_index_folder(os.path.join(BASE_DIR, "planilhas_exemplo"), db_path)

    def test_checklist_has_mechanic_sections_and_no_prices(self):
        """T5: checklist traz anotações, teste de rodagem e responsável, e nenhum valor financeiro."""
        html = pdf_generator.generate_checklist_from_file(self.sample_xlsx)

        self.assertIn("CHECKLIST", html)
        self.assertIn("FOLHA DE CHÃO DE OFICINA", html)
        self.assertIn("plate-mercosul", html)

        self.assertIn("Anotações do mecânico", html)
        self.assertIn("Teste de rodagem", html)
        self.assertIn("Mecânico responsável", html)
        self.assertIn("check-box", html)
        self.assertNotIn("R$", html, "Checklist não pode conter valores monetários")

    def test_checklist_scanner_toggle(self):
        """Valida inclusão e exclusão do bloco de códigos de falha do scanner OBD2."""
        mock_data = {
            "plate": "TST1234",
            "car_model": "Gol",
            "complaint": "Luz da injeção acesa",
            "complaint_comment": "DTC P0300 - Falha de combustão múltipla\nDTC P0171 - Mistura pobre Banco 1",
            "pecas_items": [{"description": "Vela de ignição", "quantity": 4}],
            "servicos_items": [{"description": "Diagnóstico com Scanner", "quantity": 1}]
        }

        # Com scanner habilitado
        html_with_scanner = pdf_generator.render_checklist_html(mock_data, include_scanner=True)
        self.assertIn("CÓDIGOS DE FALHA (SCANNER)", html_with_scanner)
        self.assertIn("DTC P0300", html_with_scanner)
        self.assertIn("DTC P0171", html_with_scanner)

        # Com scanner desabilitado
        html_no_scanner = pdf_generator.render_checklist_html(mock_data, include_scanner=False)
        self.assertNotIn("CÓDIGOS DE FALHA (SCANNER)", html_no_scanner)
        self.assertNotIn("DTC P0300", html_no_scanner)

    def test_checklist_custom_and_manual_items(self):
        """Valida seleção personalizada de itens e inclusão de itens manuais."""
        mock_data = {
            "plate": "TST5678",
            "car_model": "Civic",
            "pecas_items": [
                {"description": "Amortecedor Dianteiro", "quantity": 2},
                {"description": "Pastilha de Freio", "quantity": 1}
            ],
            "servicos_items": [
                {"description": "Troca de Amortecedores", "quantity": 1},
                {"description": "Troca de Pastilhas", "quantity": 1}
            ]
        }

        # Filtrando apenas 1 peça e adicionando 1 serviço manual
        custom_items = [
            {"type": "peca", "description": "Pastilha de Freio", "quantity": 1},
            {"type": "servico", "description": "Sangria de Freio (Manual)", "quantity": 1}
        ]

        html = pdf_generator.render_checklist_html(mock_data, custom_items=custom_items)
        self.assertIn("Pastilha de Freio", html)
        self.assertIn("Sangria de Freio (Manual)", html)
        self.assertNotIn("Amortecedor Dianteiro", html, "Item desmarcado não deve aparecer")
        self.assertNotIn("Troca de Amortecedores", html, "Item desmarcado não deve aparecer")

    def test_checklist_api_post_endpoint(self):
        """Valida endpoint POST /api/checklist_pdf com payload customizado."""
        payload = {
            "file_path": self.sample_xlsx,
            "include_scanner": False,
            "auto_print": True,
            "items": [
                {"type": "peca", "description": "Filtro de Óleo Específico", "quantity": "1"},
                {"type": "servico", "description": "Mão de Obra Troca", "quantity": "1"}
            ]
        }
        resp = self.client.post("/api/checklist_pdf", json=payload)
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")
        self.assertIn("Filtro de Óleo Específico", content)
        self.assertIn("Mão de Obra Troca", content)
        self.assertIn("window.print()", content)
        self.assertNotIn("CÓDIGOS DE FALHA (SCANNER)", content)

    def test_history_pdf_selected_visits(self):
        """Valida endpoint /api/history_pdf com consolidação apenas das visitas selecionadas."""
        # Consulta com apenas a primeira visita selecionada
        resp = self.client.post("/api/history_pdf", json={
            "plate": "FNB1A77",
            "selected_indices": [0],
            "without_prices": False
        })
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")
        self.assertIn("MecatroniCar", content)
        self.assertIn("HISTÓRICO COMPLETO", content)
        self.assertIn("FNB1A77", content)
        self.assertIn("Visitas selecionadas: <strong>1</strong>", content)

    def test_history_pdf_without_prices(self):
        """Valida geração do relatório de histórico em modo sem preços."""
        resp = self.client.post("/api/history_pdf", json={
            "plate": "FNB1A77",
            "without_prices": True
        })
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")
        self.assertIn("SEM VALORES", content)
        self.assertNotIn("Total Visita:", content)


if __name__ == "__main__":
    unittest.main()
