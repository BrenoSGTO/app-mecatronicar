# -*- coding: utf-8 -*-
"""
MecatroniCar - Gerador de Documentos Profissionais (Orçamento/OS e Checklist de Vidro)
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


def render_orcamento_html(parsed_data, auto_print=False):
    """
    CP-05: Gera o HTML/PDF de alta qualidade para o Orçamento / Ordem de Serviço
    com a Identidade Visual Oficial da MecatroniCar (fundo branco econômico em toner).
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
        <div class="section-box notes-box">
            <div class="section-title-bar">
                <span>🔎 DIAGNÓSTICO TÉCNICO / LEITURA DE SCANNER / OBSERVAÇÕES</span>
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
            background: #e2e8f0;
            color: #0f172a;
            font-size: 12px;
            line-height: 1.4;
        }}
        /* Floating Action Bar (Screen Only) */
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
            background: #f9cc01;
            color: #111827;
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
            padding: 14mm 15mm;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
            border-radius: 4px;
        }}

        /* Brand Header */
        .doc-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #111827;
            padding-bottom: 12px;
            margin-bottom: 14px;
        }}
        .brand-left {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .brand-logo {{
            width: 68px;
            height: 68px;
            object-fit: contain;
        }}
        .brand-name {{
            font-size: 24px;
            font-weight: 900;
            letter-spacing: -0.5px;
            color: #111827;
            line-height: 1.05;
        }}
        .brand-legal {{
            font-size: 11px;
            font-weight: 700;
            color: #334155;
            margin-top: 2px;
        }}
        .brand-meta {{
            font-size: 10.5px;
            color: #475569;
            margin-top: 2px;
        }}
        .os-box {{
            text-align: right;
            background: #f8fafc;
            border: 2px solid #111827;
            border-left: 6px solid #f9cc01;
            border-radius: 6px;
            padding: 8px 14px;
            min-width: 195px;
        }}
        .os-doc-type {{
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: #475569;
        }}
        .os-number {{
            font-size: 18px;
            font-weight: 900;
            color: #111827;
            margin: 2px 0;
        }}
        .os-dates {{
            font-size: 10.5px;
            color: #334155;
            font-weight: 600;
        }}

        /* Info Grid (Client & Vehicle) */
        .info-grid {{
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .section-box {{
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 12px;
        }}
        .info-grid .section-box {{
            margin-bottom: 0;
        }}
        .section-title-bar {{
            background: #111827;
            color: #ffffff;
            font-size: 10.5px;
            font-weight: 800;
            letter-spacing: 0.5px;
            padding: 5px 10px;
            border-bottom: 2px solid #f9cc01;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .section-content {{
            padding: 8px 10px;
        }}
        .field-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px 14px;
            margin-bottom: 4px;
            font-size: 11.5px;
        }}
        .field-row:last-child {{
            margin-bottom: 0;
        }}
        .field-label {{
            font-weight: 700;
            color: #475569;
        }}
        .field-value {{
            font-weight: 600;
            color: #0f172a;
        }}
        .plate-highlight {{
            display: inline-block;
            background: #f9cc01;
            color: #111827;
            font-family: "Consolas", "Courier New", monospace;
            font-weight: 900;
            font-size: 13px;
            padding: 1px 7px;
            border-radius: 4px;
            border: 1px solid #111827;
            letter-spacing: 0.8px;
        }}

        /* Complaint Banner */
        .complaint-banner {{
            background: #fefce8;
            border: 1px solid #fde047;
            border-left: 5px solid #f9cc01;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 12px;
            font-size: 12px;
        }}
        .complaint-label {{
            font-weight: 800;
            color: #111827;
            text-transform: uppercase;
            font-size: 10.5px;
            margin-bottom: 2px;
        }}
        .complaint-val {{
            font-weight: 600;
            color: #0f172a;
        }}

        /* Tables */
        table.doc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11.5px;
        }}
        table.doc-table th {{
            background: #f1f5f9;
            color: #1e293b;
            font-weight: 800;
            text-transform: uppercase;
            font-size: 10px;
            padding: 6px 8px;
            border-bottom: 1px solid #cbd5e1;
            text-align: left;
        }}
        table.doc-table td {{
            padding: 6px 8px;
            border-bottom: 1px solid #e2e8f0;
            color: #0f172a;
        }}
        table.doc-table tr:last-child td {{
            border-bottom: none;
        }}
        .col-idx {{
            width: 34px;
            text-align: center;
            color: #64748b;
            font-weight: 600;
        }}
        .col-desc {{
            font-weight: 600;
        }}
        .col-qty {{
            width: 55px;
            text-align: center;
            font-weight: 700;
        }}
        .col-unit {{
            width: 95px;
            text-align: right;
        }}
        .col-total {{
            width: 100px;
            text-align: right;
            font-weight: 700;
        }}
        .empty-row {{
            text-align: center;
            color: #64748b;
            font-style: italic;
            padding: 10px !important;
        }}
        .section-subtotal-bar {{
            background: #f8fafc;
            border-top: 1px solid #cbd5e1;
            padding: 6px 10px;
            text-align: right;
            font-size: 11.5px;
            font-weight: 700;
            color: #1e293b;
        }}

        /* Scanner / Technical Notes */
        .scanner-pre {{
            font-family: "Consolas", "Courier New", monospace;
            font-size: 10.5px;
            white-space: pre-wrap;
            padding: 8px 10px;
            background: #f8fafc;
            color: #1e293b;
            max-height: 220px;
            overflow: hidden;
        }}

        /* Financial Summary & Signatures */
        .bottom-grid {{
            display: grid;
            grid-template-columns: 1fr 260px;
            gap: 14px;
            margin-top: 12px;
            align-items: stretch;
        }}
        .terms-box {{
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            font-size: 10.5px;
            color: #334155;
        }}
        .signature-area {{
            margin-top: 26px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
            text-align: center;
        }}
        .sig-line {{
            border-top: 1px solid #0f172a;
            padding-top: 4px;
            font-weight: 700;
            font-size: 10.5px;
            color: #0f172a;
        }}
        .totals-card {{
            border: 2px solid #111827;
            border-radius: 6px;
            overflow: hidden;
        }}
        .totals-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 11.5px;
        }}
        .totals-row.final {{
            background: #f9cc01;
            color: #111827;
            font-size: 14px;
            font-weight: 900;
            border-bottom: none;
            padding: 8px 12px;
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
            .scanner-pre {{
                max-height: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div class="toolbar-left">
            <span class="toolbar-badge">CP-05 • Orçamento / OS Oficial</span>
            <span class="toolbar-title">{_esc(plate_disp)} — {_esc(client_name)} ({_esc(car_model)})</span>
        </div>
        <div class="toolbar-actions">
            <a class="btn-action btn-secondary" href="/api/checklist_pdf?file_path={html.escape(d.get('file_path', ''), quote=True)}">
                📋 Mudar para Checklist de Vidro (Sem Valores)
            </a>
            <button class="btn-action btn-primary" onclick="window.print()">
                🖨️ Imprimir / Salvar como PDF
            </button>
        </div>
    </div>

    <div class="sheet">
        <!-- Header -->
        <header class="doc-header">
            <div class="brand-left">
                <img src="/logo.png" alt="MecatroniCar" class="brand-logo">
                <div>
                    <div class="brand-name">MecatroniCar</div>
                    <div class="brand-legal">Mecatroni Car - Serviços e Autopeças Ltda • CNPJ: 05.961.672/0001-87</div>
                    <div class="brand-meta">Manutenção e Reparação Mecânica Automotiva &amp; Autopeças • Santos/SP</div>
                </div>
            </div>
            <div class="os-box">
                <div class="os-doc-type">Ordem de Serviço / Orçamento</div>
                <div class="os-number">VISITA Nº {_esc(visit_num)}</div>
                <div class="os-dates">
                    Entrada: {_esc(entry_date)} {_esc(entry_time)}<br>
                    {f'Saída: {_esc(exit_date)} {_esc(exit_time)}' if exit_date and exit_date != '—' else f'Hodômetro: {_esc(odometer)}'}
                </div>
            </div>
        </header>

        <!-- Client & Vehicle Info -->
        <div class="info-grid">
            <div class="section-box">
                <div class="section-title-bar">
                    <span>👤 DADOS DO CLIENTE</span>
                </div>
                <div class="section-content">
                    <div class="field-row">
                        <div><span class="field-label">Cliente:</span> <span class="field-value">{_esc(client_name)}</span></div>
                    </div>
                    <div class="field-row">
                        <div><span class="field-label">CPF/CNPJ:</span> <span class="field-value">{_esc(cpf)}</span></div>
                        {f'<div><span class="field-label">RG:</span> <span class="field-value">{_esc(rg)}</span></div>' if rg else ''}
                        <div><span class="field-label">Telefone/Celular:</span> <span class="field-value">{_esc(phone)}</span></div>
                    </div>
                    <div class="field-row">
                        <div><span class="field-label">Endereço:</span> <span class="field-value">{_esc(full_address)}</span></div>
                    </div>
                    {f'<div class="field-row"><div><span class="field-label">E-mail:</span> <span class="field-value">{_esc(email)}</span></div></div>' if email else ''}
                </div>
            </div>

            <div class="section-box">
                <div class="section-title-bar">
                    <span>🚗 DADOS DO VEÍCULO</span>
                </div>
                <div class="section-content">
                    <div class="field-row" style="align-items: center;">
                        <div><span class="field-label">Placa:</span> <span class="plate-highlight">{_esc(plate_disp)}</span></div>
                        <div><span class="field-label">Hodômetro:</span> <span class="field-value">{_esc(odometer)}</span></div>
                    </div>
                    <div class="field-row">
                        <div><span class="field-label">Veículo:</span> <span class="field-value">{_esc(car_full)}</span></div>
                        <div><span class="field-label">Ano:</span> <span class="field-value">{_esc(car_year)}</span></div>
                    </div>
                    <div class="field-row">
                        <div><span class="field-label">Cor:</span> <span class="field-value">{_esc(car_color)}</span></div>
                        <div><span class="field-label">Combustível:</span> <span class="field-value">{_esc(car_fuel)}</span></div>
                    </div>
                    {f'<div class="field-row"><div><span class="field-label">Chassi:</span> <span class="field-value">{_esc(car_chassis)}</span></div></div>' if car_chassis and car_chassis != '—' else ''}
                </div>
            </div>
        </div>

        <!-- Complaint / Symptom -->
        <div class="complaint-banner">
            <div class="complaint-label">⚠️ Solicitação do Cliente / Sintoma Relatado</div>
            <div class="complaint-val">{_esc(complaint)}</div>
        </div>

        <!-- Parts Section -->
        <div class="section-box">
            <div class="section-title-bar">
                <span>🔩 PEÇAS E INSUMOS AUTOMOTIVOS ({len(pecas)})</span>
                <span>CNAE 4530-7/03</span>
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
            <div class="section-subtotal-bar">
                Subtotal de Peças: {_esc(total_pecas)}
            </div>
        </div>

        <!-- Services Section -->
        <div class="section-box">
            <div class="section-title-bar">
                <span>🛠️ SERVIÇOS EXECUTADOS / MÃO DE OBRA ({len(servicos)})</span>
                <span>Item 14.01 • Mecânica Automotiva</span>
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
            <div class="section-subtotal-bar">
                Subtotal de Mão de Obra / Serviços: {_esc(total_servicos)}
            </div>
        </div>

        {scanner_block_html}

        <!-- Totals & Signatures -->
        <div class="bottom-grid">
            <div class="terms-box">
                <div>
                    <strong>Condições e Garantia:</strong><br>
                    • Forma de Pagamento: <strong>{_esc(payment_method)}</strong><br>
                    • Serviços e peças contam com garantia legal de 90 dias conforme o Código de Defesa do Consumidor, respeitadas as recomendações técnicas de uso e manutenção.
                </div>
                <div class="signature-area">
                    <div class="sig-line">MecatroniCar — Responsável Técnico</div>
                    <div class="sig-line">{_esc(client_name)} — Cliente</div>
                </div>
            </div>

            <div class="totals-card">
                <div class="section-title-bar">
                    <span>💰 RESUMO FINANCEIRO</span>
                </div>
                <div class="totals-row">
                    <span>Total de Peças:</span>
                    <strong>{_esc(total_pecas)}</strong>
                </div>
                <div class="totals-row">
                    <span>Total de Serviços:</span>
                    <strong>{_esc(total_servicos)}</strong>
                </div>
                <div class="totals-row">
                    <span>SubTotal:</span>
                    <strong>{_esc(subtotal)}</strong>
                </div>
                {f'<div class="totals-row"><span>Desconto Concedido:</span><strong>- {_esc(discount)}</strong></div>' if discount and discount != 'R$ 0,00' else ''}
                <div class="totals-row final">
                    <span>TOTAL GERAL:</span>
                    <span>{_esc(total)}</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        {auto_print_script}
    </script>
</body>
</html>
"""


def render_checklist_html(parsed_data, auto_print=False):
    """
    CP-04: Gera o HTML/PDF de Checklist Operacional para deixar no para-brisa do veículo.
    NÃO exibe nenhum valor monetário (apenas descrições, quantidades e checkboxes de execução).
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

    pecas = d.get("pecas_items") or []
    servicos = d.get("servicos_items") or []

    doc_title = f"Checklist_Vidro_{plate_disp.replace('-', '')}_Visita_{visit_num}_MecatroniCar"

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
            <td colspan="4" class="empty-row">Nenhuma peça registrada até o momento.</td>
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
            <td colspan="4" class="empty-row">Ver itens descritos acima ou aguardar definição de serviços.</td>
        </tr>
        """

    scanner_block_html = ""
    if complaint_comment:
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

        /* Top Banner Designed for Windshield Visibility */
        .windshield-header {{
            display: flex;
            justify-content: space-between;
            align-items: stretch;
            border: 3px solid #111827;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 12px;
        }}
        .ws-brand-col {{
            background: #111827;
            color: #ffffff;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-right: 4px solid #f9cc01;
        }}
        .ws-logo {{
            width: 52px;
            height: 52px;
            object-fit: contain;
        }}
        .ws-title {{
            font-size: 18px;
            font-weight: 900;
            color: #f9cc01;
            text-transform: uppercase;
            line-height: 1.1;
        }}
        .ws-subtitle {{
            font-size: 11px;
            color: #e2e8f0;
            font-weight: 600;
            margin-top: 2px;
        }}
        .ws-car-col {{
            flex: 1;
            padding: 8px 14px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: #f8fafc;
        }}
        .ws-car-model {{
            font-size: 18px;
            font-weight: 900;
            color: #0f172a;
        }}
        .ws-car-meta {{
            font-size: 12px;
            font-weight: 700;
            color: #334155;
            margin-top: 3px;
        }}
        .ws-plate-col {{
            background: #f9cc01;
            color: #111827;
            padding: 8px 18px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border-left: 3px solid #111827;
            min-width: 175px;
        }}
        .ws-plate-label {{
            font-size: 10px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .ws-plate-num {{
            font-family: "Consolas", "Courier New", monospace;
            font-size: 26px;
            font-weight: 900;
            letter-spacing: 1px;
            line-height: 1.1;
        }}
        .ws-visit-badge {{
            font-size: 11px;
            font-weight: 800;
            margin-top: 2px;
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

        /* Mechanic Handwritten Notes & Final Inspection */
        .mechanic-notes-box {{
            border: 2px solid #111827;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 12px;
        }}
        .mechanic-notes-title {{
            font-size: 11.5px;
            font-weight: 900;
            text-transform: uppercase;
            margin-bottom: 8px;
            color: #0f172a;
        }}
        .ruled-line {{
            border-bottom: 1px dashed #94a3b8;
            height: 24px;
        }}
        .inspection-footer {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
            border: 2px solid #111827;
            border-radius: 6px;
            padding: 10px 12px;
            background: #f8fafc;
            font-size: 11.5px;
            font-weight: 700;
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
            <span class="toolbar-badge">CP-04 • Checklist de Vidro (Sem Valores)</span>
            <span class="toolbar-title">{_esc(plate_disp)} — {_esc(car_full)} ({_esc(client_name)})</span>
        </div>
        <div class="toolbar-actions">
            <a class="btn-action btn-secondary" href="/api/orcamento_pdf?file_path={html.escape(d.get('file_path', ''), quote=True)}">
                📄 Mudar para Orçamento Completo (Com Valores)
            </a>
            <button class="btn-action btn-primary" onclick="window.print()">
                🖨️ Imprimir Checklist p/ Para-brisa
            </button>
        </div>
    </div>

    <div class="sheet">
        <!-- Top Windshield Identification Banner -->
        <div class="windshield-header">
            <div class="ws-brand-col">
                <img src="/logo.png" alt="MecatroniCar" class="ws-logo">
                <div>
                    <div class="ws-title">CHECKLIST DE PARA-BRISA</div>
                    <div class="ws-subtitle">MecatroniCar • FOLHA DE CHÃO DE OFICINA</div>
                </div>
            </div>
            <div class="ws-car-col">
                <div class="ws-car-model">{_esc(car_full)} ({_esc(car_color)} • {_esc(car_year)})</div>
                <div class="ws-car-meta">
                    👤 Cliente: {_esc(client_name)} &nbsp;|&nbsp; ⏱️ KM: {_esc(odometer)} &nbsp;|&nbsp; 📅 Entrada: {_esc(entry_date)} {_esc(entry_time)}
                </div>
            </div>
            <div class="ws-plate-col">
                <span class="ws-plate-label">PLACA DO VEÍCULO</span>
                <span class="ws-plate-num">{_esc(plate_disp)}</span>
                <span class="ws-visit-badge">Visita #{_esc(visit_num)}</span>
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

        <!-- Handwritten Mechanic Observations -->
        <div class="mechanic-notes-box">
            <div class="mechanic-notes-title">📝 ANOTAÇÕES DO MECÂNICO / PEÇAS ADICIONAIS IDENTIFICADAS NA DESMONTAGEM:</div>
            <div class="ruled-line"></div>
            <div class="ruled-line"></div>
            <div class="ruled-line"></div>
        </div>

        <!-- Final Quality Check Footer -->
        <div class="inspection-footer">
            <div>🔧 Mecânico Responsável:<br><br>_______________________________</div>
            <div>
                ✅ Conferência Final:<br>
                [ &nbsp; ] Nível de Óleo / Fluidos<br>
                [ &nbsp; ] Reaperto de Rodas / Torque<br>
                [ &nbsp; ] Peças Substituídas Guardadas
            </div>
            <div>
                🚗 Teste de Rodagem / Liberação:<br>
                [ &nbsp; ] Aprovado sem Anomalias<br><br>
                Data/Hora: ____/____ às ____:____
            </div>
        </div>
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


def generate_checklist_from_file(filepath, auto_print=False):
    parsed = parse_file(filepath)
    return render_checklist_html(parsed, auto_print=auto_print)
