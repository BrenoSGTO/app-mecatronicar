# -*- coding: utf-8 -*-
"""
Módulo excel_writer.py - MecatroniCar v2.0
Responsável por criar e atualizar planilhas .xlsx fiéis à estrutura legada (Plan1, A1:I54)
com preservação de fórmulas Excel (=G*H, =SUM), cabeçalhos, larguras de coluna, alturas de linha,
mesclagens e comentários do scanner automotivo.
"""

import os
import re
import datetime
import sqlite3
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
import openpyxl.worksheet._writer as openpyxl_ws_writer
import openpyxl.cell._writer as openpyxl_cell_writer

import parser
import config

# ==========================================
# CONSTANTES DE LAYOUT & ESTILOS LEGADOS
# ==========================================

COLUMN_WIDTHS = {
    'A': 13.0,
    'B': 13.0,
    'C': 13.0,
    'D': 13.0,
    'E': 11.7109375,
    'F': 13.0,
    'G': 13.0,
    'H': 13.0,
    'I': 9.5703125
}

ROW_HEIGHTS = {
    1: 12.75,
    2: 12.75,
    3: 12.75,
    4: 12.75,
    5: 13.7,
    7: 13.5,
    8: 13.5,
    15: 13.5,
    16: 13.5,
    19: 13.5,
    20: 14.25,
    21: 13.5,
    24: 12.75,
    25: 12.75,
    26: 12.75
}

MERGED_RANGES = [
    'A1:I5',
    'A7:I7',
    'B9:I9',
    'B10:E10',
    'B11:D11',
    'F11:G11',
    'B12:C12',
    'E12:F12',
    'H12:I12',
    'B13:C13',
    'E13:F13',
    'B14:C14',
    'E14:F14',
    'A15:I15',
    'B17:C17',
    'E17:F17',
    'H17:I17',
    'B18:C18',
    'E18:F18',
    'H18:I18',
    'B19:D19',
    'A20:I20',
    'A24:I26',
    'A28:F28',
    'A30:F30',
    'A31:F31',
    'A32:F32',
    'A33:F33',
    'A34:F34',
    'A35:F35',
    'A36:F36',
    'A37:F37',
    'A38:F38',
    'A39:F39',
    'A40:F40',
    'A41:F41',
    'A42:F42',
    'A43:F43',
    'A45:F45',
    'A47:F47',
    'A48:F48',
    'A49:F49',
    'A50:F50',
    'A54:C54',
    'D54:I54'
]

# Estilos de Fontes
FONT_BANNER = Font(name='Lucida Calligraphy', size=55, bold=True)
FONT_BOLD_10 = Font(name='Arial', size=10, bold=True)
FONT_REGULAR_10 = Font(name='Arial', size=10, bold=False)
FONT_COMPLAINT_14 = Font(name='Arial', size=14, bold=True)

# Estilos de Alinhamento
ALIGN_CENTER = Alignment(horizontal='center', vertical='center')
ALIGN_CENTER_HORIZ = Alignment(horizontal='center', vertical='bottom')
ALIGN_LEFT = Alignment(horizontal='left', vertical='bottom')
ALIGN_RIGHT = Alignment(horizontal='right', vertical='bottom')
ALIGN_COMPLAINT = Alignment(horizontal='center', vertical='center', wrap_text=True)

# Estilos de Bordas
SIDE_SLANT = Side(style='slantDashDot')
SIDE_DOUBLE = Side(style='double')
SIDE_THIN = Side(style='thin')

BORDER_DOUBLE_BOTTOM = Border(bottom=SIDE_DOUBLE)
BORDER_THIN_ALL = Border(left=SIDE_THIN, right=SIDE_THIN, top=SIDE_THIN, bottom=SIDE_THIN)

# Formatos numéricos
NUM_FMT_CURRENCY = '0.00'
NUM_FMT_INTEGER = '#,##0'
NUM_FMT_DATE = 'dd/mm/yy;@'
NUM_FMT_TIME = 'h:mm'

# ==========================================
# UTILITÁRIOS DE NOMEAÇÃO & PLACA
# ==========================================

def format_plate_filename(plate_str):
    """
    Formata a placa para o nome de arquivo com espaçamento tradicional:
    Exemplo: 'FNB1A77' -> 'FNB 1A77'
    """
    if not plate_str:
        return ""
    cleaned = parser.clean_plate(plate_str)
    if len(cleaned) == 7:
        return f"{cleaned[:3]} {cleaned[3:]}"
    return str(plate_str).strip().upper()

def sanitize_filename_part(part_str):
    r"""
    Remove caracteres proibidos no sistema de arquivos do Windows: \ / : * ? " < > |
    """
    if not part_str:
        return ""
    clean = re.sub(r'[\\/*?:"<>|]', '', str(part_str))
    # Limpa múltiplos espaços
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def generate_filename(plate, visit_num, client_name, car_model, car_color):
    """
    Gera o nome de arquivo canônico do MecatroniCar:
    'PLACA - Nº_VISITA - Nome Cliente - Modelo - Cor.xlsx'
    Exemplo: 'FNB 1A77 - 8 - Danilo Pereira - VW Fox - Prata.xlsx'
    """
    p_plate = format_plate_filename(plate) or "SEM_PLACA"
    p_visit = str(visit_num).strip() if visit_num is not None and str(visit_num).strip() != "" else "1"
    p_client = sanitize_filename_part(client_name) or "Cliente"
    p_model = sanitize_filename_part(car_model) or "Veiculo"
    p_color = sanitize_filename_part(car_color) or "NaoInformada"
    
    return f"{p_plate} - {p_visit} - {p_client} - {p_model} - {p_color}.xlsx"

# ==========================================
# HISTÓRICO & CLIENTES RECORRENTES
# ==========================================

