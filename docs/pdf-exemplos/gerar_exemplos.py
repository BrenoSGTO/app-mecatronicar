# -*- coding: utf-8 -*-
"""
Gera os PDFs de exemplo (via Edge headless) e um PNG por página 1 para revisão visual.

Uso (na raiz do repositório):
    python docs/pdf-exemplos/gerar_exemplos.py [--todas-as-paginas]

Requer: Microsoft Edge instalado e PyMuPDF (apenas para esta revisão; o app não usa).
"""
import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))

import fitz  # PyMuPDF
import parser as P
import pdf_generator as G

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
EDGE = next((p for p in EDGE_CANDIDATES if os.path.exists(p)), None)


def sample(plate, visit):
    pat = os.path.join(ROOT, "planilhas_exemplo", f"{plate} - {visit} -*.xlsx")
    pat2 = os.path.join(ROOT, "planilhas_exemplo", f"{plate} -{visit} -*.xlsx")
    hits = glob.glob(pat) + glob.glob(pat2)
    return P.parse_file(hits[0])


def html_to_pdf(html_text, name, todas):
    html_path = os.path.join(tempfile.gettempdir(), f"{name}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    pdf_path = os.path.join(OUT, f"{name}.pdf")
    subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", "file:///" + html_path.replace("\\", "/")],
        check=True, capture_output=True, timeout=120,
    )
    doc = fitz.open(pdf_path)
    pages = range(len(doc)) if todas else [0]
    for i in pages:
        suffix = "" if (i == 0 and not todas) else f"_p{i + 1}"
        doc[i].get_pixmap(dpi=110).save(os.path.join(OUT, f"{name}{suffix}.png"))
    print(f"{name}: {len(doc)} página(s)")
    doc.close()


def fixtures():
    real = sample("FNB 1A77", 7)
    one = dict(real, pecas_items=real["pecas_items"][:1], servicos_items=[],
               total_pecas="R$ 724,00", total_servicos="R$ 0,00", subtotal="R$ 724,00",
               discount="", total="R$ 724,00", complaint_comment="")
    many_p = [dict(description=f"Peça de teste número {i} com descrição razoavelmente comprida para ocupar espaço",
                   quantity=str(1 + i % 3), unit_price="R$ 85,50", total_price=f"R$ {85.5 * (1 + i % 3):.2f}".replace(".", ","))
              for i in range(1, 29)]
    many_s = [dict(description=f"Serviço {i}: substituição, regulagem e teste funcional do conjunto",
                   quantity="1", unit_price="R$ 120,00", total_price="R$ 120,00") for i in range(1, 19)]
    big = dict(real, pecas_items=many_p, servicos_items=many_s, total_pecas="R$ 3.123,00",
               total_servicos="R$ 2.160,00", subtotal="R$ 5.283,00", discount="R$ 283,00", total="R$ 5.000,00")
    odd = dict(
        plate="DFR7812", plate_display="DFR-7812", client_name="Maria Conceição d'Ávila Nogueira de Albuquerque e Souza Filho",
        car_brand="Volkswagen", car_model="Gol 1.6 MSI Total Flex Comfortline Plus Edição Especial Aniversário",
        car_color="Cinza-chumbo", visit_num="12",
        complaint="Barulho estranho na suspensão dianteira ao passar em lombadas e ruído de ‘estalo’ ao esterçar " * 2,
        pecas_items=[dict(description="Amortecedor dianteiro direito e esquerdo (par) com coxim, batente e kit de reparo completo, linha premium", quantity="2", unit_price="R$ 0,00", total_price="R$ 0,00"),
                     dict(description="Anel de vedação ÓLEO/ÁGUA — Ø 12,5mm", quantity="", unit_price="", total_price="")],
        servicos_items=[], total_pecas="R$ 0,00", total_servicos="R$ 0,00", subtotal="R$ 0,00", total="R$ 0,00",
    )
    old_plate = sample("DFR 7812", 1)
    return {
        "orcamento_real_fnb1a77": ("orc", real),
        "orcamento_1_item": ("orc", one),
        "orcamento_50_itens": ("orc", big),
        "orcamento_campos_ausentes_nomes_longos": ("orc", odd),
        "orcamento_placa_antiga": ("orc", old_plate),
        "checklist_real_fnb1a77": ("chk", real),
        "checklist_50_itens": ("chk", {k: v for k, v in big.items() if k != "items"}),
        "checklist_campos_ausentes": ("chk", odd),
    }


def history_case(plate, n=None):
    files = sorted(glob.glob(os.path.join(ROOT, "planilhas_exemplo", f"{plate} -*.xlsx")))
    visits = []
    for f in files:
        d = P.parse_file(f)
        visits.append(dict(visit_num=d["visit_num"], entry_date=d["entry_date"], odometer=d["odometer"],
                           complaint=d["complaint"], details=d, plate=d["plate"],
                           entry_date_sort="".join(reversed((d["entry_date"] or "").split("/")))))
    visits.sort(key=lambda v: (v["entry_date_sort"], int(v["visit_num"] or 0)), reverse=True)
    return visits[:n] if n else visits


def main():
    todas = "--todas-as-paginas" in sys.argv
    if not EDGE:
        sys.exit("Edge não encontrado")
    for name, (kind, data) in fixtures().items():
        fn = G.render_orcamento_html if kind == "orc" else G.render_checklist_html
        html_to_pdf(fn(data), name, todas)
    visits = history_case("BRA 2E19")
    d0 = visits[0]["details"]
    veiculo = dict(plate=d0["plate"], plate_display=d0["plate_display"], client_name=d0["client_name"],
                   car_model=d0["car_model"], car_year=d0["car_year"], car_color=d0["car_color"])
    html_to_pdf(G.render_consolidated_history_html(veiculo, visits, without_prices=False), "historico_completo_BRA2E19", todas)
    html_to_pdf(G.render_consolidated_history_html(veiculo, visits[:5], without_prices=True), "historico_sem_valores_BRA2E19", todas)


if __name__ == "__main__":
    main()
