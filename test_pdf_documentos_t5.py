# -*- coding: utf-8 -*-
"""T5 - PDFs profissionais: casos de borda dos três documentos (HTML de impressão)."""
import re
import unittest

import pdf_generator as G

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B06\u2705]")


def _itens(n, prefixo="Item"):
    return [
        {"description": f"{prefixo} {i} de teste", "quantity": "1",
         "unit_price": "R$ 10,00", "total_price": "R$ 10,00"}
        for i in range(1, n + 1)
    ]


BASE = {
    "plate": "ABC1D23", "plate_display": "ABC-1D23", "visit_num": "3",
    "client_name": "João da Conceição", "car_model": "Onix 1.0", "car_brand": "Chevrolet",
    "car_color": "Prata", "car_year": "2020", "odometer": "45000",
    "complaint": "Ruído na suspensão", "entry_date": "05/11/2026", "entry_time": "09:00",
}


class TestOrcamento(unittest.TestCase):
    def test_um_item_e_totais_calculados_quando_ausentes(self):
        d = dict(BASE, pecas_items=_itens(1), servicos_items=[])
        out = G.render_orcamento_html(d)
        self.assertIn("R$ 10,00", out)
        self.assertIn("1 item<", out)
        self.assertIn("Orcamento_ABC1D23_MecatroniCar", out)

    def test_quarenta_itens_repete_cabecalho_e_nao_quebra_linha(self):
        d = dict(BASE, pecas_items=_itens(30), servicos_items=_itens(15, "Serviço"))
        out = G.render_orcamento_html(d)
        self.assertIn("table-header-group", out)
        self.assertIn("break-inside: avoid", out)
        self.assertEqual(out.count("<tr><td class=\"idx\">"), 45)
        self.assertIn("counter(pages)", out)

    def test_campos_ausentes_e_valores_zerados_nao_quebram(self):
        out = G.render_orcamento_html({})
        self.assertIn("SEM PLACA", out)
        self.assertIn("R$ 0,00", out)
        out2 = G.render_orcamento_html(dict(BASE, pecas_items=[{"description": None}], total="R$ 0,00"))
        self.assertIn("(sem descrição)", out2)

    def test_html_escapado_e_acentos(self):
        d = dict(BASE, client_name="<script>alert(1)</script> Ávila", complaint="Óleo & água")
        out = G.render_orcamento_html(d)
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("Ávila", out)
        self.assertIn("Óleo &amp; água", out)

    def test_desconto_so_aparece_quando_diferente_de_zero(self):
        com = G.render_orcamento_html(dict(BASE, pecas_items=_itens(1), discount="R$ 5,00", total="R$ 5,00"))
        sem = G.render_orcamento_html(dict(BASE, pecas_items=_itens(1), discount="R$ 0,00"))
        self.assertIn("Desconto", com)
        self.assertNotIn("Desconto", sem)

    def test_laudo_longo_vai_como_anexo_depois_da_assinatura(self):
        laudo = "\n".join(f"Linha {i}" for i in range(40))
        out = G.render_orcamento_html(dict(BASE, complaint_comment=laudo))
        self.assertLess(out.index("Responsável técnico"), out.index("Anexo"))

    def test_sem_emojis(self):
        out = G.render_orcamento_html(dict(BASE, pecas_items=_itens(2)))
        self.assertEqual(EMOJI.findall(out), [])


class TestChecklist(unittest.TestCase):
    def test_sem_valores_financeiros(self):
        d = dict(BASE, pecas_items=_itens(3), servicos_items=_itens(2), total="R$ 999,00")
        out = G.render_checklist_html(d)
        self.assertNotIn("R$", out)
        self.assertEqual(out.count('class="chk"><div class="check-box">'), 5)
        self.assertIn("Checklist_ABC1D23_MecatroniCar", out)

    def test_secoes_do_mecanico(self):
        out = G.render_checklist_html(BASE)
        for txt in ("Anotações do mecânico", "Teste de rodagem", "Mecânico responsável"):
            self.assertIn(txt, out)

    def test_muitos_itens_e_campos_ausentes(self):
        out = G.render_checklist_html(dict(BASE, pecas_items=_itens(60)))
        self.assertEqual(out.count('class="chk"><div class="check-box">'), 60)
        G.render_checklist_html({})


class TestHistorico(unittest.TestCase):
    def _visita(self, n):
        return {
            "visit_num": str(n), "entry_date": f"0{n}/10/2026", "odometer": str(10000 * n),
            "complaint": "Revisão", "details": {
                "pecas_items": _itens(2), "servicos_items": _itens(1, "Serviço"),
                "total_geral": "R$ 30,00",
            },
        }

    def test_linha_do_tempo_com_e_sem_valores(self):
        visitas = [self._visita(3), self._visita(2), self._visita(1)]
        com = G.render_consolidated_history_html(BASE, visitas)
        sem = G.render_consolidated_history_html(BASE, visitas, without_prices=True)
        self.assertIn("HISTÓRICO COMPLETO", com)
        self.assertIn("R$ 90,00", com)
        self.assertIn("SEM VALORES", sem)
        self.assertNotIn("R$", sem)
        self.assertIn("Historico_ABC1D23_MecatroniCar", com)
        self.assertEqual(len(re.findall(r'<div class="visit(?: latest)?">', com)), 3)

    def test_vazio_e_sem_itens(self):
        self.assertIn("Nenhuma visita", G.render_consolidated_history_html(BASE, []))
        out = G.render_consolidated_history_html(BASE, [{"visit_num": "1"}])
        self.assertIn("Nenhum item registrado", out)


if __name__ == "__main__":
    unittest.main()