def get_next_visit_number(plate, folder_path=None, db_path=None):
    """
    Calcula automaticamente o próximo número de visita para um veículo (Visita N + 1).
    Consulta o cache SQLite ou os arquivos na pasta. Retorna 1 se for a primeira visita.
    """
    cleaned_plate = parser.clean_plate(plate)
    if not cleaned_plate:
        return 1
        
    db_file = db_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "oficina_cache.db")
    max_visit = 0
    
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute("""
            SELECT visit_num, file_name FROM files 
            WHERE plate_clean = ? OR plate_clean LIKE ?
            """, (cleaned_plate, f"%{cleaned_plate}%"))
            rows = cur.fetchall()
            conn.close()
            
            for v_num_str, fn in rows:
                if v_num_str and str(v_num_str).isdigit():
                    max_visit = max(max_visit, int(v_num_str))
                else:
                    meta = parser.parse_filename(fn)
                    if meta.get("visit_num") and meta["visit_num"].isdigit():
                        max_visit = max(max_visit, int(meta["visit_num"]))
        except Exception:
            pass

    # Se uma pasta foi fornecida ou configurada, confere também arquivos físicos
    target_folder = folder_path
    if not target_folder:
        try:
            cfg = config.load_config()
            target_folder = cfg.get("spreadsheet_folder", "")
        except Exception:
            pass
            
    if target_folder and os.path.isdir(target_folder):
        try:
            for root, _, files in os.walk(target_folder):
                for f in files:
                    if f.startswith("~$"):
                        continue
                    if f.lower().endswith(('.xlsx', '.xls')):
                        meta = parser.parse_filename(f)
                        if meta.get("plate") and parser.clean_plate(meta["plate"]) == cleaned_plate:
                            if meta.get("visit_num") and meta["visit_num"].isdigit():
                                max_visit = max(max_visit, int(meta["visit_num"]))
        except Exception:
            pass

    return max_visit + 1

def get_previous_vehicle_data(plate, folder_path=None, db_path=None):
    """
    Recupera os dados cadastrais da última visita de um veículo para auto-completar a nova OS:
    Nome, CPF, RG, Endereço, Telefones, Marca, Modelo, Ano, Cor, Combustível, Chassi, etc.
    """
    cleaned_plate = parser.clean_plate(plate)
    if not cleaned_plate:
        return None
        
    import cache
    db_file = db_path or cache.get_db_path()
    history = cache.get_car_history(cleaned_plate, db_file)
    
    if not history:
        return None
        
    latest = history[0]
    details = latest.get("details") or {}
    
    return {
        "client_name": details.get("client_name") or latest.get("client_name", ""),
        "cpf": details.get("cpf") or "",
        "rg": details.get("rg") or "",
        "address": details.get("address") or "",
        "address_num": details.get("address_num") or "",
        "address_compl": details.get("address_compl") or "",
        "neighborhood": details.get("neighborhood") or "",
        "city": details.get("city") or "",
        "cep": details.get("cep") or "",
        "phone": details.get("phone") or "",
        "tel_res": details.get("tel_res") or "",
        "tel_com": details.get("tel_com") or "",
        "email": details.get("email") or "",
        
        "car_brand": details.get("car_brand") or "",
        "car_model": details.get("car_model") or latest.get("car_model", ""),
        "model_comment": details.get("model_comment") or "",
        "car_year": details.get("car_year") or latest.get("car_year", ""),
        "car_plate": details.get("plate") or latest.get("plate", ""),
        "plate_comment": details.get("plate_comment") or "",
        "car_color": details.get("car_color") or latest.get("car_color", ""),
        "car_fuel": details.get("car_fuel") or "",
        "car_chassis": details.get("car_chassis") or "",
        
        "last_visit_num": latest.get("visit_num", ""),
        "next_visit_num": get_next_visit_number(plate, folder_path, db_path),
        "last_entry_date": latest.get("entry_date", ""),
        "last_odometer": latest.get("odometer", "")
    }

# ==========================================
# APLICAÇÃO DE BORDAS E FORMATAÇÃO
# ==========================================

def _apply_box_border(ws, start_row, start_col, end_row, end_col, side_style):
    """
    Aplica borda de contorno (box outline) em uma região retangular.
    """
    for r in range(start_row, end_row + 1):
        for c in range(start_col, end_col + 1):
            cell = ws.cell(r, c)
            left = side_style if c == start_col else None
            right = side_style if c == end_col else None
            top = side_style if r == start_row else None
            bottom = side_style if r == end_row else None
            cell.border = Border(left=left, right=right, top=top, bottom=bottom)

def _apply_row_bottom_border(ws, row_idx, start_col, end_col, side_style):
    """
    Aplica borda inferior ao longo de uma linha de colunas.
    """
    for c in range(start_col, end_col + 1):
        ws.cell(row_idx, c).border = Border(bottom=side_style)

# ==========================================
# CONSTRUÇÃO DO TEMPLATE LEGADO (Plan1)
# ==========================================

