# -*- coding: utf-8 -*-
"""
MecatroniCar - Gerador de Documentos Profissionais (Orçamento/OS e Checklist)
Implementa os Checkpoints CP-04 (Checklist sem valores para mecânicos) e CP-05 (Orçamento/OS Profissional com Logo).
"""
import os
import html
import datetime
from parser import parse_file, format_plate_display


def _esc(val):
    if val is None:
        return ""
    return html.escape(str(val).strip())


def _format_address_line(d):
    parts = []
    addr = d.get("address", "")
    num = d.get("address_num", "")
    compl = d.get("address_compl", "")
    if addr:
        s = addr
        if num:
            s += f", nº {num}"
        if compl:
            s += f" (Compl: {compl})"
        parts.append(s)
    neigh = d.get("neighborhood", "")
    city = d.get("city", "")
    cep = d.get("cep", "")
    loc_parts = [p for p in (neigh, city) if p]
    if loc_parts:
        parts.append(" - ".join(loc_parts))
    if cep:
        parts.append(f"CEP: {cep}")
    return " • ".join(parts)


def _format_km(val):
    if not val:
        return "—"
    digits = "".join(c for c in str(val) if c.isdigit())
    if digits:
        try:
            return f"{int(digits):,} km".replace(",", ".")
        except Exception:
            pass
    return f"{val} km"


