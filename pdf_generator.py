# -*- coding: utf-8 -*-
"""
MecatroniCar - Gerador de documentos impressos (Orçamento/OS, Checklist e Histórico).

Abordagem: cada documento é uma página HTML otimizada para impressão em A4.
O app abre a página numa janela e o usuário usa "Imprimir / Salvar como PDF" do
navegador (Edge/Chrome). Nada de biblioteca de PDF: funciona offline e sem
dependências novas. O <title> da página vira o nome do arquivo sugerido
(ex.: Orcamento_ABC1D23_MecatroniCar.pdf).

Identidade visual (docs/REPAGINACAO_V3.md, seção 3): fundo branco, preto e cinzas
para economizar toner, amarelo #F9CC01 apenas como fio/acento fino.
Numeração de páginas ("Página X de Y") usa caixas de margem do @page (Chromium 131+).
"""
import re
import html
from urllib.parse import quote
import base64
import datetime
import os

from parser import format_plate_display, parse_file, parse_currency_float


# ---------------------------------------------------------------------------
# Dados da empresa
# ---------------------------------------------------------------------------
EMPRESA_MARCA = "MecatroniCar"
EMPRESA_RAZAO_SOCIAL = "Mecatroni Car - Serviços e Autopeças Ltda"
EMPRESA_CNPJ = "05.961.672/0001-87"
EMPRESA_ATIVIDADE = "Mecânica automotiva e autopeças"
EMPRESA_CIDADE = "Santos/SP"
# Endereço e telefone não estão cadastrados em nenhum lugar do projeto. Para que
# apareçam no cabeçalho, preencha as chaves "empresa_endereco" e "empresa_telefone"
# no config.json (ou as constantes abaixo). Se vazios, são simplesmente omitidos.
EMPRESA_ENDERECO = ""
EMPRESA_TELEFONE = ""

GARANTIA_TERMOS = (
    "Serviços e peças contam com garantia legal de 90 dias, conforme o Código de Defesa "
    "do Consumidor (Art. 26, II, Lei nº 8.078/90), respeitadas as condições de uso e as "
    "especificações do fabricante."
)

ESCANER_TITULO = "Observações e laudo técnico"


def _empresa_contato():
    """Endereço/telefone configuráveis (config.json ou constantes deste arquivo)."""
    endereco, telefone = EMPRESA_ENDERECO, EMPRESA_TELEFONE
    try:
        import config
        cfg = config.load_config()
        endereco = str(cfg.get("empresa_endereco") or endereco or "").strip()
        telefone = str(cfg.get("empresa_telefone") or telefone or "").strip()
    except Exception:
        pass
    return endereco, telefone


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
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
            s += f" ({compl})"
        parts.append(s)
    loc_parts = [p for p in (d.get("neighborhood", ""), d.get("city", "")) if p]
    if loc_parts:
        parts.append(" - ".join(loc_parts))
    if d.get("cep", ""):
        parts.append(f"CEP {d['cep']}")
    return " · ".join(parts)


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


def _fmt_brl(value):
    """float -> 'R$ 1.234,56'."""
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}" if value >= 0 else f"- R$ {s}"


def _money(val, empty="—"):
    s = str(val).strip() if val is not None else ""
    return s if s else empty


def _is_zero_money(val):
    s = str(val or "").strip()
    return (not s) or parse_currency_float(s) == 0.0


def _sum_items(items):
    total = 0.0
    for it in items:
        total += parse_currency_float(it.get("total_price"))
    return total


_LOGO_CACHE = {}


def _get_logo_data_uri():
    if "uri" in _LOGO_CACHE:
        return _LOGO_CACHE["uri"]
    uri = "/logo.png"
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "static", "logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        pass
    _LOGO_CACHE["uri"] = uri
    return uri


def _plate_clean(plate):
    return re.sub(r"[^A-Za-z0-9]", "", str(plate or "")).upper()


def _file_stem(prefix, plate):
    """Nome de arquivo padrão: Orcamento_ABC1D23_MecatroniCar."""
    clean = _plate_clean(plate) or "SemPlaca"
    return f"{prefix}_{clean}_MecatroniCar"


def _css_string(text):
    """Escapa texto para uso em content: "..." de caixas de margem do @page."""
    s = str(text or "").replace("\\", "\\\\").replace('"', '\\"')
    s = re.sub(r"[\r\n]+", " ", s)
    # Dentro de <style>: impede que dados do cliente fechem a tag (</style>) e injetem HTML.
    return s.replace("<", "\\3C ").replace(">", "\\3E ").replace("&", "\\26 ")


def _plate_html(plate_disp, size="md"):
    """Placa (Mercosul com faixa azul; modelo antigo sem faixa). Tamanho via classe plate--sm/md/xl."""
    clean = _plate_clean(plate_disp)
    old = bool(re.fullmatch(r"[A-Z]{3}\d{4}", clean))
    if len(clean) == 7 and old:
        text = f"{clean[:3]}-{clean[3:]}"
    elif clean:
        text = clean
    else:
        text = "SEM PLACA"
    cls = f"plate-mercosul plate--{size}" + (" plate--old" if old else "")
    band = "" if old else '<div class="plate-band"><span>BRASIL</span></div>'
    return f'<div class="{cls}">{band}<div class="plate-text">{_esc(text)}</div></div>'


def _norm_items(items):
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append(it)
    return out


def _desc(it):
    return _esc(it.get("description")) or "(sem descrição)"


def _auto_print_script(auto_print):
    if not auto_print:
        return ""
    return "<script>window.addEventListener('load', function () { setTimeout(function () { window.print(); }, 350); });</script>"