def build_legacy_template(wb=None):
    """
    Cria ou formata a planilha Plan1 reproduzindo exatamente o padrão legado:
    - Largura das colunas A..I
    - Altura das linhas
    - 45 mesclagens oficiais
    - Textos fixos e bordas decorativas
    - Fórmulas dinâmicas pré-injetadas
    """
    if wb is None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Plan1"
    else:
        if "Plan1" in wb.sheetnames:
            ws = wb["Plan1"]
        else:
            ws = wb.create_sheet(title="Plan1", index=0)

    # Configuração de Página para Impressão A4 Retrato
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4

    # Larguras de coluna
    for col_letter, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    # Alturas de linha
    for row_idx, height in ROW_HEIGHTS.items():
        ws.row_dimensions[row_idx].height = height

    # Aplicação das Mesclagens Legadas
    existing_merges = {str(m) for m in ws.merged_cells.ranges}
    for m in MERGED_RANGES:
        if m not in existing_merges:
            ws.merge_cells(m)

    # 1. BANNER MecatroniCar (A1:I5)
    ws.cell(1, 1).value = "MecatroniCar"
    ws.cell(1, 1).font = FONT_BANNER
    ws.cell(1, 1).alignment = ALIGN_CENTER
    _apply_box_border(ws, 1, 1, 5, 9, SIDE_SLANT)

    # 2. SEÇÃO DADOS DO CLIENTE (R7..R14)
    ws.cell(7, 1).value = "Dados do Cliente"
    ws.cell(7, 1).font = FONT_BOLD_10
    ws.cell(7, 1).alignment = ALIGN_CENTER
    _apply_row_bottom_border(ws, 7, 1, 9, SIDE_DOUBLE)

    # R9: Nome:
    ws.cell(9, 1).value = "Nome:"
    ws.cell(9, 1).font = FONT_BOLD_10
    ws.cell(9, 1).alignment = ALIGN_LEFT
    ws.cell(9, 2).font = FONT_REGULAR_10
    ws.cell(9, 2).alignment = ALIGN_LEFT

    # R10: End.: | nº: | Compl.:
    ws.cell(10, 1).value = "End.:"
    ws.cell(10, 1).font = FONT_BOLD_10
    ws.cell(10, 1).alignment = ALIGN_LEFT
    ws.cell(10, 2).font = FONT_REGULAR_10
    ws.cell(10, 2).alignment = ALIGN_LEFT

    ws.cell(10, 6).value = "nº:"
    ws.cell(10, 6).font = FONT_BOLD_10
    ws.cell(10, 6).alignment = ALIGN_LEFT
    ws.cell(10, 7).font = FONT_REGULAR_10
    ws.cell(10, 7).alignment = ALIGN_LEFT

    ws.cell(10, 8).value = "Compl.:"
    ws.cell(10, 8).font = FONT_BOLD_10
    ws.cell(10, 8).alignment = ALIGN_LEFT
    ws.cell(10, 9).font = FONT_REGULAR_10
    ws.cell(10, 9).alignment = ALIGN_LEFT

    # R11: Bairro: | Cidade: | CEP:
    ws.cell(11, 1).value = "Bairro:"
    ws.cell(11, 1).font = FONT_BOLD_10
    ws.cell(11, 1).alignment = ALIGN_LEFT
    ws.cell(11, 2).font = FONT_REGULAR_10
    ws.cell(11, 2).alignment = ALIGN_LEFT

    ws.cell(11, 5).value = "Cidade:"
    ws.cell(11, 5).font = FONT_BOLD_10
    ws.cell(11, 5).alignment = ALIGN_LEFT
    ws.cell(11, 6).font = FONT_REGULAR_10
    ws.cell(11, 6).alignment = ALIGN_LEFT

    ws.cell(11, 8).value = "CEP:"
    ws.cell(11, 8).font = FONT_BOLD_10
    ws.cell(11, 8).alignment = ALIGN_LEFT
    ws.cell(11, 9).font = FONT_REGULAR_10
    ws.cell(11, 9).alignment = ALIGN_CENTER_HORIZ

    # R12: Tel. Res.: | Tel. Com: | Celular:
    ws.cell(12, 1).value = "Tel. Res.:"
    ws.cell(12, 1).font = FONT_BOLD_10
    ws.cell(12, 1).alignment = ALIGN_LEFT
    ws.cell(12, 2).font = FONT_REGULAR_10
    ws.cell(12, 2).alignment = ALIGN_LEFT

    ws.cell(12, 4).value = "Tel. Com:"
    ws.cell(12, 4).font = FONT_BOLD_10
    ws.cell(12, 4).alignment = ALIGN_LEFT
    ws.cell(12, 5).font = FONT_REGULAR_10
    ws.cell(12, 5).alignment = ALIGN_LEFT

    ws.cell(12, 7).value = "Celular:"
    ws.cell(12, 7).font = FONT_BOLD_10
    ws.cell(12, 7).alignment = ALIGN_LEFT
    ws.cell(12, 8).font = FONT_BOLD_10
    ws.cell(12, 8).alignment = ALIGN_LEFT

    # R13: CPF: | RG: | ID:
    ws.cell(13, 1).value = "CPF:"
    ws.cell(13, 1).font = FONT_BOLD_10
    ws.cell(13, 1).alignment = ALIGN_LEFT
    ws.cell(13, 2).font = FONT_REGULAR_10
    ws.cell(13, 2).alignment = ALIGN_LEFT

    ws.cell(13, 4).value = "RG:"
    ws.cell(13, 4).font = FONT_BOLD_10
    ws.cell(13, 4).alignment = ALIGN_LEFT
    ws.cell(13, 5).font = FONT_REGULAR_10
    ws.cell(13, 5).alignment = ALIGN_LEFT

    ws.cell(13, 7).value = "ID:"
    ws.cell(13, 7).font = FONT_BOLD_10
    ws.cell(13, 7).alignment = ALIGN_LEFT
    ws.cell(13, 8).font = FONT_REGULAR_10
    ws.cell(13, 8).alignment = ALIGN_LEFT

    # R14: Email:
    ws.cell(14, 1).value = "Email:"
    ws.cell(14, 1).font = FONT_BOLD_10
    ws.cell(14, 1).alignment = ALIGN_LEFT
    ws.cell(14, 2).font = FONT_REGULAR_10
    ws.cell(14, 2).alignment = ALIGN_LEFT

    # 3. SEÇÃO DADOS DO CARRO (R15..R19)
    ws.cell(15, 1).value = "Dados do Carro"
    ws.cell(15, 1).font = FONT_BOLD_10
    ws.cell(15, 1).alignment = ALIGN_CENTER
    _apply_row_bottom_border(ws, 15, 1, 9, SIDE_DOUBLE)

    # R17: Marca: | Modelo: | Ano:
    ws.cell(17, 1).value = "Marca:"
    ws.cell(17, 1).font = FONT_BOLD_10
    ws.cell(17, 1).alignment = ALIGN_LEFT
    ws.cell(17, 2).font = FONT_REGULAR_10
    ws.cell(17, 2).alignment = ALIGN_LEFT

    ws.cell(17, 4).value = "Modelo:"
    ws.cell(17, 4).font = FONT_BOLD_10
    ws.cell(17, 4).alignment = ALIGN_LEFT
    ws.cell(17, 5).font = FONT_REGULAR_10
    ws.cell(17, 5).alignment = ALIGN_LEFT

    ws.cell(17, 7).value = "Ano:"
    ws.cell(17, 7).font = FONT_BOLD_10
    ws.cell(17, 7).alignment = ALIGN_LEFT
    ws.cell(17, 8).font = FONT_REGULAR_10
    ws.cell(17, 8).alignment = ALIGN_LEFT

    # R18: Placa: | Cor: | Combust.:
    ws.cell(18, 1).value = "Placa:"
    ws.cell(18, 1).font = FONT_BOLD_10
    ws.cell(18, 1).alignment = ALIGN_LEFT
    ws.cell(18, 2).font = FONT_REGULAR_10
    ws.cell(18, 2).alignment = ALIGN_LEFT

    ws.cell(18, 4).value = "Cor:"
    ws.cell(18, 4).font = FONT_BOLD_10
    ws.cell(18, 4).alignment = ALIGN_LEFT
    ws.cell(18, 5).font = FONT_REGULAR_10
    ws.cell(18, 5).alignment = ALIGN_LEFT

    ws.cell(18, 7).value = "Combust.:"
    ws.cell(18, 7).font = FONT_BOLD_10
    ws.cell(18, 7).alignment = ALIGN_LEFT
    ws.cell(18, 8).font = FONT_REGULAR_10
    ws.cell(18, 8).alignment = ALIGN_LEFT

    # R19: Chassi:
    ws.cell(19, 1).value = "Chassi:"
    ws.cell(19, 1).font = FONT_BOLD_10
    ws.cell(19, 1).alignment = ALIGN_LEFT
    ws.cell(19, 2).font = FONT_BOLD_10
    ws.cell(19, 2).alignment = ALIGN_LEFT

    # 4. ORDEM DE SERVIÇO (R20..R24)
    ws.cell(20, 1).value = "ORDEM DE SERVIÇO"
    ws.cell(20, 1).font = FONT_BOLD_10
    ws.cell(20, 1).alignment = ALIGN_CENTER
    _apply_box_border(ws, 20, 1, 20, 9, SIDE_DOUBLE)

    # R21: Data de Entrada: | Hora: | Hodômetro:
    ws.cell(21, 1).value = "Data de Entrada:"
    ws.cell(21, 1).font = FONT_BOLD_10
    ws.cell(21, 1).alignment = ALIGN_LEFT
    ws.cell(21, 3).font = FONT_REGULAR_10
    ws.cell(21, 3).alignment = ALIGN_LEFT
    ws.cell(21, 3).number_format = NUM_FMT_DATE

    ws.cell(21, 4).value = "Hora:"
    ws.cell(21, 4).font = FONT_BOLD_10
    ws.cell(21, 4).alignment = ALIGN_LEFT
    ws.cell(21, 5).font = FONT_REGULAR_10
    ws.cell(21, 5).alignment = ALIGN_LEFT
    ws.cell(21, 5).number_format = NUM_FMT_TIME

    ws.cell(21, 7).value = "Hodômetro:"
    ws.cell(21, 7).font = FONT_BOLD_10
    ws.cell(21, 7).alignment = ALIGN_LEFT
    ws.cell(21, 9).font = FONT_REGULAR_10
    ws.cell(21, 9).alignment = ALIGN_LEFT
    ws.cell(21, 9).number_format = NUM_FMT_INTEGER

    # R22: Hora: | Hodômetro:
    ws.cell(22, 4).value = "Hora:"
    ws.cell(22, 4).font = FONT_BOLD_10
    ws.cell(22, 7).value = "Hodômetro:"
    ws.cell(22, 7).font = FONT_BOLD_10

    # R23: Data de Saida: | Hora: | Hodômetro:
    ws.cell(23, 1).value = "Data de Saida:"
    ws.cell(23, 1).font = FONT_BOLD_10
    ws.cell(23, 1).alignment = ALIGN_LEFT
    ws.cell(23, 3).font = FONT_REGULAR_10
    ws.cell(23, 3).alignment = ALIGN_LEFT
    ws.cell(23, 3).number_format = NUM_FMT_DATE

    ws.cell(23, 4).value = "Hora:"
    ws.cell(23, 4).font = FONT_BOLD_10
    ws.cell(23, 4).alignment = ALIGN_LEFT
    ws.cell(23, 5).font = FONT_REGULAR_10
    ws.cell(23, 5).alignment = ALIGN_LEFT
    ws.cell(23, 5).number_format = NUM_FMT_TIME

    ws.cell(23, 7).value = "Hodômetro:"
    ws.cell(23, 7).font = FONT_BOLD_10
    ws.cell(23, 7).alignment = ALIGN_LEFT
    ws.cell(23, 9).font = FONT_REGULAR_10
    ws.cell(23, 9).alignment = ALIGN_LEFT
    ws.cell(23, 9).number_format = NUM_FMT_INTEGER

    # R24:I26 Caixa de Defeito / Diagnóstico Scanner
    ws.cell(24, 1).font = FONT_COMPLAINT_14
    ws.cell(24, 1).alignment = ALIGN_COMPLAINT
    _apply_box_border(ws, 24, 1, 26, 9, SIDE_THIN)

    # 5. TABELA DE PEÇAS (R28..R44)
    ws.cell(28, 1).value = "Peças"
    ws.cell(28, 1).font = FONT_BOLD_10
    ws.cell(28, 1).alignment = ALIGN_CENTER
    _apply_box_border(ws, 28, 1, 28, 6, SIDE_THIN)

    ws.cell(28, 7).value = "Quant."
    ws.cell(28, 7).font = FONT_BOLD_10
    ws.cell(28, 7).alignment = ALIGN_CENTER
    ws.cell(28, 7).border = BORDER_THIN_ALL

    ws.cell(28, 8).value = "Valor Uni."
    ws.cell(28, 8).font = FONT_BOLD_10
    ws.cell(28, 8).alignment = ALIGN_CENTER
    ws.cell(28, 8).border = BORDER_THIN_ALL

    ws.cell(28, 9).value = "Valor Tot."
    ws.cell(28, 9).font = FONT_BOLD_10
    ws.cell(28, 9).alignment = ALIGN_CENTER
    ws.cell(28, 9).border = BORDER_THIN_ALL

    # 14 Linhas de Peças (R30..R43) com fórmula =G*H
    for r in range(30, 44):
        ws.cell(r, 1).font = FONT_REGULAR_10
        ws.cell(r, 1).alignment = ALIGN_LEFT

        ws.cell(r, 7).font = FONT_REGULAR_10
        ws.cell(r, 7).alignment = ALIGN_CENTER

        ws.cell(r, 8).font = FONT_REGULAR_10
        ws.cell(r, 8).number_format = NUM_FMT_CURRENCY

        ws.cell(r, 9).value = f"=G{r}*H{r}"
        ws.cell(r, 9).font = FONT_REGULAR_10
        ws.cell(r, 9).number_format = NUM_FMT_CURRENCY

    # R44: Total Peças =SUM(I30:I43)
    ws.cell(44, 9).value = "=SUM(I30:I43)"
    ws.cell(44, 9).font = FONT_REGULAR_10
    ws.cell(44, 9).number_format = NUM_FMT_CURRENCY

    # 6. TABELA DE SERVIÇOS (R45..R50)
    ws.cell(45, 1).value = "Serviço"
    ws.cell(45, 1).font = FONT_REGULAR_10
    ws.cell(45, 1).alignment = ALIGN_CENTER
    _apply_box_border(ws, 45, 1, 45, 6, SIDE_THIN)

    # 4 Linhas de Serviços (R47..R50) com fórmula =G*H
    for r in range(47, 51):
        ws.cell(r, 1).font = FONT_REGULAR_10
        ws.cell(r, 1).alignment = ALIGN_LEFT

        ws.cell(r, 7).font = FONT_REGULAR_10
        ws.cell(r, 7).alignment = ALIGN_CENTER

        ws.cell(r, 8).font = FONT_REGULAR_10
        ws.cell(r, 8).number_format = NUM_FMT_CURRENCY

        ws.cell(r, 9).value = f"=G{r}*H{r}"
        ws.cell(r, 9).font = FONT_REGULAR_10
        ws.cell(r, 9).number_format = NUM_FMT_CURRENCY

    # 7. TOTAIS E FÓRMULAS (R51..R53)
    # R51: SubTotal: | =I44+I51 | =SUM(I47:I50)
    ws.cell(51, 6).value = "SubTotal:"
    ws.cell(51, 6).font = FONT_REGULAR_10

    ws.cell(51, 7).value = "=I44+I51"
    ws.cell(51, 7).font = FONT_REGULAR_10
    ws.cell(51, 7).alignment = ALIGN_RIGHT
    ws.cell(51, 7).number_format = NUM_FMT_CURRENCY

    ws.cell(51, 9).value = "=SUM(I47:I50)"
    ws.cell(51, 9).font = FONT_REGULAR_10
    ws.cell(51, 9).number_format = NUM_FMT_CURRENCY

    # R52: Desconto: | valor
    ws.cell(52, 6).value = "Desconto:"
    ws.cell(52, 6).font = FONT_REGULAR_10
    ws.cell(52, 7).font = FONT_REGULAR_10
    ws.cell(52, 7).alignment = ALIGN_RIGHT
    ws.cell(52, 7).number_format = NUM_FMT_CURRENCY

    # R53: Total: | =I44+I51-G52
    ws.cell(53, 6).value = "Total:"
    ws.cell(53, 6).font = FONT_BOLD_10
    ws.cell(53, 6).alignment = ALIGN_RIGHT

    ws.cell(53, 7).value = "=I44+I51-G52"
    ws.cell(53, 7).font = FONT_BOLD_10
    ws.cell(53, 7).number_format = NUM_FMT_CURRENCY

    # R54: Forma de Pagamento:
    ws.cell(54, 1).value = "Forma de Pagamento:"
    ws.cell(54, 1).font = FONT_BOLD_10
    ws.cell(54, 1).alignment = ALIGN_LEFT

    ws.cell(54, 4).font = FONT_REGULAR_10
    ws.cell(54, 4).alignment = ALIGN_LEFT

    return wb

