# -*- coding: utf-8 -*-
import os
import re
import datetime
import unicodedata
import openpyxl
import xlrd

def remove_accents(input_str):
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(input_str))
    return u"".join([c for c in nfkd if not unicodedata.combining(c)])

def clean_plate(plate_str):
    if not plate_str:
        return ""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(plate_str).upper())
    m = re.search(r'([A-Z]{3}[0-9][A-Z0-9][0-9]{2})', cleaned)
    if m:
        return m.group(1)
    return cleaned[:7]

def format_plate_display(plate_str):
    if not plate_str:
        return ""
    cleaned = clean_plate(plate_str)
    if len(cleaned) == 7:
        return f"{cleaned[:3]}-{cleaned[3:]}"
    return str(plate_str).strip()

def parse_filename(filename):
    """
    Examples:
    - 'FNB 1A77 -7 -  Danilo Pereira - VW Fox - Prata.xlsx'
    - 'EVI 2484 - 13 Cauê  Raquel (cunhados ) NovoDono - (Nissan ) Sentra - Prata.xls'
    - 'DTZ 9080 - 35 - NATANAEL novo dono - Partner - Branco.xls'
    - 'FQE 5724 - 4 - Natanael - Sentra - Prata.xls'
    """
    base_name = os.path.splitext(filename)[0].strip()
    
    # Try regex matching plate at beginning (supports space, hyphen, or contiguous)
    plate_match = re.search(r'^\s*([A-Za-z]{3}[\s\-]*[\dA-Za-z]{4})', base_name)
    if plate_match:
        plate = re.sub(r'[^A-Za-z0-9]', '', plate_match.group(1)).upper()
        remainder = base_name[plate_match.end():].strip()
        parts = [plate] + [p.strip() for p in remainder.split('-') if p.strip()]
    else:
        plate = ""
        parts = [p.strip() for p in base_name.split('-') if p.strip()]
    
    visit_num = ""
    owner = ""
    model = ""
    color = ""
    
    if len(parts) >= 2:
        v_match = re.match(r'^(\d+)\s*(.*)$', parts[1])
        if v_match:
            visit_num = v_match.group(1)
            rest_of_v = v_match.group(2).strip()
            if rest_of_v:
                owner = rest_of_v
                if len(parts) >= 3:
                    model = parts[2]
                if len(parts) >= 4:
                    color = parts[3]
            else:
                if len(parts) >= 3:
                    owner = parts[2]
                if len(parts) >= 4:
                    model = parts[3]
                if len(parts) >= 5:
                    color = parts[4]
        else:
            owner = parts[1]
            if len(parts) >= 3:
                model = parts[2]
            if len(parts) >= 4:
                color = parts[3]
                
    return {
        "filename": filename,
        "plate": plate,
        "visit_num": visit_num,
        "owner": owner,
        "model": model,
        "color": color
    }

def format_date_val(val, datemode=0):
    if val is None or val == "":
        return ""
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%d/%m/%Y")
    if isinstance(val, float) or isinstance(val, int):
        if 20000 < val < 70000:
            try:
                dt = xlrd.xldate_as_datetime(float(val), datemode)
                return dt.strftime("%d/%m/%Y")
            except Exception:
                pass
        return str(val)
    return str(val).strip()

def format_number_val(val):
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        if float(val).is_integer():
            return str(int(val))
        return f"{float(val):.2f}".replace(".", ",")
    return str(val).strip()

def format_currency_val(val):
    if val is None or val == "":
        return ""
    try:
        fval = float(str(val).replace(",", ".").replace("R$", "").strip())
        if fval == 0:
            return "R$ 0,00"
        return f"R$ {fval:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(val).strip()

def get_xlsx_color(cell):
    fill = cell.fill
    if not fill or not fill.fill_type or fill.fill_type == 'none':
        return None
    sc = fill.start_color
    if not sc or not sc.rgb:
        return None
    s = str(sc.rgb)
    if len(s) == 8:
        rgb = s[2:]
    elif len(s) == 6:
        rgb = s
    else:
        return None
    if rgb.upper() in ('000000', 'FFFFFF', '00000000', 'FFFFFFFF'):
        return None
    return '#' + rgb.lower()