# ---------------------------------------------------------------------------
# CSS compartilhado
# ---------------------------------------------------------------------------
def _base_css(margin_box_left, margin_box_right_prefix="Página"):
    """Base visual + @page com rodapé 'Página X de Y'. Mensagens do rodapé vêm já como texto."""
    left = _css_string(margin_box_left)
    css = """
        :root {
            --ink: #111827;
            --ink-2: #374151;
            --muted: #6b7280;
            --line: #d1d5db;
            --line-soft: #e5e7eb;
            --soft: #f3f4f6;
            --accent: #F9CC01;
        }
        @page {
            size: A4 portrait;
            margin: 14mm 14mm 17mm 14mm;
            @top-left {
                content: "__LEFT__";
                font: 600 7.5pt "Segoe UI", system-ui, sans-serif;
                color: #6b7280;
                vertical-align: bottom;
                padding-bottom: 3mm;
            }
            @bottom-left {
                content: "__RAZAO__ · CNPJ __CNPJ__";
                font: 7.5pt "Segoe UI", system-ui, sans-serif;
                color: #6b7280;
                vertical-align: top;
                padding-top: 4mm;
            }
            @bottom-right {
                content: "__PG__ " counter(page) " de " counter(pages);
                font: 600 7.5pt "Segoe UI", system-ui, sans-serif;
                color: #374151;
                vertical-align: top;
                padding-top: 4mm;
            }
        }
        @page :first {
            @top-left { content: none; }
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
        html { background: #e5e7eb; }
        body {
            font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
            font-size: 9.5pt;
            line-height: 1.4;
            color: var(--ink);
            font-variant-numeric: tabular-nums;
            background: #e5e7eb;
        }

        /* Barra de ações (só na tela) */
        .toolbar {
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 10px 24px;
            background: #111827;
            border-bottom: 2px solid var(--accent);
            color: #f9fafb;
            font-size: 13px;
        }
        .toolbar-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
        .toolbar-tag {
            flex: none;
            padding: 3px 8px;
            border: 1px solid #4b5563;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: .06em;
            text-transform: uppercase;
            color: #e5e7eb;
        }
        .toolbar-title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .toolbar-actions { display: flex; gap: 8px; flex: none; }
        .btn {
            display: inline-flex;
            align-items: center;
            padding: 7px 14px;
            border-radius: 6px;
            border: 1px solid #4b5563;
            background: transparent;
            color: #f9fafb;
            font: 600 13px "Segoe UI", system-ui, sans-serif;
            text-decoration: none;
            cursor: pointer;
        }
        .btn:hover { background: #1f2937; }
        .btn-primary { background: var(--accent); border-color: var(--accent); color: #111827; }
        .btn-primary:hover { background: #e6bb00; }

        /* Folha A4 (tela). Na impressão a folha vira só o conteúdo. */
        .sheet {
            width: 210mm;
            max-width: 100%;
            margin: 20px auto;
            padding: 14mm;
            background: #fff;
            box-shadow: 0 1px 3px rgba(17, 24, 39, .12), 0 8px 24px rgba(17, 24, 39, .06);
        }

        /* Cabeçalho institucional */
        .doc-header {
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8mm;
            padding-bottom: 4mm;
            margin-bottom: 5mm;
            border-bottom: .3mm solid var(--ink);
        }
        .doc-header::after {
            content: "";
            position: absolute;
            left: 0;
            bottom: -.65mm;
            width: 26mm;
            height: 1mm;
            background: var(--accent);
        }
        .brand { display: flex; align-items: center; gap: 4mm; min-width: 0; }
        .brand img { width: 17mm; height: 17mm; object-fit: contain; flex: none; }
        .brand-name { font-size: 16pt; font-weight: 700; letter-spacing: -.01em; line-height: 1.1; }
        .brand-legal { margin-top: 1mm; font-size: 8.5pt; font-weight: 600; color: var(--ink-2); }
        .brand-meta { font-size: 8pt; color: var(--muted); line-height: 1.35; }
        .brand-meta + .brand-meta { margin-top: .2mm; }
        .doc-id { text-align: right; flex: none; }
        .doc-kind { font-size: 7.5pt; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .doc-number { font-size: 21pt; font-weight: 700; line-height: 1.1; letter-spacing: -.02em; margin: .8mm 0 1.2mm; }
        .doc-dates { font-size: 8.5pt; color: var(--ink-2); line-height: 1.45; }
        .doc-dates b { font-weight: 600; color: var(--ink); }

        /* Títulos de seção e rótulos */
        .section { margin-bottom: 5mm; }
        .section-title {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding-bottom: 1mm;
            margin-bottom: 2mm;
            border-bottom: .25mm solid var(--ink);
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: var(--ink);
        }
        .section-title small { font-size: 8pt; font-weight: 500; letter-spacing: 0; text-transform: none; color: var(--muted); }

        /* Placa */
        .plate-mercosul {
            display: inline-flex;
            flex-direction: column;
            width: 20em;
            height: 6.6em;
            background: #fff;
            border: .22em solid #111;
            border-radius: .7em;
            overflow: hidden;
            vertical-align: middle;
        }
        .plate-band {
            flex: none;
            height: 1.5em;
            background: #003399;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font: 700 .85em "Segoe UI", Arial, sans-serif;
            letter-spacing: .32em;
            line-height: 1;
        }
        .plate-text {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Bahnschrift, "Arial Narrow", "Segoe UI", Arial, sans-serif;
            font-weight: 700;
            font-size: 3.6em;
            letter-spacing: .06em;
            line-height: 1;
            white-space: nowrap;
            color: #000;
        }
        .plate--old .plate-text { font-size: 3.1em; }
        .plate--sm { font-size: 1.55mm; }
        .plate--md { font-size: 2.1mm; }
        .plate--xl { font-size: 5.3mm; }

        /* Tabelas */
        table.items { width: 100%; border-collapse: collapse; margin-bottom: 5mm; }
        table.items thead { display: table-header-group; }
        table.items tr { break-inside: avoid; page-break-inside: avoid; }
        table.items tbody.keep { break-inside: avoid; page-break-inside: avoid; }
        table.items th, table.items td { text-align: left; vertical-align: top; }
        table.items tr.sec th {
            padding: 1mm 0 1.2mm;
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: var(--ink);
        }
        table.items tr.sec th small { float: right; font-size: 8pt; font-weight: 500; letter-spacing: 0; text-transform: none; color: var(--muted); }
        table.items tr.cols th {
            padding: 1.2mm 2mm;
            font-size: 7pt;
            font-weight: 600;
            letter-spacing: .08em;
            text-transform: uppercase;
            color: var(--muted);
            border-top: .25mm solid var(--ink);
            border-bottom: .25mm solid var(--line);
            background: var(--soft);
        }
        table.items td { padding: 1.7mm 2mm; border-bottom: .2mm solid var(--line-soft); font-size: 9pt; }
        table.items td.desc, table.items th.desc { overflow-wrap: anywhere; word-break: break-word; }
        table.items .idx { width: 9mm; color: var(--muted); }
        table.items .qty { width: 14mm; text-align: center; }
        table.items .num { text-align: right; white-space: nowrap; }
        table.items .unit { width: 27mm; }
        table.items .tot { width: 29mm; font-weight: 600; }
        table.items td.empty { padding: 3mm 2mm; color: var(--muted); font-style: italic; }
        table.items tr.subtotal td {
            padding: 1.8mm 2mm 0;
            border-bottom: 0;
            font-size: 9pt;
            color: var(--ink-2);
            text-align: right;
        }
        table.items tr.subtotal td b { margin-left: 4mm; color: var(--ink); font-size: 10pt; }

        /* Texto pré-formatado (laudo / scanner) */
        pre.report {
            font-family: Consolas, "Courier New", monospace;
            font-size: 8pt;
            line-height: 1.4;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            padding: 2.5mm 3.5mm;
            background: #f9fafb;
            border-left: .6mm solid #9ca3af;
            color: var(--ink-2);
        }

        .keep { break-inside: avoid; page-break-inside: avoid; }

        @media print {
            html, body { background: #fff; }
            .toolbar { display: none !important; }
            .sheet { width: auto; margin: 0; padding: 0; box-shadow: none; }
        }
"""
    return (css.replace("__LEFT__", left)
               .replace("__RAZAO__", _css_string(EMPRESA_RAZAO_SOCIAL))
               .replace("__CNPJ__", EMPRESA_CNPJ)
               .replace("__PG__", _css_string(margin_box_right_prefix)))