# ==========================================
# PREENCHIMENTO DE DADOS DA OS
# ==========================================

def _parse_currency_float(val):
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace("R$", "").strip()
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def _parse_date_obj(val):
    if not val:
        return None
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val
    try:
        m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', str(val).strip())
        if m:
            d, mo, y = [int(x) for x in m.groups()]
            if y < 100:
                y += 2000
            return datetime.datetime(y, mo, d, 0, 0)
    except Exception:
        pass
    return str(val)

def _parse_time_obj(val):
    if not val:
        return None
    if isinstance(val, (datetime.time, datetime.datetime)):
        return val
    try:
        m = re.match(r'^(\d{1,2}):(\d{1,2})', str(val).strip())
        if m:
            h, mi = [int(x) for x in m.groups()]
            return datetime.time(h, mi)
    except Exception:
        pass
    return str(val)

def populate_workbook(wb, data):
    """
    Preenche a planilha Plan1 com o dicionário de dados da OS e calcula o mapa de valores cacheados
    para escrita direta das tags <v> nas fórmulas.
    """
    if "Plan1" not in wb.sheetnames:
        build_legacy_template(wb)
    ws = wb["Plan1"]

    # Mapa de valores pré-calculados para injeção na gravação das fórmulas
    cached_map = {}

    # 1. Dados do Cliente
    if "client_name" in data and data["client_name"] is not None:
        ws.cell(9, 2).value = str(data["client_name"]).strip()
    if "address" in data and data["address"] is not None:
        ws.cell(10, 2).value = str(data["address"]).strip()
    if "address_num" in data and data["address_num"] is not None:
        v = data["address_num"]
        ws.cell(10, 7).value = int(v) if str(v).isdigit() else str(v).strip()
    if "address_compl" in data and data["address_compl"] is not None:
        v = data["address_compl"]
        ws.cell(10, 9).value = int(v) if str(v).isdigit() else str(v).strip()
    if "neighborhood" in data and data["neighborhood"] is not None:
        ws.cell(11, 2).value = str(data["neighborhood"]).strip()
    if "city" in data and data["city"] is not None:
        ws.cell(11, 6).value = str(data["city"]).strip()
    if "cep" in data and data["cep"] is not None:
        ws.cell(11, 9).value = str(data["cep"]).strip()
    if "tel_res" in data and data["tel_res"] is not None:
        ws.cell(12, 2).value = str(data["tel_res"]).strip()
    if "tel_com" in data and data["tel_com"] is not None:
        ws.cell(12, 5).value = str(data["tel_com"]).strip()
    if "phone" in data and data["phone"] is not None:
        ws.cell(12, 8).value = str(data["phone"]).strip()
    if "cpf" in data and data["cpf"] is not None:
        ws.cell(13, 2).value = str(data["cpf"]).strip()
    if "rg" in data and data["rg"] is not None:
        ws.cell(13, 5).value = str(data["rg"]).strip()
    if "email" in data and data["email"] is not None:
        ws.cell(14, 2).value = str(data["email"]).strip()

    # 2. Dados do Carro
    if "car_brand" in data and data["car_brand"] is not None:
        ws.cell(17, 2).value = str(data["car_brand"]).strip()
    if "car_model" in data and data["car_model"] is not None:
        ws.cell(17, 5).value = str(data["car_model"]).strip()
        if data.get("model_comment"):
            ws.cell(17, 5).comment = Comment(str(data["model_comment"]).strip(), "MecatroniCar")
    if "car_year" in data and data["car_year"] is not None:
        v = data["car_year"]
        ws.cell(17, 8).value = int(v) if str(v).isdigit() else str(v).strip()
    if "car_plate" in data and data["car_plate"] is not None:
        ws.cell(18, 2).value = str(data["car_plate"]).strip()
        if data.get("plate_comment"):
            ws.cell(18, 2).comment = Comment(str(data["plate_comment"]).strip(), "MecatroniCar")
    elif "plate" in data and data["plate"] is not None:
        ws.cell(18, 2).value = str(data["plate"]).strip()
    if "car_color" in data and data["car_color"] is not None:
        ws.cell(18, 5).value = str(data["car_color"]).strip()
    if "car_fuel" in data and data["car_fuel"] is not None:
        ws.cell(18, 8).value = str(data["car_fuel"]).strip()
    if "car_chassis" in data and data["car_chassis"] is not None:
        ws.cell(19, 2).value = str(data["car_chassis"]).strip()

    # 3. Ordem de Serviço (Entrada, Saída, Hodômetro e Reclamação)
    if "entry_date" in data and data["entry_date"]:
        dt_val = _parse_date_obj(data["entry_date"])
        ws.cell(21, 3).value = dt_val
    if "entry_time" in data and data["entry_time"]:
        tm_val = _parse_time_obj(data["entry_time"])
        ws.cell(21, 5).value = tm_val
    if "odometer" in data and data["odometer"] is not None and str(data["odometer"]).strip() != "":
        raw_odo = re.sub(r'[^\d]', '', str(data["odometer"]))
        ws.cell(21, 9).value = int(raw_odo) if raw_odo else None

    if "exit_date" in data and data["exit_date"]:
        dt_val = _parse_date_obj(data["exit_date"])
        ws.cell(23, 3).value = dt_val
    if "exit_time" in data and data["exit_time"]:
        tm_val = _parse_time_obj(data["exit_time"])
        ws.cell(23, 5).value = tm_val
    if "exit_odometer" in data and data["exit_odometer"]:
        raw_odo = re.sub(r'[^\d]', '', str(data["exit_odometer"]))
        ws.cell(23, 9).value = int(raw_odo) if raw_odo else None

    # Reclamação do Cliente / Relato do Scanner (A24:I26)
    if "complaint" in data and data["complaint"] is not None:
        ws.cell(24, 1).value = str(data["complaint"]).strip()
    if data.get("complaint_comment"):
        ws.cell(24, 1).comment = Comment(str(data["complaint_comment"]).strip(), "MecatroniCar")

    # 4. Itens de Peças e Serviços
    pecas = data.get("pecas_items")
    servicos = data.get("servicos_items")
    
    # Se recebeu uma lista genérica 'items', segrega automaticamente
    if pecas is None and servicos is None and "items" in data:
        all_items = data.get("items", [])
        pecas = [i for i in all_items if i.get("section") != "Serviço"]
        servicos = [i for i in all_items if i.get("section") == "Serviço"]
    else:
        pecas = pecas or []
        servicos = servicos or []

    # Peças: Linhas 30..43 (Máximo 14 itens na grade legada)
    sum_pecas = 0.0
    for idx in range(14):
        r = 30 + idx
        if idx < len(pecas):
            item = pecas[idx]
            desc = str(item.get("description") or item.get("desc", "")).strip()
            qty_raw = item.get("quantity") if "quantity" in item else item.get("qty")
            qty = float(qty_raw) if qty_raw not in (None, "") and _parse_currency_float(qty_raw) > 0 else (1.0 if desc else None)
            unit_price = _parse_currency_float(item.get("unit_price"))
            
            ws.cell(r, 1).value = desc
            ws.cell(r, 7).value = int(qty) if (qty is not None and qty.is_integer()) else qty
            ws.cell(r, 8).value = unit_price if (desc and unit_price > 0) else (unit_price if desc else None)
            
            tot_row = (qty or 0.0) * unit_price if desc else 0.0
            sum_pecas += tot_row
            cached_map[f"I{r}"] = tot_row
            
            # Comentário ou Cor na linha de peça
            if item.get("comment"):
                ws.cell(r, 1).comment = Comment(str(item["comment"]).strip(), "MecatroniCar")
            if item.get("color"):
                hex_color = item["color"].lstrip("#").upper()
                if len(hex_color) == 6:
                    fill = PatternFill(start_color="FF" + hex_color, end_color="FF" + hex_color, fill_type="solid")
                    for c_idx in range(1, 10):
                        ws.cell(r, c_idx).fill = fill
        else:
            ws.cell(r, 1).value = None
            ws.cell(r, 7).value = None
            ws.cell(r, 8).value = None
            cached_map[f"I{r}"] = 0.0

    # I44: Total Peças
    cached_map["I44"] = sum_pecas

    # Serviços: Linhas 47..50 (Máximo 4 itens na grade legada)
    sum_servicos = 0.0
    for idx in range(4):
        r = 47 + idx
        if idx < len(servicos):
            item = servicos[idx]
            desc = str(item.get("description") or item.get("desc", "")).strip()
            qty_raw = item.get("quantity") if "quantity" in item else item.get("qty")
            qty = float(qty_raw) if qty_raw not in (None, "") and _parse_currency_float(qty_raw) > 0 else (1.0 if desc and item.get("unit_price") else None)
            unit_price = _parse_currency_float(item.get("unit_price"))
            
            ws.cell(r, 1).value = desc
            ws.cell(r, 7).value = int(qty) if (qty is not None and qty.is_integer()) else qty
            ws.cell(r, 8).value = unit_price if (desc and unit_price > 0) else (unit_price if desc else None)
            
            tot_row = (qty or 0.0) * unit_price if (desc and qty) else (unit_price if desc else 0.0)
            sum_servicos += tot_row
            cached_map[f"I{r}"] = tot_row
            
            # Comentário ou Cor na linha de serviço
            if item.get("comment"):
                ws.cell(r, 1).comment = Comment(str(item["comment"]).strip(), "MecatroniCar")
            if item.get("color"):
                hex_color = item["color"].lstrip("#").upper()
                if len(hex_color) == 6:
                    fill = PatternFill(start_color="FF" + hex_color, end_color="FF" + hex_color, fill_type="solid")
                    for c_idx in range(1, 10):
                        ws.cell(r, c_idx).fill = fill
        else:
            ws.cell(r, 1).value = None
            ws.cell(r, 7).value = None
            ws.cell(r, 8).value = None
            cached_map[f"I{r}"] = 0.0

    # I51: Total Serviços
    cached_map["I51"] = sum_servicos

    # G51: Subtotal Geral (Peças + Serviços)
    subtotal_val = sum_pecas + sum_servicos
    cached_map["G51"] = subtotal_val

    # Desconto (G52)
    discount_val = _parse_currency_float(data.get("discount", 0.0))
    if discount_val > 0:
        ws.cell(52, 7).value = discount_val
        cached_map["G52"] = discount_val
    else:
        ws.cell(52, 7).value = None
        cached_map["G52"] = 0.0

    # Total Geral com Desconto (G53)
    total_final = max(0.0, subtotal_val - discount_val)
    cached_map["G53"] = total_final

    # 5. Forma de Pagamento (D54)
    if "payment_method" in data and data["payment_method"] is not None:
        ws.cell(54, 4).value = str(data["payment_method"]).strip()

    return wb, cached_map