def get_xls_color(wb, ws, r, c):
    xf = wb.xf_list[ws.cell_xf_index(r, c)]
    bg = xf.background.pattern_colour_index
    if bg in (64, 65, 0):
        return None
    rgb = wb.colour_map.get(bg)
    if rgb and rgb != (255, 255, 255) and rgb != (0, 0, 0):
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
    return None

def get_contrast_text_color(hex_color):
    if not hex_color or not hex_color.startswith('#') or len(hex_color) != 7:
        return '#1e293b'
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return '#ffffff' if lum < 135 else '#1e293b'
    except Exception:
        return '#1e293b'

def parse_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.xlsx':
        return parse_xlsx(filepath)
    elif ext == '.xls':
        return parse_xls(filepath)
    else:
        raise ValueError(f"Formato não suportado: {ext}")

def parse_xlsx(filepath):
    filename = os.path.basename(filepath)
    meta_fn = parse_filename(filename)
    
    wb = openpyxl.load_workbook(filepath, data_only=True)
    all_sheet_names = wb.sheetnames
    
    sheet_name = 'Plan1' if 'Plan1' in all_sheet_names else all_sheet_names[0]
    ws = wb[sheet_name]
    
    client_name = ""
    phone = ""
    car_brand = ""
    car_model = ""
    car_year = ""
    car_plate = ""
    car_color = ""
    car_fuel = ""
    car_chassis = ""
    
    entry_date = ""
    exit_date = ""
    odometer = ""
    complaint = ""
    
    complaint_comment = ""
    model_comment = ""
    plate_comment = ""
    
    subtotal = ""
    discount = ""
    total = ""
    
    rows_data = []
    
    max_r = min(ws.max_row, 80)
    max_c = min(ws.max_column, 15)
    
    pecas_row_idx = -1
    servico_row_idx = -1
    totais_row_idx = -1
    
    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            cell = ws.cell(r, c)
            val = str(cell.value or '').strip()
            val_clean = remove_accents(val).lower()
            
            if val_clean.startswith('nome:'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    client_name = str(c_val).strip()
            elif 'celular:' in val_clean:
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    phone = str(c_val).strip()
            elif val_clean.startswith('marca:'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    car_brand = str(c_val).strip()
            elif val_clean.startswith('modelo:'):
                c_cell = ws.cell(r, c + 1)
                if c_cell.value:
                    car_model = str(c_cell.value).strip()
                if c_cell.comment:
                    model_comment = c_cell.comment.text.strip()
            elif val_clean.startswith('ano:'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    car_year = format_number_val(c_val)
            elif val_clean.startswith('placa:'):
                c_cell = ws.cell(r, c + 1)
                if c_cell.value:
                    car_plate = str(c_cell.value).strip()
                if c_cell.comment:
                    plate_comment = c_cell.comment.text.strip()
            elif val_clean.startswith('cor:'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    car_color = str(c_val).strip()
            elif val_clean.startswith('combust.'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    car_fuel = str(c_val).strip()
            elif val_clean.startswith('chassi:'):
                c_val = ws.cell(r, c + 1).value
                if c_val:
                    car_chassis = str(c_val).strip()
            elif 'data de entrada:' in val_clean:
                for offset in (1, 2):
                    target = ws.cell(r, c + offset)
                    if target.value:
                        entry_date = format_date_val(target.value)
                        break
            elif 'data de saida:' in val_clean or 'data de saida :' in val_clean:
                for offset in (1, 2):
                    target = ws.cell(r, c + offset)
                    if target.value:
                        exit_date = format_date_val(target.value)
                        break
            elif 'hodometro:' in val_clean or 'odometro:' in val_clean:
                for offset in range(1, 4):
                    target = ws.cell(r, c + offset)
                    if target.value is not None and str(target.value).strip() != '':
                        odometer = format_number_val(target.value)
                        break
            elif val_clean in ('pecas', 'peças') and pecas_row_idx == -1 and r > 18:
                pecas_row_idx = r
            elif val_clean in ('servico', 'serviço', 'servicos', 'serviços') and servico_row_idx == -1 and r > 18:
                servico_row_idx = r
            elif 'subtotal:' in val_clean and totais_row_idx == -1 and r > 24:
                totais_row_idx = r
                for offset in range(1, 4):
                    target = ws.cell(r, c + offset)
                    if target.value is not None and str(target.value).strip() != '':
                        subtotal = format_currency_val(target.value)
                        break
            elif val_clean == 'total:' and r > 24:
                for offset in range(1, 4):
                    target = ws.cell(r, c + offset)
                    if target.value is not None and str(target.value).strip() != '':
                        total = format_currency_val(target.value)
                        break
            elif val_clean == 'desconto:' and r > 24:
                for offset in range(1, 4):
                    target = ws.cell(r, c + offset)
                    if target.value is not None and str(target.value).strip() != '':
                        discount = format_currency_val(target.value)
                        break

    for r in range(20, min(pecas_row_idx if pecas_row_idx != -1 else 30, max_r)):
        cell = ws.cell(r, 1)
        val = str(cell.value or '').strip()
        val_clean = remove_accents(val).lower()
        if val and not any(k in val_clean for k in ['ordem de servico', 'data de entrada', 'data de saida', 'hora:']):
            complaint = val
            if cell.comment:
                complaint_comment = cell.comment.text.strip()
            break

    start_r = pecas_row_idx + 1 if pecas_row_idx != -1 else 28
    end_r = totais_row_idx if totais_row_idx != -1 else max_r
    
    current_section = "Peças"
    
    for r in range(start_r, end_r + 1):
        if r == servico_row_idx:
            current_section = "Serviço"
            continue
        if r == totais_row_idx:
            break
            
        desc_cell = ws.cell(r, 1)
        desc_val = str(desc_cell.value or '').strip()
        
        if isinstance(desc_cell.value, (datetime.datetime, datetime.date)):
            desc_val = format_date_val(desc_cell.value)
        elif isinstance(desc_cell.value, (int, float)) and 20000 < desc_cell.value < 70000:
            desc_val = format_date_val(desc_cell.value)
            
        row_color = None
        row_comment = desc_cell.comment.text.strip() if desc_cell.comment else ""
        
        q_val = ""
        u_val = ""
        t_val = ""
        
        for c in range(1, max_c + 1):
            cell = ws.cell(r, c)
            c_color = get_xlsx_color(cell)
            if c_color and not row_color:
                row_color = c_color
            if cell.comment and not row_comment:
                row_comment = cell.comment.text.strip()
                
            if c == 7 and cell.value is not None:
                q_val = format_number_val(cell.value)
            elif c == 8 and cell.value is not None:
                u_val = format_currency_val(cell.value)
            elif c == 9 and cell.value is not None:
                t_val = format_currency_val(cell.value)

        if not desc_val and not row_comment and not row_color:
            continue
        if not desc_val and t_val in ("R$ 0,00", "0", "") and not row_comment and not row_color:
            continue

        rows_data.append({
            "section": current_section,
            "row_index": r,
            "description": desc_val,
            "quantity": q_val,
            "unit_price": u_val,
            "total_price": t_val,
            "color": row_color,
            "text_color": get_contrast_text_color(row_color),
            "comment": row_comment
        })

    extra_sheets_data = []
    for sec_name in all_sheet_names[1:]:
        try:
            sec_parsed = parse_secondary_xlsx_sheet(wb[sec_name], sec_name)
            if sec_parsed:
                extra_sheets_data.append(sec_parsed)
        except Exception:
            pass

    final_plate = car_plate or meta_fn.get("plate", "")
    final_owner = client_name or meta_fn.get("owner", "")
    final_model = car_model or meta_fn.get("model", "")
    final_color = car_color or meta_fn.get("color", "")
    final_visit = meta_fn.get("visit_num", "")

    return {
        "file_path": filepath,
        "file_name": filename,
        "file_size": os.path.getsize(filepath),
        "file_mtime": os.path.getmtime(filepath),
        "format": "xlsx",
        "sheets": all_sheet_names,
        "active_sheet": sheet_name,
        "extra_sheets_data": extra_sheets_data,
        "plate": final_plate,
        "plate_display": format_plate_display(final_plate),
        "plate_comment": plate_comment,
        "client_name": final_owner,
        "phone": phone,
        "car_brand": car_brand,
        "car_model": final_model,
        "model_comment": model_comment,
        "car_year": car_year,
        "car_color": final_color,
        "car_fuel": car_fuel,
        "car_chassis": car_chassis,
        "visit_num": final_visit,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "odometer": odometer,
        "complaint": complaint,
        "complaint_comment": complaint_comment,
        "items": rows_data,
        "subtotal": subtotal,
        "discount": discount,
        "total": total
    }

def parse_secondary_xlsx_sheet(ws, sheet_name):
    max_r = min(ws.max_row, 80)
    max_c = min(ws.max_column, 15)
    pecas_row_idx = -1
    servico_row_idx = -1
    totais_row_idx = -1
    subtotal = ""
    discount = ""
    total = ""
    title_notes = []

    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            val = str(ws.cell(r, c).value or "").strip()
            if not val:
                continue
            val_clean = remove_accents(val).lower()
            if val_clean in ("pecas", "peças") and pecas_row_idx == -1 and c <= 3:
                pecas_row_idx = r
            elif val_clean in ("servico", "serviço", "servicos", "serviços") and servico_row_idx == -1 and c <= 3:
                servico_row_idx = r
            elif "subtotal:" in val_clean and totais_row_idx == -1:
                totais_row_idx = r
                for offset in range(1, 4):
                    if c + offset <= max_c:
                        v = ws.cell(r, c + offset).value
                        if v is not None and str(v).strip() not in ("", "0", "0.0"):
                            subtotal = format_currency_val(v)
                            break
            elif val_clean == "total:":
                for offset in range(1, 4):
                    if c + offset <= max_c:
                        v = ws.cell(r, c + offset).value
                        if v is not None and str(v).strip() not in ("", "0", "0.0"):
                            total = format_currency_val(v)
                            break
            elif val_clean == "desconto:":
                for offset in range(1, 4):
                    if c + offset <= max_c:
                        v = ws.cell(r, c + offset).value
                        if v is not None and str(v).strip() not in ("", "0", "0.0"):
                            discount = format_currency_val(v)
                            break

    if pecas_row_idx != -1:
        for r in range(1, pecas_row_idx):
            for c in range(1, max_c + 1):
                v = str(ws.cell(r, c).value or "").strip()
                if v and remove_accents(v).lower() not in ("pecas", "quant.", "valor uni.", "valor tot."):
                    title_notes.append(v)

        items = []
        current_section = "Peças"
        end_r = totais_row_idx if totais_row_idx != -1 else max_r
        for r in range(pecas_row_idx + 1, end_r + 1):
            if r == servico_row_idx:
                current_section = "Serviço"
                continue
            if r == totais_row_idx:
                break

            desc_cell = ws.cell(r, 1)
            desc_val = str(desc_cell.value or "").strip()
            if isinstance(desc_cell.value, (datetime.datetime, datetime.date)):
                desc_val = format_date_val(desc_cell.value)

            row_color = None
            row_comment = desc_cell.comment.text.strip() if desc_cell.comment else ""
            q_val = ""
            u_val = ""
            t_val = ""

            for c in range(1, max_c + 1):
                cell = ws.cell(r, c)
                c_color = get_xlsx_color(cell)
                if c_color and not row_color:
                    row_color = c_color
                if cell.comment and not row_comment:
                    row_comment = cell.comment.text.strip()
                if c == 7 and cell.value is not None:
                    q_val = format_number_val(cell.value)
                elif c == 8 and cell.value is not None:
                    u_val = format_currency_val(cell.value)
                elif c == 9 and cell.value is not None:
                    t_val = format_currency_val(cell.value)

            if not desc_val and not row_comment:
                continue
            if desc_val.lower() in ("quant.", "valor uni.", "valor tot.", "subtotal:", "total:", "desconto:"):
                continue

            items.append({
                "section": current_section,
                "row_index": r,
                "description": desc_val,
                "quantity": q_val if q_val not in ("0", "0,00") else "",
                "unit_price": u_val if u_val not in ("R$ 0,00", "0") else "",
                "total_price": t_val if t_val not in ("R$ 0,00", "0") else "",
                "color": row_color,
                "text_color": get_contrast_text_color(row_color),
                "comment": row_comment
            })

        if not items and not title_notes and subtotal in ("", "R$ 0,00") and total in ("", "R$ 0,00"):
            return None

        return {
            "sheet_name": sheet_name,
            "title": " • ".join(title_notes),
            "items": items,
            "grid_rows": [],
            "subtotal": subtotal if subtotal != "R$ 0,00" else "",
            "discount": discount if discount != "R$ 0,00" else "",
            "total": total if total != "R$ 0,00" else ""
        }
    else:
        grid_rows = []
        for r in range(1, max_r + 1):
            row_cells = []
            has_text = False
            for c in range(1, max_c + 1):
                v = ws.cell(r, c).value
                s = str(v).strip() if v is not None else ""
                if s and s not in ("0", "0.0"):
                    has_text = True
                row_cells.append(s)
            if has_text:
                while row_cells and not row_cells[-1]:
                    row_cells.pop()
                while row_cells and not row_cells[0]:
                    row_cells.pop(0)
                if row_cells:
                    grid_rows.append(row_cells)
        if not grid_rows:
            return None
        return {
            "sheet_name": sheet_name,
            "title": "",
            "items": [],
            "grid_rows": grid_rows,
            "subtotal": "",
            "discount": "",
            "total": ""
        }

def parse_secondary_xls_sheet(wb, ws, sheet_name):
    nrows = min(ws.nrows, 80)
    ncols = min(ws.ncols, 15)
    pecas_row_idx = -1
    servico_row_idx = -1
    totais_row_idx = -1
    subtotal = ""
    discount = ""
    total = ""
    title_notes = []

    for r in range(nrows):
        for c in range(ncols):
            val = str(ws.cell_value(r, c) or "").strip()
            if not val:
                continue
            val_clean = remove_accents(val).lower()
            if val_clean in ("pecas", "peças") and pecas_row_idx == -1 and c <= 2:
                pecas_row_idx = r
            elif val_clean in ("servico", "serviço", "servicos", "serviços") and servico_row_idx == -1 and c <= 2:
                servico_row_idx = r
            elif "subtotal:" in val_clean and totais_row_idx == -1:
                totais_row_idx = r
                for offset in range(1, 4):
                    if c + offset < ncols:
                        v = ws.cell_value(r, c + offset)
                        if v != "" and str(v).strip() not in ("0", "0.0"):
                            subtotal = format_currency_val(v)
                            break
            elif val_clean == "total:":
                for offset in range(1, 4):
                    if c + offset < ncols:
                        v = ws.cell_value(r, c + offset)
                        if v != "" and str(v).strip() not in ("0", "0.0"):
                            total = format_currency_val(v)
                            break
            elif val_clean == "desconto:":
                for offset in range(1, 4):
                    if c + offset < ncols:
                        v = ws.cell_value(r, c + offset)
                        if v != "" and str(v).strip() not in ("0", "0.0"):
                            discount = format_currency_val(v)
                            break

    if pecas_row_idx != -1:
        for r in range(0, pecas_row_idx):
            for c in range(ncols):
                v = str(ws.cell_value(r, c) or "").strip()
                if v and remove_accents(v).lower() not in ("pecas", "quant.", "valor uni.", "valor tot."):
                    title_notes.append(v)

        items = []
        current_section = "Peças"
        end_r = totais_row_idx if totais_row_idx != -1 else nrows
        for r in range(pecas_row_idx + 1, end_r):
            if r == servico_row_idx:
                current_section = "Serviço"
                continue
            if r == totais_row_idx:
                break

            desc_raw = ws.cell_value(r, 0)
            desc_val = str(desc_raw or "").strip()
            if ws.cell_type(r, 0) == xlrd.XL_CELL_DATE:
                desc_val = format_date_val(desc_raw, wb.datemode)

            row_color = None
            note_0 = ws.cell_note_map.get((r, 0))
            row_comment = note_0.text.strip() if note_0 else ""
            q_val = ""
            u_val = ""
            t_val = ""

            for c in range(ncols):
                c_color = get_xls_color(wb, ws, r, c)
                if c_color and not row_color:
                    row_color = c_color
                n = ws.cell_note_map.get((r, c))
                if n and not row_comment:
                    row_comment = n.text.strip()
                if c == 6 and ws.cell_value(r, c) != "":
                    q_val = format_number_val(ws.cell_value(r, c))
                elif c == 7 and ws.cell_value(r, c) != "":
                    u_val = format_currency_val(ws.cell_value(r, c))
                elif c == 8 and ws.cell_value(r, c) != "":
                    t_val = format_currency_val(ws.cell_value(r, c))

            if not desc_val and not row_comment:
                continue
            if desc_val.lower() in ("quant.", "valor uni.", "valor tot.", "subtotal:", "total:", "desconto:"):
                continue

            items.append({
                "section": current_section,
                "row_index": r + 1,
                "description": desc_val,
                "quantity": q_val if q_val not in ("0", "0,00") else "",
                "unit_price": u_val if u_val not in ("R$ 0,00", "0") else "",
                "total_price": t_val if t_val not in ("R$ 0,00", "0") else "",
                "color": row_color,
                "text_color": get_contrast_text_color(row_color),
                "comment": row_comment
            })

        if not items and not title_notes and subtotal in ("", "R$ 0,00") and total in ("", "R$ 0,00"):
            return None

        return {
            "sheet_name": sheet_name,
            "title": " • ".join(title_notes),
            "items": items,
            "grid_rows": [],
            "subtotal": subtotal if subtotal != "R$ 0,00" else "",
            "discount": discount if discount != "R$ 0,00" else "",
            "total": total if total != "R$ 0,00" else ""
        }
    else:
        grid_rows = []
        for r in range(nrows):
            row_cells = []
            has_text = False
            for c in range(ncols):
                v = ws.cell_value(r, c)
                s = str(v).strip() if v is not None else ""
                if s and s not in ("0", "0.0"):
                    has_text = True
                row_cells.append(s)
            if has_text:
                while row_cells and not row_cells[-1]:
                    row_cells.pop()
                while row_cells and not row_cells[0]:
                    row_cells.pop(0)
                if row_cells:
                    grid_rows.append(row_cells)
        if not grid_rows:
            return None
        return {
            "sheet_name": sheet_name,
            "title": "",
            "items": [],
            "grid_rows": grid_rows,
            "subtotal": "",
            "discount": "",
            "total": ""
        }

def parse_xls(filepath):
    filename = os.path.basename(filepath)
    meta_fn = parse_filename(filename)
    
    wb = xlrd.open_workbook(filepath, formatting_info=True)
    all_sheet_names = wb.sheet_names()
    sheet_idx = 0
    ws = wb.sheet_by_index(sheet_idx)
    sheet_name = ws.name
    
    client_name = ""
    phone = ""
    car_brand = ""
    car_model = ""
    car_year = ""
    car_plate = ""
    car_color = ""
    car_fuel = ""
    car_chassis = ""
    
    entry_date = ""
    exit_date = ""
    odometer = ""
    complaint = ""
    
    complaint_comment = ""
    model_comment = ""
    plate_comment = ""
    
    subtotal = ""
    discount = ""
    total = ""
    
    rows_data = []
    
    pecas_row_idx = -1
    servico_row_idx = -1
    totais_row_idx = -1
    
    nrows = min(ws.nrows, 80)
    ncols = min(ws.ncols, 15)
    
    for r in range(nrows):
        for c in range(ncols):
            val = str(ws.cell_value(r, c) or '').strip()
            val_clean = remove_accents(val).lower()
            
            note_obj = ws.cell_note_map.get((r, c))
            cell_comment = note_obj.text.strip() if note_obj else ""
            
            if val_clean.startswith('nome:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    client_name = str(ws.cell_value(r, c + 1)).strip()
            elif 'celular:' in val_clean:
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    phone = str(ws.cell_value(r, c + 1)).strip()
            elif val_clean.startswith('marca:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_brand = str(ws.cell_value(r, c + 1)).strip()
            elif val_clean.startswith('modelo:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_model = str(ws.cell_value(r, c + 1)).strip()
                if c + 1 < ncols:
                    n = ws.cell_note_map.get((r, c + 1))
                    if n:
                        model_comment = n.text.strip()
            elif val_clean.startswith('ano:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_year = format_number_val(ws.cell_value(r, c + 1))
            elif val_clean.startswith('placa:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_plate = str(ws.cell_value(r, c + 1)).strip()
                if c + 1 < ncols:
                    n = ws.cell_note_map.get((r, c + 1))
                    if n:
                        plate_comment = n.text.strip()
            elif val_clean.startswith('cor:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_color = str(ws.cell_value(r, c + 1)).strip()
            elif val_clean.startswith('combust.'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_fuel = str(ws.cell_value(r, c + 1)).strip()
            elif val_clean.startswith('chassi:'):
                if c + 1 < ncols and ws.cell_value(r, c + 1):
                    car_chassis = str(ws.cell_value(r, c + 1)).strip()
            elif 'data de entrada:' in val_clean or 'data de entrada' in val_clean:
                for offset in (1, 2):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        entry_date = format_date_val(ws.cell_value(r, c + offset), wb.datemode)
                        break
            elif 'data de saida:' in val_clean or 'data de saida' in val_clean:
                for offset in (1, 2):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        exit_date = format_date_val(ws.cell_value(r, c + offset), wb.datemode)
                        break
            elif 'hodometro:' in val_clean or 'odometro:' in val_clean:
                for offset in range(1, 4):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        odometer = format_number_val(ws.cell_value(r, c + offset))
                        break
            elif val_clean in ('pecas', 'peças') and pecas_row_idx == -1 and r > 18:
                pecas_row_idx = r
            elif val_clean in ('servico', 'serviço', 'servicos', 'serviços') and servico_row_idx == -1 and r > 18:
                servico_row_idx = r
            elif 'subtotal:' in val_clean and totais_row_idx == -1 and r > 24:
                totais_row_idx = r
                for offset in range(1, 4):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        subtotal = format_currency_val(ws.cell_value(r, c + offset))
                        break
            elif val_clean == 'total:' and r > 24:
                for offset in range(1, 4):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        total = format_currency_val(ws.cell_value(r, c + offset))
                        break
            elif val_clean == 'desconto:' and r > 24:
                for offset in range(1, 4):
                    if c + offset < ncols and ws.cell_value(r, c + offset) != '':
                        discount = format_currency_val(ws.cell_value(r, c + offset))
                        break

    for r in range(19, min(pecas_row_idx if pecas_row_idx != -1 else 28, nrows)):
        val = str(ws.cell_value(r, 0) or '').strip()
        val_clean = remove_accents(val).lower()
        if val and not any(k in val_clean for k in ['ordem de servico', 'data de entrada', 'data de saida', 'hora:']):
            complaint = val
            note_obj = ws.cell_note_map.get((r, 0))
            if note_obj:
                complaint_comment = note_obj.text.strip()
            break

    start_r = pecas_row_idx + 1 if pecas_row_idx != -1 else 27
    end_r = totais_row_idx if totais_row_idx != -1 else nrows
    
    current_section = "Peças"
    
    for r in range(start_r, end_r):
        if r == servico_row_idx:
            current_section = "Serviço"
            continue
        if r == totais_row_idx:
            break
            
        desc_raw = ws.cell_value(r, 0)
        desc_val = str(desc_raw or '').strip()
        
        if ws.cell_type(r, 0) == xlrd.XL_CELL_DATE:
            desc_val = format_date_val(desc_raw, wb.datemode)
        elif isinstance(desc_raw, (int, float)) and 20000 < desc_raw < 70000:
            desc_val = format_date_val(desc_raw, wb.datemode)
            
        row_color = None
        row_comment = ""
        
        note_0 = ws.cell_note_map.get((r, 0))
        if note_0:
            row_comment = note_0.text.strip()
            
        q_val = ""
        u_val = ""
        t_val = ""
        
        for c in range(ncols):
            c_color = get_xls_color(wb, ws, r, c)
            if c_color and not row_color:
                row_color = c_color
                
            n = ws.cell_note_map.get((r, c))
            if n and not row_comment:
                row_comment = n.text.strip()
                
            if c == 6 and ws.cell_value(r, c) != '':
                q_val = format_number_val(ws.cell_value(r, c))
            elif c == 7 and ws.cell_value(r, c) != '':
                u_val = format_currency_val(ws.cell_value(r, c))
            elif c == 8 and ws.cell_value(r, c) != '':
                t_val = format_currency_val(ws.cell_value(r, c))

        if not desc_val and not row_comment and not row_color:
            continue
        if not desc_val and t_val in ("R$ 0,00", "0", "0.0", "") and not row_comment and not row_color:
            continue

        rows_data.append({
            "section": current_section,
            "row_index": r + 1,
            "description": desc_val,
            "quantity": q_val,
            "unit_price": u_val,
            "total_price": t_val,
            "color": row_color,
            "text_color": get_contrast_text_color(row_color),
            "comment": row_comment
        })

    extra_sheets_data = []
    for sec_idx in range(1, len(all_sheet_names)):
        try:
            sec_ws = wb.sheet_by_index(sec_idx)
            sec_parsed = parse_secondary_xls_sheet(wb, sec_ws, sec_ws.name)
            if sec_parsed:
                extra_sheets_data.append(sec_parsed)
        except Exception:
            pass

    final_plate = car_plate or meta_fn.get("plate", "")
    final_owner = client_name or meta_fn.get("owner", "")
    final_model = car_model or meta_fn.get("model", "")
    final_color = car_color or meta_fn.get("color", "")
    final_visit = meta_fn.get("visit_num", "")

    return {
        "file_path": filepath,
        "file_name": filename,
        "file_size": os.path.getsize(filepath),
        "file_mtime": os.path.getmtime(filepath),
        "format": "xls",
        "sheets": all_sheet_names,
        "active_sheet": sheet_name,
        "extra_sheets_data": extra_sheets_data,
        "plate": final_plate,
        "plate_display": format_plate_display(final_plate),
        "plate_comment": plate_comment,
        "client_name": final_owner,
        "phone": phone,
        "car_brand": car_brand,
        "car_model": final_model,
        "model_comment": model_comment,
        "car_year": car_year,
        "car_color": final_color,
        "car_fuel": car_fuel,
        "car_chassis": car_chassis,
        "visit_num": final_visit,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "odometer": odometer,
        "complaint": complaint,
        "complaint_comment": complaint_comment,
        "items": rows_data,
        "subtotal": subtotal,
        "discount": discount,
        "total": total
    }