def _get_logo_data_uri():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "static", "logo.png")
        if os.path.exists(logo_path):
            import base64
            with open(logo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
                return f"data:image/png;base64,{b64}"
    except Exception:
        pass
    return "/logo.png"


def render_orcamento_html(parsed_data, auto_print=False):
    """
    CP-05: Gera o HTML/PDF de alta qualidade para o Orçamento / Ordem de Serviço
    com layout corporativo, minimalista e profissional da MecatroniCar.
    Títulos e subtítulos em negrito com linha de separação inferior, sem excesso
    de bordas de caixas ou cabeçalhos visuais pesados (design limpo).
    """
    d = parsed_data or {}
    plate_disp = d.get("plate_display") or format_plate_display(d.get("plate", "")) or "SEM PLACA"
    visit_num = d.get("visit_num") or "—"
    client_name = d.get("client_name") or "Cliente não informado"
    cpf = d.get("cpf") or "—"
    rg = d.get("rg") or ""
    phone = d.get("phone") or "—"
    email = d.get("email") or ""
    full_address = _format_address_line(d) or "—"

    car_brand = d.get("car_brand") or ""
    car_model = d.get("car_model") or "Veículo não informado"
    car_full = f"{car_brand} {car_model}".strip()
    car_year = d.get("car_year") or "—"
    car_color = d.get("car_color") or "—"
    car_fuel = d.get("car_fuel") or "—"
    car_chassis = d.get("car_chassis") or "—"

    entry_date = d.get("entry_date") or datetime.datetime.now().strftime("%d/%m/%Y")
    entry_time = d.get("entry_time") or ""
    exit_date = d.get("exit_date") or "—"
    exit_time = d.get("exit_time") or ""
    odometer = _format_km(d.get("odometer"))
    complaint = d.get("complaint") or "Revisão / Manutenção Automotiva"
    complaint_comment = d.get("complaint_comment") or ""
    payment_method = d.get("payment_method") or "A combinar"

    pecas = d.get("pecas_items") or []
    servicos = d.get("servicos_items") or []

    total_pecas = d.get("total_pecas") or "R$ 0,00"
    total_servicos = d.get("total_servicos") or "R$ 0,00"
    subtotal = d.get("subtotal") or "R$ 0,00"
    discount = d.get("discount") or ""
    total = d.get("total") or subtotal or "R$ 0,00"

    doc_title = f"Orcamento_OS_{plate_disp.replace('-', '')}_Visita_{visit_num}_MecatroniCar"
    logo_src = _get_logo_data_uri()

    pecas_rows_html = ""
    if pecas:
        for idx, it in enumerate(pecas, 1):
            pecas_rows_html += f"""
            <tr>
                <td class="col-idx">{idx:02d}</td>
                <td class="col-desc">{_esc(it.get('description'))}</td>
                <td class="col-qty">{_esc(it.get('quantity') or '1')}</td>
                <td class="col-unit">{_esc(it.get('unit_price') or '—')}</td>
                <td class="col-total">{_esc(it.get('total_price') or '—')}</td>
            </tr>
            """
    else:
        pecas_rows_html = """
        <tr>
            <td colspan="5" class="empty-row">Nenhuma peça discriminada nesta Ordem de Serviço.</td>
        </tr>
        """

    servicos_rows_html = ""
    if servicos:
        for idx, it in enumerate(servicos, 1):
            servicos_rows_html += f"""
            <tr>
                <td class="col-idx">{idx:02d}</td>
                <td class="col-desc">{_esc(it.get('description'))}</td>
                <td class="col-qty">{_esc(it.get('quantity') or '1')}</td>
                <td class="col-unit">{_esc(it.get('unit_price') or '—')}</td>
                <td class="col-total">{_esc(it.get('total_price') or '—')}</td>
            </tr>
            """
    else:
        servicos_rows_html = """
        <tr>
            <td colspan="5" class="empty-row">Mão de obra / serviços inclusos ou não discriminados separadamente.</td>
        </tr>
        """

    scanner_block_html = ""
    if complaint_comment:
        scanner_block_html = f"""
        <div class="section-block">
            <div class="section-title">
                <span>Diagnóstico Técnico / Leitura de Scanner / Observações</span>
            </div>
            <pre class="scanner-pre">{_esc(complaint_comment)}</pre>
        </div>
        """

    auto_print_script = "window.addEventListener('load', () => { setTimeout(() => window.print(), 350); });" if auto_print else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{_esc(doc_title)}</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 12mm 14mm;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #e2e8f0;
            color: #0f172a;
            font-size: 11.5px;
            line-height: 1.45;
        }}
        /* Floating Action Bar (Screen Only) */
        .print-toolbar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: #111827;
            border-bottom: 2px solid #f9cc01;
            color: #ffffff;
            padding: 10px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}
        .toolbar-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .toolbar-badge {{
            background: #f9cc01;
            color: #111827;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .toolbar-title {{
            font-size: 13.5px;
            font-weight: 600;
            color: #f8fafc;
        }}
        .toolbar-actions {{
            display: flex;
            gap: 10px;
        }}
        .btn-action {{
            border: none;
            border-radius: 6px;
            padding: 7px 14px;
            font-size: 12.5px;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
            transition: all 0.15s;
        }}
        .btn-primary {{
            background: #f9cc01;
            color: #111827;
        }}
        .btn-primary:hover {{
            background: #e5b800;
        }}
        .btn-secondary {{
            background: #1f2937;
            color: #f8fafc;
            border: 1px solid #374151;
        }}
        .btn-secondary:hover {{
            background: #374151;
        }}

        /* A4 Sheet Container */
        .sheet {{
            max-width: 210mm;
            margin: 20px auto;
            background: #ffffff;
            padding: 14mm 16mm;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
            border-radius: 2px;
        }}

        /* Document Header */
        .doc-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            padding-bottom: 12px;
            margin-bottom: 14px;
            border-bottom: 2px solid #0f172a;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .brand-logo {{
            width: 58px;
            height: 58px;
            object-fit: contain;
        }}
        .brand-name {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #0f172a;
            line-height: 1.1;
        }}
        .brand-legal {{
            font-size: 10.5px;
            font-weight: 600;
            color: #334155;
            margin-top: 3px;
        }}
        .brand-meta {{
            font-size: 10px;
            color: #64748b;
            margin-top: 1px;
        }}
        .header-right {{
            text-align: right;
            padding-top: 2px;
        }}
        .doc-kind {{
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: #64748b;
        }}
        .doc-number {{
            font-size: 17px;
            font-weight: 800;
            color: #0f172a;
            margin: 2px 0 3px 0;
            letter-spacing: -0.3px;
        }}
        .doc-dates {{
            font-size: 10.5px;
            color: #475569;
            line-height: 1.4;
        }}
        .doc-dates strong {{
            color: #1e293b;
        }}

        /* Section Headings: Apenas em negrito, fonte um pouco maior e linha de separação embaixo */
        .section-block {{
            margin-bottom: 14px;
        }}
        .section-title {{
            font-size: 12.5px;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding-bottom: 4px;
            margin-bottom: 8px;
            border-bottom: 1.5px solid #0f172a;
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}
        .section-title .section-meta {{
            font-size: 10px;
            font-weight: 500;
            color: #64748b;
            text-transform: none;
            letter-spacing: 0;
        }}

        /* Client & Vehicle 2-Column Info Grid */
        .info-grid {{
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 20px;
            margin-bottom: 14px;
        }}
        .info-col {{
            display: flex;
            flex-direction: column;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }}
        .info-table td {{
            padding: 2.5px 0;
            vertical-align: top;
        }}
        .info-table .lbl {{
            width: 78px;
            font-weight: 600;
            color: #64748b;
        }}
        .info-table .val {{
            color: #0f172a;
        }}
        .info-table .val strong {{
            color: #0f172a;
            font-weight: 700;
        }}
        .plate-text {{
            font-family: "Consolas", "Courier New", monospace;
            font-weight: 800;
            font-size: 12px;
            color: #0f172a;
            letter-spacing: 0.5px;
        }}

        /* Complaint / Symptom Section */
        .complaint-content {{
            font-size: 11.5px;
            color: #0f172a;
            line-height: 1.45;
            padding: 2px 0 4px 0;
        }}

        /* Tables for Parts and Services */
        table.doc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }}
        table.doc-table th {{
            color: #475569;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 9.5px;
            letter-spacing: 0.5px;
            padding: 5px 6px;
            border-bottom: 1.5px solid #0f172a;
            text-align: left;
        }}
        table.doc-table td {{
            padding: 5px 6px;
            border-bottom: 1px solid #e2e8f0;
            color: #0f172a;
            vertical-align: middle;
        }}
        table.doc-table tr:last-child td {{
            border-bottom: 1px solid #cbd5e1;
        }}
        .col-idx {{
            width: 30px;
            color: #64748b;
            font-weight: 600;
            text-align: center;
        }}
        .col-desc {{
            font-weight: 500;
        }}
        .col-qty {{
            width: 50px;
            text-align: center;
            font-weight: 600;
        }}
        .col-unit {{
            width: 95px;
            text-align: right;
            color: #334155;
        }}
        .col-total {{
            width: 100px;
            text-align: right;
            font-weight: 700;
            color: #0f172a;
        }}
        .empty-row {{
            text-align: center;
            color: #64748b;
            font-style: italic;
            padding: 8px !important;
        }}
        .subtotal-row {{
            text-align: right;
            font-size: 11px;
            color: #475569;
            padding: 5px 6px 4px 6px;
        }}
        .subtotal-row strong {{
            color: #0f172a;
            font-size: 11.5px;
            font-weight: 700;
            margin-left: 6px;
        }}

        /* Technical Notes / Scanner */
        .scanner-pre {{
            font-family: "Consolas", "Courier New", monospace;
            font-size: 10.5px;
            line-height: 1.45;
            white-space: pre-wrap;
            padding: 8px 12px;
            background: #f8fafc;
            border-left: 3px solid #94a3b8;
            color: #1e293b;
        }}

        /* Bottom Grid: Terms/Signatures & Financial Summary */
        .bottom-grid {{
            display: grid;
            grid-template-columns: 1fr 270px;
            gap: 24px;
            margin-top: 10px;
            align-items: start;
            page-break-inside: avoid;
        }}
        .terms-block {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            font-size: 10.5px;
            color: #475569;
            line-height: 1.45;
        }}
        .terms-text p {{
            margin-bottom: 5px;
        }}
        .terms-text strong {{
            color: #1e293b;
        }}
        .signature-area {{
            margin-top: 34px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            text-align: center;
        }}
        .sig-line {{
            border-top: 1px solid #475569;
            padding-top: 4px;
            font-weight: 600;
            font-size: 10px;
            color: #1e293b;
        }}

        /* Financial Summary Table */
        .totals-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11.5px;
        }}
        .totals-table td {{
            padding: 4px 4px;
        }}
        .tot-lbl {{
            color: #475569;
            font-weight: 500;
        }}
        .tot-val {{
            text-align: right;
            color: #0f172a;
            font-weight: 600;
        }}
        .tot-val.discount {{
            color: #15803d;
        }}
        .totals-table tr.final-row td {{
            padding-top: 8px;
            border-top: 1.5px solid #0f172a;
            font-size: 13.5px;
            font-weight: 800;
            color: #0f172a;
        }}

        @media print {{
            body {{
                background: #ffffff;
            }}
            .print-toolbar {{
                display: none !important;
            }}
            .sheet {{
                margin: 0;
                padding: 0;
                box-shadow: none;
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div class="toolbar-left">
            <span class="toolbar-badge">Orçamento / OS</span>
            <span class="toolbar-title">{_esc(plate_disp)} — {_esc(client_name)} ({_esc(car_model)})</span>
        </div>
        <div class="toolbar-actions">
            <a class="btn-action btn-secondary" href="/api/checklist_pdf?file_path={html.escape(d.get('file_path', ''), quote=True)}">
                📋 Mudar para Checklist (Sem Valores)
            </a>
            <button class="btn-action btn-primary" onclick="window.print()">
                🖨️ Imprimir / Salvar como PDF
            </button>
        </div>
    </div>

    <div class="sheet">
        <!-- Header -->
        <header class="doc-header">
            <div class="header-left">
                <img src="{logo_src}" alt="MecatroniCar" class="brand-logo">
                <div class="brand-info">
                    <div class="brand-name">MecatroniCar</div>
                    <div class="brand-legal">Mecatroni Car - Serviços e Autopeças Ltda • CNPJ: 05.961.672/0001-87</div>
                    <div class="brand-meta">Manutenção e Reparação Mecânica Automotiva &amp; Autopeças • Santos/SP</div>
                </div>
            </div>
            <div class="header-right">
                <div class="doc-kind">Ordem de Serviço / Orçamento</div>
                <div class="doc-number">VISITA Nº {_esc(visit_num)}</div>
                <div class="doc-dates">
                    <span><strong>Entrada:</strong> {_esc(entry_date)} {_esc(entry_time)}</span>
                    {f'<br><span><strong>Saída:</strong> {_esc(exit_date)} {_esc(exit_time)}</span>' if exit_date and exit_date != '—' else ''}
                </div>
            </div>
        </header>

        <!-- Client & Vehicle Info Grid -->
        <div class="info-grid">
            <div class="info-col">
                <div class="section-title">
                    <span>Dados do Cliente</span>
                </div>
                <table class="info-table">
                    <tr>
                        <td class="lbl">Cliente:</td>
                        <td class="val"><strong>{_esc(client_name)}</strong></td>
                    </tr>
                    <tr>
                        <td class="lbl">CPF/CNPJ:</td>
                        <td class="val">{_esc(cpf)}{f' &nbsp;|&nbsp; <strong>RG:</strong> {_esc(rg)}' if rg else ''}</td>
                    </tr>
                    <tr>
                        <td class="lbl">Telefone:</td>
                        <td class="val">{_esc(phone)}</td>
                    </tr>
                    <tr>
                        <td class="lbl">Endereço:</td>
                        <td class="val">{_esc(full_address)}</td>
                    </tr>
                    {f'<tr><td class="lbl">E-mail:</td><td class="val">{_esc(email)}</td></tr>' if email else ''}
                </table>
            </div>

            <div class="info-col">
                <div class="section-title">
                    <span>Dados do Veículo</span>
                </div>
                <table class="info-table">
                    <tr>
                        <td class="lbl">Placa:</td>
                        <td class="val"><span class="plate-text">{_esc(plate_disp)}</span></td>
                    </tr>
                    <tr>
                        <td class="lbl">Veículo:</td>
                        <td class="val"><strong>{_esc(car_full)}</strong></td>
                    </tr>
                    <tr>
                        <td class="lbl">Ano / Cor:</td>
                        <td class="val">{_esc(car_year)} • {_esc(car_color)}</td>
                    </tr>
                    <tr>
                        <td class="lbl">Combustível:</td>
                        <td class="val">{_esc(car_fuel)} &nbsp;|&nbsp; <strong>KM:</strong> {_esc(odometer)}</td>
                    </tr>
                    {f'<tr><td class="lbl">Chassi:</td><td class="val">{_esc(car_chassis)}</td></tr>' if car_chassis and car_chassis != '—' else ''}
                </table>
            </div>
        </div>

        <!-- Complaint / Symptom Section -->
        <div class="section-block">
            <div class="section-title">
                <span>Solicitação do Cliente / Sintoma Relatado</span>
            </div>
            <div class="complaint-content">
                {_esc(complaint)}
            </div>
        </div>

        <!-- Parts Section -->
        <div class="section-block">
            <div class="section-title">
                <span>Peças e Insumos Aplicados</span>
                <span class="section-meta">{len(pecas)} {('item' if len(pecas) == 1 else 'itens')} • CNAE 4530-7/03</span>
            </div>
            <table class="doc-table">
                <thead>
                    <tr>
                        <th class="col-idx">#</th>
                        <th>Descrição da Peça / Material Aplicado</th>
                        <th class="col-qty">Quant.</th>
                        <th class="col-unit">Valor Unit.</th>
                        <th class="col-total">Valor Total</th>
                    </tr>
                </thead>
                <tbody>
                    {pecas_rows_html}
                </tbody>
            </table>
            <div class="subtotal-row">
                Subtotal de Peças: <strong>{_esc(total_pecas)}</strong>
            </div>
        </div>

        <!-- Services Section -->
        <div class="section-block">
            <div class="section-title">
                <span>Serviços Executados / Mão de Obra</span>
                <span class="section-meta">{len(servicos)} {('item' if len(servicos) == 1 else 'itens')} • Item 14.01</span>
            </div>
            <table class="doc-table">
                <thead>
                    <tr>
                        <th class="col-idx">#</th>
                        <th>Descrição do Serviço / Mão de Obra Técnica</th>
                        <th class="col-qty">Quant.</th>
                        <th class="col-unit">Valor Unit.</th>
                        <th class="col-total">Valor Total</th>
                    </tr>
                </thead>
                <tbody>
                    {servicos_rows_html}
                </tbody>
            </table>
            <div class="subtotal-row">
                Subtotal de Mão de Obra: <strong>{_esc(total_servicos)}</strong>
            </div>
        </div>

        {scanner_block_html}

        <!-- Bottom Grid: Terms & Financial Summary -->
        <div class="bottom-grid">
            <div class="terms-block">
                <div>
                    <div class="section-title">
                        <span>Condições Gerais e Garantia</span>
                    </div>
                    <div class="terms-text">
                        <p>• <strong>Forma de Pagamento:</strong> {_esc(payment_method)}</p>
                        <p>• Serviços e peças contam com garantia legal de 90 dias conforme o Código de Defesa do Consumidor (Art. 26, II, Lei nº 8.078/90), respeitadas as condições de uso e especificações do fabricante.</p>
                    </div>
                </div>
                <div class="signature-area">
                    <div class="sig-line">MecatroniCar — Responsável Técnico</div>
                    <div class="sig-line">{_esc(client_name)} — Cliente</div>
                </div>
            </div>

            <div class="totals-block">
                <div class="section-title">
                    <span>Resumo Financeiro</span>
                </div>
                <table class="totals-table">
                    <tr>
                        <td class="tot-lbl">Total de Peças:</td>
                        <td class="tot-val">{_esc(total_pecas)}</td>
                    </tr>
                    <tr>
                        <td class="tot-lbl">Total de Serviços:</td>
                        <td class="tot-val">{_esc(total_servicos)}</td>
                    </tr>
                    <tr>
                        <td class="tot-lbl">Subtotal:</td>
                        <td class="tot-val">{_esc(subtotal)}</td>
                    </tr>
                    {f'<tr><td class="tot-lbl">Desconto:</td><td class="tot-val discount">- {_esc(discount)}</td></tr>' if discount and discount != 'R$ 0,00' else ''}
                    <tr class="final-row">
                        <td class="tot-lbl">TOTAL GERAL:</td>
                        <td class="tot-val">{_esc(total)}</td>
                    </tr>
                </table>
            </div>
        </div>
    </div>

    <script>
        {auto_print_script}
    </script>
</body>
</html>
"""


def render_checklist_html(parsed_data, auto_print=False, include_scanner=True, custom_items=None, pecas=None, servicos=None):
    """
    CP-04 / Issue #13: Gera o HTML/PDF de Checklist Operacional Customizável para deixar no para-brisa do veículo.
    NÃO exibe nenhum valor monetário (apenas descrições, quantidades e checkboxes de execução).
    Permite escolher quais itens vão aparecer, adicionar itens manualmente e ativar/desativar códigos de scanner.
    """
    d = parsed_data or {}
    plate_disp = d.get("plate_display") or format_plate_display(d.get("plate", "")) or "SEM PLACA"
    visit_num = d.get("visit_num") or "—"
    client_name = d.get("client_name") or "Cliente não informado"
    phone = d.get("phone") or "—"

    car_brand = d.get("car_brand") or ""
    car_model = d.get("car_model") or "Veículo"
    car_full = f"{car_brand} {car_model}".strip()
    car_year = d.get("car_year") or "—"
    car_color = d.get("car_color") or "—"
    car_fuel = d.get("car_fuel") or "—"

    entry_date = d.get("entry_date") or datetime.datetime.now().strftime("%d/%m/%Y")
    entry_time = d.get("entry_time") or ""
    odometer = _format_km(d.get("odometer"))
    complaint = d.get("complaint") or "Revisão / Manutenção"
    complaint_comment = d.get("complaint_comment") or ""

    # Determina toggle do Scanner OBD2
    if include_scanner is None:
        include_scanner = d.get("include_scanner", True)
    if isinstance(include_scanner, str):
        include_scanner = include_scanner.lower() not in ("0", "false", "no", "nao", "não")
    include_scanner = bool(include_scanner)

    # Resolução de Peças e Serviços (customizados ou originais da visita)
    if pecas is None:
        if "pecas" in d and isinstance(d["pecas"], list):
            pecas = list(d["pecas"])
        elif custom_items is not None or "items" in d:
            all_items = custom_items if custom_items is not None else d.get("items", [])
            pecas = [
                it for it in all_items
                if str(it.get("type", "")).lower() in ("peca", "peça", "part")
                or str(it.get("section", "")).lower() in ("peca", "peça")
                or (not it.get("type") and str(it.get("section", "")).lower() not in ("serviço", "servico"))
            ]
        elif "pecas_items" in d and isinstance(d["pecas_items"], list):
            pecas = list(d["pecas_items"])
        else:
            pecas = []
    else:
        pecas = list(pecas)

    if servicos is None:
        if "servicos" in d and isinstance(d["servicos"], list):
            servicos = list(d["servicos"])
        elif custom_items is not None or "items" in d:
            all_items = custom_items if custom_items is not None else d.get("items", [])
            servicos = [
                it for it in all_items
                if str(it.get("type", "")).lower() in ("servico", "serviço", "service")
                or str(it.get("section", "")).lower() in ("servico", "serviço")
            ]
        elif "servicos_items" in d and isinstance(d["servicos_items"], list):
            servicos = list(d["servicos_items"])
        else:
            servicos = []
    else:
        servicos = list(servicos)

    # Suporte a itens manuais adicionados via interface
    manual_items = d.get("manual_items") or []
    if manual_items:
        for m_item in manual_items:
            m_type = str(m_item.get("type", "")).lower()
            if m_type in ("servico", "serviço", "service"):
                servicos.append(m_item)
            else:
                pecas.append(m_item)

    doc_title = f"Checklist_{plate_disp.replace('-', '')}_Visita_{visit_num}_MecatroniCar"

    pecas_rows_html = ""
    if pecas:
        for idx, it in enumerate(pecas, 1):
            note_html = f'<div class="item-tech-note">📌 Obs: {_esc(it.get("comment"))}</div>' if it.get("comment") else ""
            pecas_rows_html += f"""
            <tr>
                <td class="col-check"><div class="check-box"></div></td>
                <td class="col-qty">{_esc(it.get('quantity') or '1')}</td>
                <td class="col-desc">
                    <div class="item-main-desc">{_esc(it.get('description'))}</div>
                    {note_html}
                </td>
                <td class="col-mec-initial"></td>
            </tr>
            """
    else:
        pecas_rows_html = """
        <tr>
            <td colspan="4" class="empty-row">Nenhuma peça selecionada para este checklist.</td>
        </tr>
        """

    servicos_rows_html = ""
    if servicos:
        for idx, it in enumerate(servicos, 1):
            note_html = f'<div class="item-tech-note">📌 Obs: {_esc(it.get("comment"))}</div>' if it.get("comment") else ""
            servicos_rows_html += f"""
            <tr>
                <td class="col-check"><div class="check-box"></div></td>
                <td class="col-qty">{_esc(it.get('quantity') or '1')}</td>
                <td class="col-desc">
                    <div class="item-main-desc">{_esc(it.get('description'))}</div>
                    {note_html}
                </td>
                <td class="col-mec-initial"></td>
            </tr>
            """
    else:
        servicos_rows_html = """
        <tr>
            <td colspan="4" class="empty-row">Nenhum serviço selecionado para este checklist.</td>
        </tr>
        """

    scanner_block_html = ""
    if include_scanner and complaint_comment:
        scanner_block_html = f"""
        <div class="section-box">
            <div class="section-title-bar">
                <span>🔎 CÓDIGOS DE FALHA (SCANNER) / ANOTAÇÕES DE DIAGNÓSTICO</span>
            </div>
            <pre class="scanner-pre">{_esc(complaint_comment)}</pre>
        </div>
        """

    auto_print_script = "window.addEventListener('load', () => { setTimeout(() => window.print(), 350); });" if auto_print else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{_esc(doc_title)}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>
        @page {{
            size: A4 portrait;
            margin: 10mm 12mm;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #e2e8f0;
            color: #0f172a;
            font-size: 13px;
            line-height: 1.4;
        }}
        .print-toolbar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: #111827;
            border-bottom: 3px solid #f9cc01;
            color: #ffffff;
            padding: 10px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
        .toolbar-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .toolbar-badge {{
            background: #10b981;
            color: #ffffff;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .toolbar-title {{
            font-size: 14px;
            font-weight: 600;
            color: #f8fafc;
        }}
        .toolbar-actions {{
            display: flex;
            gap: 10px;
        }}
        .btn-action {{
            border: none;
            border-radius: 7px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }}
        .btn-primary {{
            background: #f9cc01;
            color: #111827;
        }}
        .btn-secondary {{
            background: #1f2937;
            color: #f8fafc;
            border: 1px solid #374151;
        }}

        .sheet {{
            max-width: 210mm;
            margin: 20px auto;
            background: #ffffff;
            padding: 12mm 14mm;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
            border-radius: 4px;
        }}

        /* Top Banner Designed for Windshield & Shop Floor Visibility */
        .windshield-header {{
            display: flex;
            justify-content: space-between;
            align-items: stretch;
            border: 3px solid #111827;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 12px;
            background: #ffffff;
        }}
        .ws-brand-col {{
            background: #111827;
            color: #ffffff;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-right: 4px solid #f9cc01;
            min-width: 210px;
        }}
        .ws-logo {{
            width: 52px;
            height: 52px;
            object-fit: contain;
        }}
        .ws-title {{
            font-size: 22px;
            font-weight: 900;
            color: #f9cc01;
            text-transform: uppercase;
            line-height: 1.1;
            letter-spacing: 0.5px;
        }}
        .ws-subtitle {{
            font-size: 10.5px;
            color: #e2e8f0;
            font-weight: 600;
            margin-top: 3px;
            letter-spacing: 0.3px;
        }}
        .ws-car-col {{
            flex: 1;
            padding: 10px 16px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: #f8fafc;
            border-right: 2px solid #e2e8f0;
        }}
        .ws-car-model {{
            font-size: 26px;
            font-weight: 900;
            color: #0f172a;
            line-height: 1.15;
            letter-spacing: -0.3px;
        }}
        .ws-car-spec {{
            font-size: 14px;
            font-weight: 700;
            color: #475569;
            margin-left: 6px;
        }}
        .ws-car-meta {{
            margin-top: 6px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .ws-client-row {{
            font-size: 13.5px;
            font-weight: 600;
            color: #0f172a;
        }}
        .ws-client-name {{
            font-weight: 800;
            color: #0f172a;
        }}
        .ws-vehicle-row {{
            font-size: 12px;
            font-weight: 600;
            color: #475569;
            display: flex;
            gap: 16px;
        }}
        .ws-plate-col {{
            background: #f1f5f9;
            padding: 8px 16px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-width: 205px;
        }}

        /* Mercosul Brazilian Plate Drawing */
        .plate-mercosul {{
            width: 178px;
            height: 72px;
            background: #ffffff;
            border: 2.5px solid #000000;
            border-radius: 6px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        .plate-top-bar {{
            background: #003399 !important;
            color: #ffffff;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 8px;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        .plate-country {{
            font-size: 11px;
            font-weight: 900;
            letter-spacing: 2px;
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            line-height: 1;
        }}
        .plate-body {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #ffffff;
            padding: 2px 4px;
        }}
        .plate-number-text {{
            font-family: "Impact", "Arial Black", "Consolas", monospace, sans-serif;
            font-size: 26px;
            font-weight: 900;
            letter-spacing: 1.5px;
            color: #000000;
            line-height: 1;
            text-transform: uppercase;
        }}
        .ws-visit-badge {{
            font-size: 11px;
            font-weight: 800;
            background: #f9cc01;
            color: #111827;
            border: 1.5px solid #111827;
            border-radius: 4px;
            padding: 2px 10px;
            margin-top: 5px;
            letter-spacing: 0.5px;
            text-align: center;
        }}

        /* Complaint Box */
        .symptom-box {{
            border: 2px solid #111827;
            border-left: 8px solid #f9cc01;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 12px;
            background: #fefce8;
        }}
        .symptom-title {{
            font-size: 11px;
            font-weight: 900;
            text-transform: uppercase;
            color: #111827;
            margin-bottom: 2px;
        }}
        .symptom-text {{
            font-size: 14px;
            font-weight: 800;
            color: #0f172a;
        }}

        /* Checklist Tables */
        .section-box {{
            border: 2px solid #111827;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 12px;
        }}
        .section-title-bar {{
            background: #111827;
            color: #ffffff;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 0.5px;
            padding: 6px 12px;
            border-bottom: 3px solid #f9cc01;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        table.check-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        table.check-table th {{
            background: #f1f5f9;
            color: #0f172a;
            font-size: 11px;
            font-weight: 900;
            text-transform: uppercase;
            padding: 7px 10px;
            border-bottom: 2px solid #cbd5e1;
            text-align: left;
        }}
        table.check-table td {{
            padding: 9px 10px;
            border-bottom: 1px solid #cbd5e1;
            vertical-align: middle;
        }}
        table.check-table tr:last-child td {{
            border-bottom: none;
        }}
        .col-check {{
            width: 48px;
            text-align: center;
        }}
        .check-box {{
            width: 22px;
            height: 22px;
            border: 2.5px solid #0f172a;
            border-radius: 4px;
            margin: 0 auto;
            background: #ffffff;
        }}
        .col-qty {{
            width: 65px;
            text-align: center;
            font-size: 15px;
            font-weight: 900;
            color: #0f172a;
            border-left: 1px solid #e2e8f0;
            border-right: 1px solid #e2e8f0;
        }}
        .col-desc {{
            padding-left: 12px !important;
        }}
        .item-main-desc {{
            font-size: 14px;
            font-weight: 700;
            color: #0f172a;
        }}
        .item-tech-note {{
            font-size: 11.5px;
            color: #334155;
            margin-top: 2px;
            font-weight: 600;
        }}
        .col-mec-initial {{
            width: 90px;
            border-left: 1px dashed #cbd5e1;
        }}
        .empty-row {{
            text-align: center;
            color: #64748b;
            font-style: italic;
            padding: 12px !important;
        }}

        .scanner-pre {{
            font-family: "Consolas", "Courier New", monospace;
            font-size: 11px;
            white-space: pre-wrap;
            padding: 8px 10px;
            background: #f8fafc;
            color: #0f172a;
        }}

        @media print {{
            body {{
                background: #ffffff;
            }}
            .print-toolbar {{
                display: none !important;
            }}
            .sheet {{
                margin: 0;
                padding: 0;
                box-shadow: none;
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div class="toolbar-left">
            <span class="toolbar-badge">Checklist</span>
            <span class="toolbar-title">{_esc(plate_disp)} — {_esc(car_full)} ({_esc(client_name)})</span>
        </div>
        <div class="toolbar-actions">
            <a class="btn-action btn-secondary" href="/api/orcamento_pdf?file_path={html.escape(d.get('file_path', ''), quote=True)}">
                📄 Mudar para Orçamento Completo (Com Valores)
            </a>
            <button class="btn-action btn-primary" onclick="window.print()">
                🖨️ Imprimir Checklist
            </button>
        </div>
    </div>

    <div class="sheet">
        <!-- Top Identification Banner -->
        <div class="windshield-header">
            <div class="ws-brand-col">
                <img src="/logo.png" alt="MecatroniCar" class="ws-logo">
                <div>
                    <div class="ws-title">CHECKLIST</div>
                    <div class="ws-subtitle">MecatroniCar • FOLHA DE CHÃO DE OFICINA</div>
                </div>
            </div>
            <div class="ws-car-col">
                <div class="ws-car-model">{_esc(car_full)} <span class="ws-car-spec">({_esc(car_color)} • {_esc(car_year)})</span></div>
                <div class="ws-car-meta">
                    <div class="ws-client-row">
                        👤 <strong>Cliente:</strong> <span class="ws-client-name">{_esc(client_name)}</span>
                    </div>
                    <div class="ws-vehicle-row">
                        <span>⏱️ <strong>KM:</strong> {_esc(odometer)}</span>
                        <span>📅 <strong>Entrada:</strong> {_esc(entry_date)} {_esc(entry_time)}</span>
                    </div>
                </div>
            </div>
            <div class="ws-plate-col">
                <div class="plate-mercosul">
                    <div class="plate-top-bar">
                        <svg class="mercosul-emblem" viewBox="0 0 24 16" width="16" height="11">
                            <rect width="24" height="16" fill="#003399"/>
                            <circle cx="12" cy="4" r="1.2" fill="#ffffff"/>
                            <circle cx="7" cy="8" r="1.2" fill="#ffffff"/>
                            <circle cx="17" cy="8" r="1.2" fill="#ffffff"/>
                            <circle cx="12" cy="12" r="1.2" fill="#ffffff"/>
                        </svg>
                        <span class="plate-country">BRASIL</span>
                        <svg class="brasil-flag" viewBox="0 0 20 14" width="16" height="11">
                            <rect width="20" height="14" fill="#009c3b" rx="1"/>
                            <polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#ffdf00"/>
                            <circle cx="10" cy="7" r="3.2" fill="#002776"/>
                            <path d="M7.2,7 A3.2,3.2 0 0,0 12.8,7" stroke="#ffffff" stroke-width="0.6" fill="none"/>
                        </svg>
                    </div>
                    <div class="plate-body">
                        <span class="plate-number-text">{_esc(plate_disp)}</span>
                    </div>
                </div>
                <span class="ws-visit-badge">VISITA #{_esc(visit_num)}</span>
            </div>
        </div>

        <!-- Symptom / Complaint -->
        <div class="symptom-box">
            <div class="symptom-title">⚠️ DEFEITO RELATADO / SOLICITAÇÃO DO CLIENTE</div>
            <div class="symptom-text">{_esc(complaint)}</div>
        </div>

        <!-- Approved Parts Table (Zero Prices) -->
        <div class="section-box">
            <div class="section-title-bar">
                <span>🔩 PEÇAS APROVADAS PARA SUBSTITUIÇÃO / APLICAÇÃO ({len(pecas)})</span>
                <span>SEM VALORES • USO INTERNO OFICINA</span>
            </div>
            <table class="check-table">
                <thead>
                    <tr>
                        <th class="col-check">OK</th>
                        <th class="col-qty">QUANT.</th>
                        <th>DESCRIÇÃO DA PEÇA / COMPONENTE</th>
                        <th class="col-mec-initial" style="text-align: center;">VISTO</th>
                    </tr>
                </thead>
                <tbody>
                    {pecas_rows_html}
                </tbody>
            </table>
        </div>

        <!-- Approved Services Table (Zero Prices) -->
        <div class="section-box">
            <div class="section-title-bar">
                <span>🛠️ SERVIÇOS E MÃO DE OBRA APROVADOS ({len(servicos)})</span>
                <span>CONFERÊNCIA DE EXECUÇÃO</span>
            </div>
            <table class="check-table">
                <thead>
                    <tr>
                        <th class="col-check">OK</th>
                        <th class="col-qty">QTD</th>
                        <th>DESCRIÇÃO DO SERVIÇO A EXECUTAR</th>
                        <th class="col-mec-initial" style="text-align: center;">VISTO</th>
                    </tr>
                </thead>
                <tbody>
                    {servicos_rows_html}
                </tbody>
            </table>
        </div>

        {scanner_block_html}
    </div>

    <script>
        {auto_print_script}
    </script>
</body>
</html>
"""


def generate_orcamento_from_file(filepath, auto_print=False):
    parsed = parse_file(filepath)
    return render_orcamento_html(parsed, auto_print=auto_print)


def generate_checklist_from_file(filepath, auto_print=False, include_scanner=True, custom_items=None, pecas=None, servicos=None):
    parsed = parse_file(filepath)
    return render_checklist_html(
        parsed,
        auto_print=auto_print,
        include_scanner=include_scanner,
        custom_items=custom_items,
        pecas=pecas,
        servicos=servicos
    )


def render_consolidated_history_html(vehicle_info, visits, without_prices=False, auto_print=False):
    """
    CP-09 / Issue #13: Gera o HTML/PDF consolidado de histórico com apenas as visitas selecionadas pelo usuário.
    Suporta modo completo com valores ou modo sem preços.
    """
    v_info = vehicle_info or {}
    plate_disp = v_info.get("plate_display") or format_plate_display(v_info.get("plate", "")) or "SEM PLACA"
    client_name = v_info.get("client_name") or "Cliente não informado"
    car_model = v_info.get("car_model") or "Veículo"
    car_year = v_info.get("car_year") or "—"
    car_color = v_info.get("car_color") or "—"
    total_selected = len(visits)

    doc_title = f"Historico_{plate_disp.replace('-', '')}_MecatroniCar"
    price_mode_title = "SEM VALORES" if without_prices else "HISTÓRICO COMPLETO"

    visits_html = ""
    for idx, v in enumerate(visits, 1):
        v_num = v.get("visit_num") or "—"
        v_date = v.get("entry_date") or "Data não informada"
        v_km = _format_km(v.get("odometer"))
        v_complaint = v.get("complaint") or "Manutenção / Revisão"

        details = v.get("details") or {}
        items = details.get("items") or []
        pecas = details.get("pecas_items") or [it for it in items if it.get("section") != "Serviço"]
        servicos = details.get("servicos_items") or [it for it in items if it.get("section") == "Serviço"]
        total_pecas = details.get("total_pecas") or ""
        total_servicos = details.get("total_servicos") or ""
        total_geral = details.get("total_geral") or ""

        # Tabela de Peças
        pecas_rows = ""
        if pecas:
            for p in pecas:
                price_td = f'<td class="col-price">{_esc(p.get("total_price") or "-")}</td>' if not without_prices else ''
                pecas_rows += f"""
                <tr>
                    <td class="col-qty">{_esc(p.get('quantity') or '1')}</td>
                    <td class="col-desc">{_esc(p.get('description'))}</td>
                    {price_td}
                </tr>
                """
        else:
            colspan = "2" if without_prices else "3"
            pecas_rows = f'<tr><td colspan="{colspan}" class="empty-row">Nenhuma peça registrada nesta visita.</td></tr>'

        # Tabela de Serviços
        servicos_rows = ""
        if servicos:
            for s in servicos:
                price_td = f'<td class="col-price">{_esc(s.get("total_price") or "-")}</td>' if not without_prices else ''
                servicos_rows += f"""
                <tr>
                    <td class="col-qty">{_esc(s.get('quantity') or '1')}</td>
                    <td class="col-desc">{_esc(s.get('description'))}</td>
                    {price_td}
                </tr>
                """
        else:
            colspan = "2" if without_prices else "3"
            servicos_rows = f'<tr><td colspan="{colspan}" class="empty-row">Nenhum serviço registrado nesta visita.</td></tr>'

        price_th = '<th class="col-price">TOTAL</th>' if not without_prices else ''
        footer_totals = ""
        if not without_prices and (total_pecas or total_servicos or total_geral):
            footer_totals = f"""
            <div class="visit-card-totals">
                {f'<span>Peças: <strong>{_esc(total_pecas)}</strong></span>' if total_pecas else ''}
                {f'<span>Mão de Obra: <strong>{_esc(total_servicos)}</strong></span>' if total_servicos else ''}
                {f'<span class="total-highlight">Total Visita: <strong>{_esc(total_geral)}</strong></span>' if total_geral else ''}
            </div>
            """

        visits_html += f"""
        <div class="history-visit-card">
            <div class="history-visit-header">
                <div class="hvh-left">
                    <span class="badge-visit">VISITA #{_esc(v_num)}</span>
                    <span class="badge-date">📅 {_esc(v_date)}</span>
                    <span class="badge-km">⏱️ {_esc(v_km)}</span>
                </div>
                <div class="hvh-right">
                    <span class="badge-file">📄 {_esc(v.get('file_name', ''))}</span>
                </div>
            </div>

            <div class="history-complaint">
                <strong>Defeito / Queixa Relatada:</strong> {_esc(v_complaint)}
            </div>

            <div class="history-tables-grid">
                <div class="table-block">
                    <div class="table-subheading">🔩 Peças e Componentes ({len(pecas)})</div>
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th class="col-qty">QTD</th>
                                <th>DESCRIÇÃO</th>
                                {price_th}
                            </tr>
                        </thead>
                        <tbody>
                            {pecas_rows}
                        </tbody>
                    </table>
                </div>

                <div class="table-block">
                    <div class="table-subheading">🛠️ Mão de Obra e Serviços ({len(servicos)})</div>
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th class="col-qty">QTD</th>
                                <th>DESCRIÇÃO</th>
                                {price_th}
                            </tr>
                        </thead>
                        <tbody>
                            {servicos_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            {footer_totals}
        </div>
        """

    auto_print_script = "window.addEventListener('load', () => { setTimeout(() => window.print(), 350); });" if auto_print else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{_esc(doc_title)}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>
        @page {{
            size: A4 portrait;
            margin: 12mm 14mm;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f1f5f9;
            color: #0f172a;
            font-size: 13px;
            line-height: 1.4;
        }}
        .print-toolbar {{
            background: #111827;
            color: #ffffff;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #f9cc01;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            position: sticky;
            top: 0;
            z-index: 1000;
        }}
        .toolbar-title {{
            font-size: 15px;
            font-weight: 800;
        }}
        .toolbar-badge {{
            background: #f9cc01;
            color: #111827;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 800;
            margin-right: 8px;
        }}
        .btn-action {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            border: none;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: #f9cc01;
            color: #111827;
        }}
        .btn-primary:hover {{
            background: #e5b800;
        }}
        .sheet {{
            max-width: 900px;
            margin: 20px auto;
            background: #ffffff;
            padding: 24px 28px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.06);
            border-radius: 8px;
        }}
        .history-main-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2.5px solid #111827;
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        .brand-block {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .brand-logo {{
            width: 48px;
            height: 48px;
            object-fit: contain;
        }}
        .brand-title {{
            font-size: 18px;
            font-weight: 900;
            color: #111827;
            letter-spacing: -0.5px;
        }}
        .brand-sub {{
            font-size: 11px;
            color: #64748b;
            font-weight: 600;
        }}
        .car-summary-box {{
            text-align: right;
        }}
        .car-plate-title {{
            font-size: 20px;
            font-weight: 900;
            color: #0f172a;
            font-family: "Impact", "Arial Black", sans-serif;
            letter-spacing: 1px;
        }}
        .car-meta-line {{
            font-size: 12.5px;
            color: #475569;
            font-weight: 600;
            margin-top: 2px;
        }}
        .history-visit-card {{
            border: 1.5px solid #cbd5e1;
            border-radius: 6px;
            margin-bottom: 18px;
            overflow: hidden;
            page-break-inside: avoid;
        }}
        .history-visit-header {{
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .hvh-left {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .badge-visit {{
            background: #111827;
            color: #f9cc01;
            font-weight: 800;
            font-size: 11.5px;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .badge-date, .badge-km {{
            font-size: 12px;
            font-weight: 700;
            color: #334155;
        }}
        .badge-file {{
            font-size: 11px;
            color: #64748b;
            font-family: monospace;
        }}
        .history-complaint {{
            padding: 8px 14px;
            background: #ffffff;
            font-size: 12.5px;
            border-bottom: 1px dashed #e2e8f0;
            color: #1e293b;
        }}
        .history-tables-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            padding: 10px 14px;
        }}
        .table-subheading {{
            font-size: 11.5px;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
            text-transform: uppercase;
        }}
        .history-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11.5px;
        }}
        .history-table th {{
            background: #f1f5f9;
            padding: 5px 6px;
            text-align: left;
            font-weight: 700;
            color: #475569;
            border-bottom: 1px solid #cbd5e1;
        }}
        .history-table td {{
            padding: 5px 6px;
            border-bottom: 1px solid #f1f5f9;
        }}
        .col-qty {{
            width: 38px;
            text-align: center !important;
            font-weight: 700;
        }}
        .col-price {{
            width: 75px;
            text-align: right !important;
            font-weight: 700;
            font-family: monospace;
        }}
        .empty-row {{
            text-align: center;
            color: #94a3b8;
            font-style: italic;
            padding: 8px !important;
        }}
        .visit-card-totals {{
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
            padding: 8px 14px;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 20px;
            font-size: 12px;
            color: #334155;
        }}
        .total-highlight {{
            background: #fefce8;
            color: #854d0e;
            padding: 2px 8px;
            border: 1px solid #fde047;
            border-radius: 4px;
            font-weight: 800;
        }}
        @media print {{
            body {{
                background: #ffffff;
            }}
            .print-toolbar {{
                display: none !important;
            }}
            .sheet {{
                margin: 0;
                padding: 0;
                box-shadow: none;
                max-width: 100%;
            }}
            .history-visit-card {{
                border: 1px solid #94a3b8;
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div>
            <span class="toolbar-badge">Histórico</span>
            <span class="toolbar-title">{_esc(plate_disp)} — {_esc(car_model)} ({total_selected} visitas selecionadas • {price_mode_title})</span>
        </div>
        <div>
            <button class="btn-action btn-primary" onclick="window.print()">
                🖨️ Imprimir Histórico Selecionado
            </button>
        </div>
    </div>

    <div class="sheet">
        <div class="history-main-header">
            <div class="brand-block">
                <img src="/logo.png" alt="MecatroniCar" class="brand-logo">
                <div>
                    <div class="brand-title">MecatroniCar</div>
                    <div class="brand-sub">Serviços e Autopeças Ltda • CNPJ 05.961.672/0001-87</div>
                    <div class="brand-sub">Relatório Consolidado de Visitas • {price_mode_title}</div>
                </div>
            </div>
            <div class="car-summary-box">
                <div class="car-plate-title">{_esc(plate_disp)}</div>
                <div class="car-meta-line">{_esc(car_model)} ({_esc(car_color)} • {_esc(car_year)})</div>
                <div class="car-meta-line">👤 Cliente: <strong>{_esc(client_name)}</strong></div>
                <div class="car-meta-line">📋 Visitas selecionadas: <strong>{total_selected}</strong></div>
            </div>
        </div>

        {visits_html}
    </div>

    <script>
        {auto_print_script}
    </script>
</body>
</html>
"""