# ==========================================
# SALVAMENTO COM PRESERVAÇÃO DE VALORES CACHEADOS
# ==========================================

def save_workbook_with_cached_formulas(wb, filepath, cached_map=None):
    """
    Salva a pasta de trabalho injetando tags <v> com o valor calculado das fórmulas.
    Isso segue estritamente a especificação OpenXML (ISO/IEC 29500) e permite que o openpyxl
    com data_only=True e o parser.py leiam os valores instantaneamente com 100% de precisão,
    sem obrigar os usuários a abrir e salvar no Excel antes.
    """
    if not cached_map:
        cached_map = {}

    orig_ws_write = openpyxl_ws_writer.write_cell

    def patched_write(xf, worksheet, cell, styled=False):
        c_val = cached_map.get(cell.coordinate)
        if cell.data_type == 'f' and c_val is not None:
            value, attributes = openpyxl_cell_writer._set_attributes(cell, styled)
            with xf.element('c', attributes):
                with xf.element('f'):
                    xf.write(value[1:])
                with xf.element('v'):
                    xf.write(openpyxl_cell_writer.safe_string(c_val))
        else:
            orig_ws_write(xf, worksheet, cell, styled)

    prev_write = openpyxl_ws_writer.write_cell
    openpyxl_ws_writer.write_cell = patched_write
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        wb.save(filepath)
    finally:
        openpyxl_ws_writer.write_cell = prev_write

    return filepath