def _toolbar(tag, title, secondary=None, primary="Imprimir / Salvar como PDF"):
    sec = ""
    if secondary:
        href, label = secondary
        sec = f'<a class="btn" href="{html.escape(href, quote=True)}">{_esc(label)}</a>'
    return f"""
    <div class="toolbar">
        <div class="toolbar-left">
            <span class="toolbar-tag">{_esc(tag)}</span>
            <span class="toolbar-title">{_esc(title)}</span>
        </div>
        <div class="toolbar-actions">
            {sec}
            <button class="btn btn-primary" onclick="window.print()">{_esc(primary)}</button>
        </div>
    </div>"""


def _brand_block(compact=False):
    endereco, telefone = _empresa_contato()
    meta = [EMPRESA_CIDADE]
    if endereco:
        meta.insert(0, endereco)
    contato = f"{_esc(' · '.join(meta))}"
    if telefone:
        contato += f" · Tel. {_esc(telefone)}"
    return f"""
            <div class="brand">
                <img src="{_get_logo_data_uri()}" alt="{EMPRESA_MARCA}">
                <div>
                    <div class="brand-name">{EMPRESA_MARCA}</div>
                    <div class="brand-legal">{_esc(EMPRESA_RAZAO_SOCIAL)}</div>
                    <div class="brand-meta">CNPJ {EMPRESA_CNPJ}{'' if compact else ' · ' + _esc(EMPRESA_ATIVIDADE)}</div>
                    {'' if compact else '<div class="brand-meta">' + contato + '</div>'}
                </div>
            </div>"""


def _hoje():
    return datetime.datetime.now().strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Orçamento / Ordem de Serviço
# ---------------------------------------------------------------------------
def _orcamento_rows(items, empty_text):
    """Devolve (linhas_do_tbody_principal, linhas_do_tbody_final) já em HTML.
    A última linha vai junto do subtotal num tbody que não quebra (evita subtotal órfão)."""
    if not items:
        return f'<tr><td colspan="5" class="empty">{_esc(empty_text)}</td></tr>', ""

    def row(idx, it):
        return (
            "<tr>"
            f'<td class="idx">{idx:02d}</td>'
            f'<td class="desc">{_desc(it)}</td>'
            f'<td class="qty">{_esc(it.get("quantity") or "1")}</td>'
            f'<td class="num unit">{_esc(_money(it.get("unit_price")))}</td>'
            f'<td class="num tot">{_esc(_money(it.get("total_price")))}</td>'
            "</tr>"
        )

    rows = [row(i, it) for i, it in enumerate(items, 1)]
    return "".join(rows[:-1]), rows[-1]


def _orcamento_table(title, desc_header, items, empty_text, subtotal_label, subtotal):
    count = f"{len(items)} {'item' if len(items) == 1 else 'itens'}"
    main_rows, last_row = _orcamento_rows(items, empty_text)
    return f"""
        <table class="items">
            <thead>
                <tr class="sec"><th colspan="5">{_esc(title)}<small>{count}</small></th></tr>
                <tr class="cols">
                    <th class="idx">Nº</th>
                    <th class="desc">{_esc(desc_header)}</th>
                    <th class="qty">Qtd.</th>
                    <th class="num unit">Valor unit.</th>
                    <th class="num tot">Total</th>
                </tr>
            </thead>
            <tbody>{main_rows}</tbody>
            <tbody class="keep">{last_row}
                <tr class="subtotal"><td colspan="5">{_esc(subtotal_label)}<b>{_esc(subtotal)}</b></td></tr>
            </tbody>
        </table>"""