# ==========================================
# API PRINCIPAL DE CRIAÇÃO E ATUALIZAÇÃO
# ==========================================

def save_os_spreadsheet(data, filepath=None, folder_path=None, auto_index=True, db_path=None):
    """
    Cria ou atualiza uma planilha de OS no padrão legado MecatroniCar.

    Parâmetros:
    - data: dict com as informações do cliente, veículo, OS, itens e totais.
    - filepath: caminho absoluto ou relativo do arquivo .xlsx. Se omitido, gera automaticamente
      na pasta oficial com o nome canônico 'PLACA - Nº_VISITA - Nome Cliente - Modelo - Cor.xlsx'.
    - folder_path: pasta destino caso filepath não seja fornecido (padrão: config.json).
    - auto_index: se True, sincroniza imediatamente com o banco SQLite oficina_cache.db.
    - db_path: caminho customizado do banco de cache (opcional).

    Retorna:
    dict com status de sucesso, caminho do arquivo e dados salvos.
    """
    plate = data.get("car_plate") or data.get("plate", "")
    visit_num = data.get("visit_num")
    client_name = data.get("client_name", "")
    car_model = data.get("car_model", "")
    car_color = data.get("car_color", "")

    # Se não foi fornecido visit_num, calcula automaticamente Visita N + 1
    if visit_num is None or str(visit_num).strip() == "":
        visit_num = get_next_visit_number(plate, folder_path=folder_path, db_path=db_path)
        data["visit_num"] = str(visit_num)

    # Determina o caminho do arquivo
    target_path = filepath
    if not target_path:
        dest_folder = folder_path
        if not dest_folder:
            cfg = config.load_config()
            dest_folder = cfg.get("spreadsheet_folder", "")
            if not dest_folder or not os.path.isdir(dest_folder):
                dest_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "planilhas_exemplo")

        canonical_name = generate_filename(plate, visit_num, client_name, car_model, car_color)
        target_path = os.path.join(dest_folder, canonical_name)

    # Abre arquivo existente ou cria nova pasta de trabalho a partir do template legado
    if os.path.exists(target_path):
        wb = openpyxl.load_workbook(target_path, data_only=False)
        # Garante que Plan1 possua as larguras e mesclagens oficiais
        build_legacy_template(wb)
    else:
        wb = build_legacy_template()

    # Preenche os dados e computa valores das fórmulas
    wb, cached_map = populate_workbook(wb, data)

    # Salva garantindo a estrutura OpenXML com fórmulas e valores cacheados
    save_workbook_with_cached_formulas(wb, target_path, cached_map)

    # Atualiza o índice do cache SQLite automaticamente, se solicitado
    index_res = None
    if auto_index:
        try:
            import cache
            cache_file = db_path or cache.get_db_path()
            conn = sqlite3.connect(cache_file)
            cur = conn.cursor()
            d_entry = {"file_path": target_path}
            d_res, updated = cache._ensure_row_parsed(conn, cur, d_entry)
            if updated:
                conn.commit()
            conn.close()
            index_res = True
        except Exception as e:
            index_res = False

    return {
        "success": True,
        "file_path": os.path.abspath(target_path),
        "file_name": os.path.basename(target_path),
        "plate": plate,
        "visit_num": str(visit_num),
        "cached_index_updated": index_res,
        "data": data
    }