def _orcamento_css():
    return """
        .parties { display: grid; grid-template-columns: 1.15fr 1fr; gap: 8mm; margin-bottom: 4.5mm; }
        dl.kv { display: grid; grid-template-columns: 22mm 1fr; column-gap: 2mm; row-gap: 1.1mm; font-size: 9pt; }
        dl.kv dt { color: var(--muted); font-size: 8pt; padding-top: .3mm; }
        dl.kv dd { min-width: 0; overflow-wrap: anywhere; }
        dl.kv dd.strong { font-weight: 600; }
        .callout {
            margin-bottom: 5mm;
            padding: 2mm 3.5mm 2.2mm;
            border-left: 1.1mm solid var(--accent);
            background: #fafafa;
        }
        .callout-label { font-size: 7.5pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .callout-text { margin-top: .5mm; font-size: 11pt; font-weight: 600; overflow-wrap: anywhere; }
        .callout-extra { margin-top: .8mm; font-size: 9pt; color: var(--ink-2); overflow-wrap: anywhere; }
        .summary { display: grid; grid-template-columns: 1fr 78mm; gap: 10mm; margin-bottom: 5mm; align-items: start; }
        .pay-label { font-size: 7.5pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .pay-value { margin-top: .6mm; font-size: 10.5pt; font-weight: 600; overflow-wrap: anywhere; }
        table.totals { width: 100%; border-collapse: collapse; }
        table.totals td { padding: 1.1mm 0; font-size: 9.5pt; color: var(--ink-2); }
        table.totals td.v { text-align: right; white-space: nowrap; color: var(--ink); font-weight: 600; }
        table.totals tr.total td {
            padding: 2.4mm 2.5mm;
            background: var(--soft);
            border-top: .5mm solid var(--ink);
            border-bottom: .5mm solid var(--ink);
            font-size: 14pt;
            font-weight: 700;
            color: var(--ink);
            letter-spacing: -.01em;
        }
        table.totals tr.total td:first-child { font-size: 9pt; letter-spacing: .1em; text-transform: uppercase; }
        .terms p { font-size: 8.5pt; color: var(--ink-2); line-height: 1.5; }
        .signatures { display: grid; grid-template-columns: 1fr 1fr; gap: 14mm; margin-top: 14mm; }
        .sig { border-top: .25mm solid var(--ink); padding-top: 1.2mm; font-size: 8.5pt; color: var(--ink-2); }
        .sig b { display: block; color: var(--ink); font-weight: 600; }
        .sig-date { margin: 5mm 0 6mm; font-size: 8.5pt; color: var(--ink-2); }
"""


def render_orcamento_html(parsed_data, auto_print=False):
    """Orçamento / Ordem de Serviço A4, com valores."""
    d = parsed_data or {}
    plate_disp = d.get("plate_display") or format_plate_display(d.get("plate", "")) or "SEM PLACA"
    visit_num = d.get("visit_num") or "—"
    client_name = d.get("client_name") or "Cliente não informado"
    cpf = d.get("cpf") or "—"
    rg = d.get("rg") or ""
    phone = d.get("phone") or "—"
    email = d.get("email") or ""
    full_address = _format_address_line(d) or "—"

    car_full = f"{d.get('car_brand') or ''} {d.get('car_model') or 'Veículo não informado'}".strip()
    car_year = d.get("car_year") or "—"
    car_color = d.get("car_color") or "—"
    car_fuel = d.get("car_fuel") or "—"
    car_chassis = d.get("car_chassis") or ""

    entry_date = d.get("entry_date") or ""
    entry_time = d.get("entry_time") or ""
    exit_date = d.get("exit_date") or ""
    exit_time = d.get("exit_time") or ""
    odometer = _format_km(d.get("odometer"))
    complaint = d.get("complaint") or "Revisão / manutenção automotiva"
    complaint_comment = d.get("complaint_comment") or ""
    payment_method = d.get("payment_method") or "A combinar"

    pecas = _norm_items(d.get("pecas_items") or d.get("pecas"))
    servicos = _norm_items(d.get("servicos_items") or d.get("servicos"))

    # Totais: usa o que veio da planilha; calcula se estiver ausente.
    total_pecas = d.get("total_pecas") or _fmt_brl(_sum_items(pecas))
    total_servicos = d.get("total_servicos") or _fmt_brl(_sum_items(servicos))
    subtotal = d.get("subtotal") or _fmt_brl(parse_currency_float(total_pecas) + parse_currency_float(total_servicos))
    discount = d.get("discount") or ""
    total = d.get("total") or d.get("total_geral") or _fmt_brl(
        parse_currency_float(subtotal) - parse_currency_float(discount)
    )

    doc_title = _file_stem("Orcamento", d.get("plate") or plate_disp)
    running = f"Ordem de Serviço nº {visit_num} · {plate_disp} · {client_name}"

    dates = ""
    if entry_date:
        dates += f"<div><b>Entrada</b> {_esc(entry_date)} {_esc(entry_time)}</div>"
    if exit_date and exit_date != "—":
        dates += f"<div><b>Saída</b> {_esc(exit_date)} {_esc(exit_time)}</div>"
    dates += f"<div><b>Emitido em</b> {_hoje()}</div>"

    ano_cor = " · ".join(p for p in (str(car_year), str(car_color)) if p and p != "—") or "—"
    rg_html = f" · RG {_esc(rg)}" if rg else ""
    email_html = f"<dt>E-mail</dt><dd>{_esc(email)}</dd>" if email else ""
    chassis_html = f"<dt>Chassi</dt><dd>{_esc(car_chassis)}</dd>" if car_chassis and car_chassis != "—" else ""

    # Laudo curto fica antes da garantia; laudo longo (ex.: relatório de scanner)
    # vai como anexo depois da assinatura, para não empurrar o fechamento para outra página.
    laudo_inline, laudo_anexo = "", ""
    if complaint_comment:
        longo = len(complaint_comment.splitlines()) > 10 or len(complaint_comment) > 700
        titulo = "Anexo · laudo técnico / leitura de scanner" if longo else ESCANER_TITULO
        bloco = f"""
        <div class="section{'' if longo else ' keep'}">
            <div class="section-title"><span>{titulo}</span></div>
            <pre class="report">{_esc(complaint_comment)}</pre>
        </div>"""
        if longo:
            laudo_anexo = bloco
        else:
            laudo_inline = bloco

    discount_row = ""
    if discount and not _is_zero_money(discount):
        discount_row = f'<tr><td>Desconto</td><td class="v">- {_esc(discount)}</td></tr>'

    switch_href = "/api/checklist_pdf?file_path=" + quote(str(d.get("file_path", "")))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_esc(doc_title)}</title>
    <style>{_base_css(running)}{_orcamento_css()}
    </style>