def save_new_or_updated_os(payload=None, filepath=None, existing_filepath=None, target_folder=None, folder_path=None, auto_index=True, db_path=None, data=None, **kwargs):
    """
    Função facilitadora que aceita payloads em formato aninhado
    {'client': {...}, 'car': {...}, 'os': {...}, 'pecas': [...], 'servicos': [...], 'patio_status': '...'}
    ou formato plano, normalizando para save_os_spreadsheet.
    """
    input_data = payload if payload is not None else (data if data is not None else {})
    dest_dir = target_folder or folder_path or kwargs.get("folder") or kwargs.get("target_folder")
    target_fpath = filepath or existing_filepath or kwargs.get("existing_file_path")
    normalized = {}
    
    if "client" in input_data or "car" in input_data or "os" in input_data:
        client = input_data.get("client") or {}
        car = input_data.get("car") or {}
        os_info = input_data.get("os") or {}
        
        normalized["client_name"] = client.get("name") or client.get("client_name") or input_data.get("client_name", "")
        normalized["phone"] = client.get("phone") or input_data.get("phone", "")
        normalized["tel_res"] = client.get("tel_res") or input_data.get("tel_res", "")
        normalized["tel_com"] = client.get("tel_com") or input_data.get("tel_com", "")
        normalized["cpf"] = client.get("cpf") or input_data.get("cpf", "")
        normalized["rg"] = client.get("rg") or input_data.get("rg", "")
        normalized["address"] = client.get("address") or input_data.get("address", "")
        normalized["address_num"] = client.get("address_num") or input_data.get("address_num", "")
        normalized["address_compl"] = client.get("address_compl") or input_data.get("address_compl", "")
        normalized["neighborhood"] = client.get("neighborhood") or input_data.get("neighborhood", "")
        normalized["city"] = client.get("city") or input_data.get("city") or "Santos"
        normalized["cep"] = client.get("cep") or input_data.get("cep", "")
        normalized["email"] = client.get("email") or input_data.get("email", "")
        
        normalized["car_plate"] = car.get("plate") or car.get("car_plate") or input_data.get("car_plate") or input_data.get("plate", "")
        normalized["car_model"] = car.get("model") or car.get("car_model") or input_data.get("car_model", "")
        normalized["car_year"] = car.get("year") or car.get("car_year") or input_data.get("car_year", "")
        normalized["car_color"] = car.get("color") or car.get("car_color") or input_data.get("car_color", "")
        normalized["car_brand"] = car.get("brand") or car.get("car_brand") or input_data.get("car_brand", "")
        normalized["car_fuel"] = car.get("fuel") or car.get("car_fuel") or input_data.get("car_fuel", "")
        normalized["car_chassis"] = car.get("chassis") or car.get("car_chassis") or input_data.get("car_chassis", "")
        
        normalized["visit_num"] = os_info.get("visit_num") or input_data.get("visit_num", "")
        normalized["odometer"] = os_info.get("odometer") or input_data.get("odometer", "")
        normalized["complaint"] = os_info.get("complaint") or input_data.get("complaint", "")
        normalized["payment_method"] = os_info.get("payment_method") or input_data.get("payment_method", "")
        normalized["discount"] = os_info.get("discount") or input_data.get("discount", 0.0)
        normalized["entry_date"] = os_info.get("entry_date") or input_data.get("entry_date", "")
        normalized["entry_time"] = os_info.get("entry_time") or input_data.get("entry_time", "")
        normalized["exit_date"] = os_info.get("exit_date") or input_data.get("exit_date", "")
        normalized["exit_time"] = os_info.get("exit_time") or input_data.get("exit_time", "")
        
        pecas_raw = input_data.get("pecas") or input_data.get("pecas_items") or []
        servicos_raw = input_data.get("servicos") or input_data.get("servicos_items") or []
        
        normalized["pecas_items"] = [
            {
                "description": p.get("desc") or p.get("description", ""),
                "quantity": p.get("qty") if p.get("qty") is not None else p.get("quantity", 1),
                "unit_price": p.get("unit_price") if p.get("unit_price") is not None else p.get("unit_value", p.get("price", 0.0)),
                "color": p.get("color"),
                "comment": p.get("comment", "")
            }
            for p in pecas_raw
        ]
        normalized["servicos_items"] = [
            {
                "description": s.get("desc") or s.get("description", ""),
                "quantity": s.get("qty") if s.get("qty") is not None else s.get("quantity", 1),
                "unit_price": s.get("unit_price") if s.get("unit_price") is not None else s.get("unit_value", s.get("price", 0.0)),
                "color": s.get("color"),
                "comment": s.get("comment", "")
            }
            for s in servicos_raw
        ]
    else:
        normalized = dict(input_data)
        if "plate" in normalized and not normalized.get("car_plate"):
            normalized["car_plate"] = normalized["plate"]
        if "pecas" in normalized and "pecas_items" not in normalized:
            normalized["pecas_items"] = [
                {
                    "description": p.get("desc") or p.get("description", ""),
                    "quantity": p.get("qty") if p.get("qty") is not None else p.get("quantity", 1),
                    "unit_price": p.get("unit_price") if p.get("unit_price") is not None else p.get("unit_value", p.get("price", 0.0)),
                    "color": p.get("color"),
                    "comment": p.get("comment", "")
                }
                for p in normalized["pecas"]
            ]
        if "servicos" in normalized and "servicos_items" not in normalized:
            normalized["servicos_items"] = [
                {
                    "description": s.get("desc") or s.get("description", ""),
                    "quantity": s.get("qty") if s.get("qty") is not None else s.get("quantity", 1),
                    "unit_price": s.get("unit_price") if s.get("unit_price") is not None else s.get("unit_value", s.get("price", 0.0)),
                    "color": s.get("color"),
                    "comment": s.get("comment", "")
                }
                for s in normalized["servicos"]
            ]
        
    res = save_os_spreadsheet(
        data=normalized,
        filepath=target_fpath,
        folder_path=dest_dir,
        auto_index=auto_index,
        db_path=db_path
    )
    res["filename"] = res.get("file_name")
    
    # Atualiza status do pátio se fornecido
    patio_st = input_data.get("patio_status")
    if patio_st:
        try:
            import cache
            c_db = db_path or cache.get_db_path()
            cache.save_patio_car({
                "plate": normalized.get("car_plate", res.get("plate")),
                "client_name": normalized.get("client_name", ""),
                "car_model": normalized.get("car_model", ""),
                "car_color": normalized.get("car_color", ""),
                "status": patio_st,
                "notes": normalized.get("complaint", ""),
                "file_path": res["file_path"]
            }, c_db)
            cache.update_patio_status(
                file_path=res["file_path"],
                plate=res["plate"],
                status=patio_st,
                db_path=c_db
            )
        except Exception:
            pass
            
    return res