</head>
<body>
    {_toolbar("Orçamento / OS", f"{plate_disp} — {client_name} ({car_full})",
              (switch_href, "Ver checklist (sem valores)"))}

    <div class="sheet">
        <header class="doc-header">
            {_brand_block()}
            <div class="doc-id">
                <div class="doc-kind">Ordem de serviço · Orçamento</div>
                <div class="doc-number">Nº {_esc(visit_num)}</div>
                <div class="doc-dates">{dates}</div>
            </div>
        </header>

        <div class="parties">
            <section>
                <div class="section-title"><span>Cliente</span></div>
                <dl class="kv">
                    <dt>Nome</dt><dd class="strong">{_esc(client_name)}</dd>
                    <dt>CPF / CNPJ</dt><dd>{_esc(cpf)}{rg_html}</dd>
                    <dt>Telefone</dt><dd>{_esc(phone)}</dd>
                    <dt>Endereço</dt><dd>{_esc(full_address)}</dd>
                    {email_html}
                </dl>
            </section>
            <section>
                <div class="section-title"><span>Veículo</span></div>
                <dl class="kv">
                    <dt>Placa</dt><dd>{_plate_html(plate_disp, "sm")}</dd>
                    <dt>Veículo</dt><dd class="strong">{_esc(car_full)}</dd>
                    <dt>Ano / cor</dt><dd>{_esc(ano_cor)}</dd>
                    <dt>Combustível</dt><dd>{_esc(car_fuel)}</dd>
                    <dt>Hodômetro</dt><dd>{_esc(odometer)}</dd>
                    {chassis_html}
                </dl>
            </section>
        </div>

        <div class="callout keep">
            <div class="callout-label">Queixa / defeito relatado</div>
            <div class="callout-text">{_esc(complaint)}</div>
        </div>

        {_orcamento_table("Peças e insumos", "Descrição da peça / material", pecas,
                          "Nenhuma peça discriminada nesta ordem de serviço.", "Subtotal de peças", total_pecas)}

        {_orcamento_table("Mão de obra e serviços", "Descrição do serviço", servicos,
                          "Mão de obra incluída ou não discriminada separadamente.", "Subtotal de mão de obra", total_servicos)}

        <div class="summary keep">
            <div>
                <div class="pay-label">Forma de pagamento</div>
                <div class="pay-value">{_esc(payment_method)}</div>
            </div>
            <table class="totals">
                <tr><td>Peças</td><td class="v">{_esc(total_pecas)}</td></tr>
                <tr><td>Mão de obra</td><td class="v">{_esc(total_servicos)}</td></tr>
                <tr><td>Subtotal</td><td class="v">{_esc(subtotal)}</td></tr>
                {discount_row}
                <tr class="total"><td>Total geral</td><td class="v">{_esc(total)}</td></tr>
            </table>
        </div>

        {laudo_inline}

        <div class="keep">
            <div class="terms section">
                <div class="section-title"><span>Garantia e condições</span></div>
                <p>{_esc(GARANTIA_TERMOS)}</p>
            </div>
            <div class="signatures">
                <div class="sig"><b>{EMPRESA_MARCA}</b>Responsável técnico</div>
                <div class="sig"><b>{_esc(client_name)}</b>Cliente · ciente e de acordo</div>
            </div>
            <div class="sig-date">Santos, ____ / ____ / ________</div>
        </div>
        {laudo_anexo}
    </div>
    {_auto_print_script(auto_print)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Checklist de para-brisa (sem valores)
# ---------------------------------------------------------------------------
def _checklist_css():
    return """
        body { font-size: 11pt; }
        .doc-header { margin-bottom: 4mm; padding-bottom: 2.5mm; }
        .brand img { width: 13mm; height: 13mm; }
        .brand-name { font-size: 13pt; }
        .doc-number { font-size: 17pt; margin: .4mm 0 .8mm; }

        .hero { display: flex; align-items: center; gap: 7mm; margin-bottom: 4mm; }
        .hero-info { flex: 1; min-width: 0; }
        .hero-model { font-size: 19pt; font-weight: 700; line-height: 1.15; letter-spacing: -.01em; overflow-wrap: anywhere; }
        .hero-sub { margin-top: 1mm; font-size: 13pt; font-weight: 600; color: var(--ink-2); }
        .hero-line { margin-top: 2.2mm; font-size: 12pt; }
        .hero-line span { display: block; font-size: 7.5pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .hero-line b { font-weight: 700; font-size: 14pt; overflow-wrap: anywhere; }

        .complaint {
            margin-bottom: 4mm;
            padding: 3mm 4mm 3.2mm 5mm;
            border: .5mm solid var(--ink);
            border-left: 2.6mm solid var(--accent);
        }
        .complaint-label { font-size: 8pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-2); }
        .complaint-text { margin-top: 1mm; font-size: 17pt; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; }

        table.items tr.sec th { font-size: 10pt; padding-bottom: 1.5mm; }
        table.items tr.sec th small { font-size: 8.5pt; }
        table.items tr.cols th { font-size: 7.5pt; }
        table.todo td { padding: 2.3mm 2mm; border-bottom: .25mm solid var(--line); vertical-align: middle; }
        table.todo .chk { width: 15mm; text-align: center; }
        table.todo .qty { width: 16mm; font-size: 15pt; font-weight: 700; }
        table.todo td.desc { font-size: 13pt; font-weight: 600; line-height: 1.25; }
        .check-box { width: 9mm; height: 9mm; margin: 0 auto; border: .55mm solid var(--ink); border-radius: 1.2mm; background: #fff; }
        .item-note { margin-top: .8mm; font-size: 9.5pt; font-weight: 400; color: var(--ink-2); }
        table.todo td.empty { font-size: 10pt; }

        .notes-lines div { height: 8mm; border-bottom: .25mm solid #9ca3af; }
        .closing { display: grid; grid-template-columns: 1.2fr 1fr; gap: 9mm; margin-top: 2mm; }
        .field { height: 9mm; display: flex; align-items: flex-end; border-bottom: .25mm solid var(--ink); font-size: 7.5pt; color: var(--muted); letter-spacing: .08em; text-transform: uppercase; font-weight: 600; }
        .rodagem { display: flex; flex-direction: column; gap: 2.2mm; margin: 3mm 0 1mm; font-size: 12pt; font-weight: 600; }
        .rodagem .opt { display: inline-flex; align-items: center; gap: 3mm; }
        .rodagem .check-box { width: 7mm; height: 7mm; margin: 0; }
"""


def _checklist_rows(items, empty_text):
    if not items:
        return f'<tr><td colspan="3" class="empty">{_esc(empty_text)}</td></tr>'
    rows = []
    for it in items:
        note = f'<div class="item-note">Obs.: {_esc(it.get("comment"))}</div>' if it.get("comment") else ""
        rows.append(
            "<tr>"
            '<td class="chk"><div class="check-box"></div></td>'
            f'<td class="qty">{_esc(it.get("quantity") or "1")}</td>'
            f'<td class="desc">{_desc(it)}{note}</td>'
            "</tr>"
        )
    return "".join(rows)


def _checklist_table(title, desc_header, items, empty_text):
    return f"""
        <table class="items todo">
            <thead>
                <tr class="sec"><th colspan="3">{_esc(title)}<small>{len(items)} {'item' if len(items) == 1 else 'itens'}</small></th></tr>
                <tr class="cols"><th class="chk" style="text-align:center">OK</th><th class="qty">Qtd.</th><th class="desc">{_esc(desc_header)}</th></tr>
            </thead>
            <tbody>{_checklist_rows(items, empty_text)}</tbody>
        </table>"""


def _split_checklist_items(d, custom_items, pecas, servicos):
    """Resolução de peças/serviços (customizados pela interface ou originais da visita)."""
    if pecas is None:
        if isinstance(d.get("pecas"), list):
            pecas = list(d["pecas"])
        elif custom_items is not None or "items" in d:
            all_items = custom_items if custom_items is not None else d.get("items", [])
            pecas = [
                it for it in all_items
                if str(it.get("type", "")).lower() in ("peca", "peça", "part")
                or str(it.get("section", "")).lower() in ("peca", "peça", "peças", "pecas")
                or (not it.get("type") and str(it.get("section", "")).lower() not in ("serviço", "servico"))
            ]
        elif isinstance(d.get("pecas_items"), list):
            pecas = list(d["pecas_items"])
        else:
            pecas = []
    else:
        pecas = list(pecas)

    if servicos is None:
        if isinstance(d.get("servicos"), list):
            servicos = list(d["servicos"])
        elif custom_items is not None or "items" in d:
            all_items = custom_items if custom_items is not None else d.get("items", [])
            servicos = [
                it for it in all_items
                if str(it.get("type", "")).lower() in ("servico", "serviço", "service")
                or str(it.get("section", "")).lower() in ("servico", "serviço")
            ]
        elif isinstance(d.get("servicos_items"), list):
            servicos = list(d["servicos_items"])
        else:
            servicos = []
    else:
        servicos = list(servicos)

    for m_item in d.get("manual_items") or []:
        if not isinstance(m_item, dict):
            continue
        if str(m_item.get("type", "")).lower() in ("servico", "serviço", "service"):
            servicos.append(m_item)
        else:
            pecas.append(m_item)
    return _norm_items(pecas), _norm_items(servicos)


def render_checklist_html(parsed_data, auto_print=False, include_scanner=True, custom_items=None, pecas=None, servicos=None):
    """Checklist de para-brisa: SEM nenhum valor financeiro. Legível pendurado no vidro."""
    d = parsed_data or {}
    plate_disp = d.get("plate_display") or format_plate_display(d.get("plate", "")) or "SEM PLACA"
    visit_num = d.get("visit_num") or "—"
    client_name = d.get("client_name") or "Cliente não informado"

    car_full = f"{d.get('car_brand') or ''} {d.get('car_model') or 'Veículo'}".strip()
    car_year = d.get("car_year") or ""
    car_color = d.get("car_color") or ""
    entry_date = d.get("entry_date") or ""
    entry_time = d.get("entry_time") or ""
    odometer = _format_km(d.get("odometer"))
    complaint = d.get("complaint") or "Revisão / manutenção"
    complaint_comment = d.get("complaint_comment") or ""

    if include_scanner is None:
        include_scanner = d.get("include_scanner", True)
    if isinstance(include_scanner, str):
        include_scanner = include_scanner.lower() not in ("0", "false", "no", "nao", "não")
    include_scanner = bool(include_scanner)

    pecas, servicos = _split_checklist_items(d, custom_items, pecas, servicos)

    doc_title = _file_stem("Checklist", d.get("plate") or plate_disp)
    running = f"Checklist · OS nº {visit_num} · {plate_disp}"

    sub = " · ".join(p for p in (car_color, car_year) if p and p != "—")

    scanner_html = ""
    if include_scanner and complaint_comment:
        scanner_html = f"""
        <div class="section" style="margin-top:5mm">
            <div class="section-title"><span>CÓDIGOS DE FALHA (SCANNER) E ANOTAÇÕES DE DIAGNÓSTICO</span></div>
            <pre class="report">{_esc(complaint_comment)}</pre>
        </div>"""

    note_lines = "".join("<div></div>" for _ in range(6))
    switch_href = "/api/orcamento_pdf?file_path=" + quote(str(d.get("file_path", "")))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_esc(doc_title)}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>{_base_css(running)}{_checklist_css()}
    </style>
</head>
<body>
    {_toolbar("Checklist", f"{plate_disp} — {car_full} ({client_name})",
              (switch_href, "Ver orçamento completo"), "Imprimir checklist")}

    <div class="sheet">
        <header class="doc-header">
            {_brand_block(compact=True)}
            <div class="doc-id">
                <div class="doc-kind">CHECKLIST · FOLHA DE CHÃO DE OFICINA</div>
                <div class="doc-number">OS nº {_esc(visit_num)}</div>
                <div class="doc-dates">{('<b>Entrada</b> ' + _esc(entry_date) + ' ' + _esc(entry_time)) if entry_date else '<b>Emitido em</b> ' + _hoje()}</div>
            </div>
        </header>

        <div class="hero keep">
            {_plate_html(plate_disp, "xl")}
            <div class="hero-info">
                <div class="hero-model">{_esc(car_full)}</div>
                <div class="hero-sub">{_esc(sub)}</div>
                <div class="hero-line"><span>Hodômetro</span><b>{_esc(odometer)}</b></div>
                <div class="hero-line"><span>Cliente</span><b>{_esc(client_name)}</b></div>
            </div>
        </div>

        <div class="complaint keep">
            <div class="complaint-label">Defeito relatado / solicitação do cliente</div>
            <div class="complaint-text">{_esc(complaint)}</div>
        </div>

        {_checklist_table("Peças aprovadas", "Peça / componente", pecas, "Nenhuma peça selecionada para este checklist.")}

        {_checklist_table("Serviços e mão de obra aprovados", "Serviço a executar", servicos, "Nenhum serviço selecionado para este checklist.")}

        <div class="closing keep">
            <div>
                <div class="section-title"><span>Anotações do mecânico</span></div>
                <div class="notes-lines">{note_lines}</div>
            </div>
            <div>
                <div class="section-title"><span>Teste de rodagem</span></div>
                <div class="rodagem">
                    <span class="opt"><span class="check-box"></span> Realizado</span>
                    <span class="opt"><span class="check-box"></span> Sem anormalidades</span>
                    <span class="opt"><span class="check-box"></span> Retornar à bancada</span>
                </div>
                <div class="field">Rodagem (km)</div>
                <div class="field">Mecânico responsável</div>
                <div class="field">Data / hora</div>
            </div>
        </div>

        {scanner_html}
    </div>
    {_auto_print_script(auto_print)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Histórico do veículo (linha do tempo)
# ---------------------------------------------------------------------------
def _history_css():
    return """
        .vehicle {
            display: flex;
            align-items: center;
            gap: 6mm;
            margin-bottom: 4mm;
            padding-bottom: 4mm;
            border-bottom: .2mm solid var(--line);
        }
        .vehicle-info { flex: 1; min-width: 0; }
        .vehicle-model { font-size: 13pt; font-weight: 700; overflow-wrap: anywhere; }
        .vehicle-meta { margin-top: .6mm; font-size: 9pt; color: var(--ink-2); }
        .stats { display: flex; gap: 8mm; text-align: right; }
        .stat span { display: block; font-size: 7pt; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .stat b { font-size: 12pt; font-weight: 700; }

        .timeline { position: relative; margin: 6mm 0 0 2.2mm; padding-left: 7mm; border-left: .3mm solid #9ca3af; }
        .visit { position: relative; padding-bottom: 5.5mm; break-inside: avoid; page-break-inside: avoid; }
        .visit::before {
            content: "";
            position: absolute;
            left: calc(-7mm - 1.3mm - .15mm);
            top: 1.1mm;
            width: 2.6mm;
            height: 2.6mm;
            border-radius: 50%;
            background: var(--ink);
            box-shadow: 0 0 0 1mm #fff;
        }
        .visit.latest::before { background: var(--accent); border: .45mm solid var(--ink); }
        .visit-head { display: flex; align-items: baseline; gap: 3.5mm; }
        .v-date { font-size: 11pt; font-weight: 700; }
        .v-meta { font-size: 8.5pt; color: var(--muted); }
        .v-total { margin-left: auto; font-size: 10.5pt; font-weight: 700; white-space: nowrap; }
        .v-complaint { margin-top: .8mm; font-size: 9pt; color: var(--ink-2); overflow-wrap: anywhere; }
        .v-lists { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm 8mm; margin-top: 1.8mm; }
        .v-lists.single { grid-template-columns: 1fr; }
        .v-lists h4 { margin-bottom: .6mm; padding-bottom: .5mm; border-bottom: .2mm solid var(--line); font-size: 7pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
        .v-lists ul { list-style: none; }
        .v-lists li { display: flex; gap: 2mm; padding: .5mm 0; font-size: 8.5pt; line-height: 1.3; }
        .v-lists li .q { flex: none; width: 6mm; color: var(--muted); text-align: right; }
        .v-lists li .t { flex: 1; min-width: 0; overflow-wrap: anywhere; }
        .v-lists li .p { flex: none; white-space: nowrap; color: var(--ink-2); }
        .v-none { margin-top: 1.5mm; font-size: 8.5pt; color: var(--muted); font-style: italic; }
        .tl-empty { padding: 6mm 0; color: var(--muted); font-style: italic; }
"""


def _history_list(title, items, without_prices):
    if not items:
        return ""
    lis = []
    for it in items:
        price = ""
        if not without_prices:
            price = f'<span class="p">{_esc(_money(it.get("total_price")))}</span>'
        lis.append(
            f'<li><span class="q">{_esc(it.get("quantity") or "1")}×</span>'
            f'<span class="t">{_desc(it)}</span>{price}</li>'
        )
    return f"<div><h4>{_esc(title)} ({len(items)})</h4><ul>{''.join(lis)}</ul></div>"


def render_consolidated_history_html(vehicle_info, visits, without_prices=False, auto_print=False):
    """Histórico do veículo como linha do tempo das visitas (modo completo ou sem valores)."""
    v_info = vehicle_info or {}
    visits = list(visits or [])
    plate_disp = v_info.get("plate_display") or format_plate_display(v_info.get("plate", "")) or "SEM PLACA"
    client_name = v_info.get("client_name") or "Cliente não informado"
    car_model = v_info.get("car_model") or "Veículo"
    car_year = v_info.get("car_year") or ""
    car_color = v_info.get("car_color") or ""
    total_selected = len(visits)

    doc_title = _file_stem("Historico", v_info.get("plate") or plate_disp)
    mode_label = "SEM VALORES" if without_prices else "HISTÓRICO COMPLETO"
    running = f"Histórico do veículo · {plate_disp}"

    grand_total = 0.0
    entries = []
    for idx, v in enumerate(visits):
        v_num = v.get("visit_num") or "—"
        v_date = v.get("entry_date") or "Data não informada"
        v_km = _format_km(v.get("odometer"))
        v_complaint = v.get("complaint") or "Manutenção / revisão"

        details = v.get("details") or {}
        items = _norm_items(details.get("items"))
        pecas = _norm_items(details.get("pecas_items")) or [
            it for it in items if str(it.get("section", "")).lower() not in ("serviço", "servico")
        ]
        servicos = _norm_items(details.get("servicos_items")) or [
            it for it in items if str(it.get("section", "")).lower() in ("serviço", "servico")
        ]
        total_visit = details.get("total_geral") or details.get("total") or ""
        grand_total += parse_currency_float(total_visit)

        if pecas or servicos:
            cls = "v-lists" if (pecas and servicos) else "v-lists single"
            body = (
                f'<div class="{cls}">{_history_list("Peças", pecas, without_prices)}'
                f'{_history_list("Mão de obra", servicos, without_prices)}</div>'
            )
        else:
            body = '<div class="v-none">Nenhum item registrado nesta visita.</div>'

        total_html = ""
        if not without_prices and total_visit:
            total_html = f'<span class="v-total">{_esc(total_visit)}</span>'

        entries.append(f"""
            <div class="visit{' latest' if idx == 0 else ''}">
                <div class="visit-head">
                    <span class="v-date">{_esc(v_date)}</span>
                    <span class="v-meta">OS nº {_esc(v_num)} · {_esc(v_km)}</span>
                    {total_html}
                </div>
                <div class="v-complaint">{_esc(v_complaint)}</div>
                {body}
            </div>""")

    timeline = "".join(entries) if entries else '<div class="tl-empty">Nenhuma visita selecionada.</div>'

    dates = [v.get("entry_date") for v in visits if v.get("entry_date")]
    periodo = f"{dates[-1]} a {dates[0]}" if len(dates) > 1 else (dates[0] if dates else "—")

    total_stat = ""
    if not without_prices:
        total_stat = f'<div class="stat"><span>Total no período</span><b>{_esc(_fmt_brl(grand_total))}</b></div>'

    sub = " · ".join(p for p in (car_color, car_year) if p and p != "—")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_esc(doc_title)}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>{_base_css(running)}{_history_css()}
    </style>