def save_order_to_excel(order_data, folder_path=None, existing_filepath=None, db_path=None, **kwargs):
    """
    Função oficial para salvar ordem de serviço diretamente no Excel e sincronizar com o banco SQLite.
    Compatível com os payloads e parâmetros enviados pela rota /api/save_order.
    """
    return save_new_or_updated_os(
        payload=order_data,
        target_folder=folder_path,
        existing_filepath=existing_filepath,
        db_path=db_path,
        **kwargs
    )


def get_next_visit_num(plate, db_path=None, folder_path=None):
    return get_next_visit_number(plate, folder_path=folder_path, db_path=db_path)


def get_client_vehicle_autocomplete(q, db_path=None):
    import cache
    cache_file = db_path or cache.get_db_path()
    results = cache.search_files(q, cache_file)
    suggestions = []
    seen = set()
    for r in results:
        p = r.get("plate_clean", "")
        if p and p not in seen:
            seen.add(p)
            det = r.get("details") or {}
            suggestions.append({
                "plate": r.get("plate_display") or r.get("plate"),
                "plate_clean": p,
                "client_name": r.get("client_name") or "",
                "car_model": r.get("car_model") or "",
                "car_year": r.get("car_year") or "",
                "car_color": r.get("car_color") or "",
                "phone": det.get("phone") or "",
                "address": det.get("address") or "",
                "address_num": det.get("address_num") or "",
                "address_compl": det.get("address_compl") or "",
                "neighborhood": det.get("neighborhood") or "",
                "city": det.get("city") or "Santos",
                "cep": det.get("cep") or "",
                "cpf": det.get("cpf") or "",
                "rg": det.get("rg") or "",
                "email": det.get("email") or "",
                "last_odometer": r.get("odometer") or "",
                "last_visit_num": r.get("visit_num") or "1"
            })
            if len(suggestions) >= 15:
                break
    return suggestions