</head>
<body>
    {_toolbar("Histórico", f"{plate_disp} — {car_model} ({total_selected} visitas · {mode_label})", None, "Imprimir histórico")}

    <div class="sheet">
        <header class="doc-header">
            {_brand_block()}
            <div class="doc-id">
                <div class="doc-kind">Histórico do veículo</div>
                <div class="doc-number" style="font-size:13pt;letter-spacing:.02em">{mode_label}</div>
                <div class="doc-dates"><b>Período</b> {_esc(periodo)}<br><b>Emitido em</b> {_hoje()}</div>
            </div>
        </header>

        <div class="vehicle">
            {_plate_html(plate_disp, "md")}
            <div class="vehicle-info">
                <div class="vehicle-model">{_esc(car_model)}</div>
                <div class="vehicle-meta">{_esc(sub)}{' · ' if sub else ''}Cliente: <b>{_esc(client_name)}</b></div>
                <div class="vehicle-meta">Visitas selecionadas: <strong>{total_selected}</strong></div>
            </div>
            <div class="stats">{total_stat}</div>
        </div>

        <div class="timeline">{timeline}
        </div>
    </div>
    {_auto_print_script(auto_print)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Atalhos a partir de arquivo
# ---------------------------------------------------------------------------
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
        servicos=servicos,
    )
