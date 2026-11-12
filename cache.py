# -*- coding: utf-8 -*-
import os
import sqlite3
import json
import re
import datetime
from parser import parse_file, parse_filename, remove_accents, clean_plate, format_plate_display, PARSER_VERSION, parse_currency_float

DB_FILE = "oficina_cache.db"
FAST_INDEX_THRESHOLD = 15

def get_db_path(base_dir=None):
    if base_dir:
        return os.path.join(base_dir, DB_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILE)

PATIO_STATUSES = [
    "Em Diagnostico",
    "Esperando Orcamento",
    "Esperando Aprovacao",
    "Esperando Pecas",
    "Em Execucao",
    "Esperando Cliente",
    "Liberado Terceiro"
]

VALID_PATIO_STATUSES = PATIO_STATUSES

PATIO_STATUSES_DISPLAY = [
    "Em Diagnóstico",
    "Esperando Orçamento",
    "Esperando Aprovação",
    "Esperando Peças",
    "Em Execução",
    "Esperando Cliente Buscar",
    "Liberado p/ Retirada por Terceiro"
]

STATUS_DISPLAY_MAP = {
    "Em Diagnostico": "Em Diagnóstico",
    "Esperando Orcamento": "Esperando Orçamento",
    "Esperando Aprovacao": "Esperando Aprovação",
    "Esperando Pecas": "Esperando Peças",
    "Em Execucao": "Em Execução",
    "Esperando Cliente": "Esperando Cliente Buscar",
    "Esperando Cliente Buscar": "Esperando Cliente Buscar",
    "Liberado Terceiro": "Liberado p/ Retirada por Terceiro",
    "Liberado p/ Retirada por Terceiro": "Liberado p/ Retirada por Terceiro"
}

VALID_NF_STATUSES = [
    "Pendente",
    "Emitida",
    "Cancelada",
    "Nao Aplicavel"
]

def normalize_patio_status(status_str):
    if not status_str:
        return "Em Diagnostico"
    s_raw = str(status_str).strip()
    s = remove_accents(s_raw).lower()
    mapping = {
        "em diagnostico": "Em Diagnostico",
        "esperando orcamento": "Esperando Orcamento",
        "esperando aprovacao": "Esperando Aprovacao",
        "esperando pecas": "Esperando Pecas",
        "em execucao": "Em Execucao",
        "esperando cliente": "Esperando Cliente",
        "esperando cliente buscar": "Esperando Cliente",
        "pronto": "Esperando Cliente",
        "pronto / esperando cliente": "Esperando Cliente",
        "liberado terceiro": "Liberado p/ Retirada por Terceiro",
        "liberado p/ retirada por terceiro": "Liberado p/ Retirada por Terceiro",
        "liberado para retirada por terceiro": "Liberado p/ Retirada por Terceiro"
    }
    return mapping.get(s, s_raw)

def _setup_patio_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patio_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        plate TEXT,
        plate_clean TEXT,
        status TEXT DEFAULT 'Em Diagnostico',
        mechanic_name TEXT,
        third_party_name TEXT,
        third_party_doc TEXT,
        updated_at TEXT,
        notes TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patio_plate ON patio_status(plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patio_file_path ON patio_status(file_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patio_status ON patio_status(status)")

def _setup_nf_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS nf_control (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        plate_clean TEXT,
        visit_num TEXT,
        nfse_status TEXT DEFAULT 'Pendente',
        nfse_number TEXT DEFAULT '',
        nfe_status TEXT DEFAULT 'Pendente',
        nfe_number TEXT DEFAULT '',
        updated_at TEXT,
        notes TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_file_path ON nf_control(file_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_plate ON nf_control(plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_plate_visit ON nf_control(plate_clean, visit_num)")

def init_db(db_path=None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        file_path TEXT PRIMARY KEY,
        file_name TEXT,
        file_mtime REAL,
        file_size INTEGER,
        plate TEXT,
        plate_clean TEXT,
        plate_display TEXT,
        client_name TEXT,
        client_clean TEXT,
        car_model TEXT,
        car_year TEXT,
        car_color TEXT,
        visit_num TEXT,
        entry_date TEXT,
        entry_date_sort TEXT,
        odometer TEXT,
        odometer_int INTEGER,
        complaint TEXT,
        data_json TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plate_clean ON files(plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_client_clean ON files(client_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entry_date_sort ON files(entry_date_sort)")

    # Estruturas do CP-01 (patio_status, nf_control e templates)
    _setup_patio_table(cur)
    _setup_nf_table(cur)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        content TEXT,
        updated_at TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_template_name ON templates(name)")

    conn.commit()
    conn.close()

def parse_date_sortable(date_str):
    if not date_str:
        return "0000-00-00"
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', date_str.strip())
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"
    return "0000-00-00"

def parse_odometer_int(odometer_str):
    if not odometer_str:
        return 0
    cleaned = re.sub(r'[^\d]', '', str(odometer_str))
    try:
        return int(cleaned)
    except Exception:
        return 0

def parse_visit_int(visit_str):
    if not visit_str:
        return 0
    cleaned = re.sub(r'[^\d]', '', str(visit_str))
    try:
        return int(cleaned)
    except Exception:
        return 0

def _ensure_row_parsed(conn, cur, d):
    """
    Se a planilha foi indexada apenas pelo nome do arquivo (modo ultrarrápido),
    lê o conteúdo interno do Excel sob demanda (apenas quando buscada/aberta)
    e salva o resultado no banco SQLite para as próximas consultas.
    """
    fpath = d.get("file_path", "")
    if d.get("data_json"):
        try:
            loaded = json.loads(d["data_json"])
            if loaded.get("parser_version") == PARSER_VERSION and "servicos_items" in loaded:
                d["details"] = loaded
                return d, False
        except Exception:
            pass

    if not fpath or not os.path.exists(fpath):
        d["details"] = None
        return d, False

    try:
        mtime = os.path.getmtime(fpath)
        fsize = os.path.getsize(fpath)
        parsed = parse_file(fpath)

        plate_raw = parsed.get("plate", "") or d.get("plate", "")
        plate_clean = clean_plate(plate_raw)
        plate_display = parsed.get("plate_display", "") or format_plate_display(plate_raw)
        client_name = parsed.get("client_name", "") or d.get("client_name", "")
        client_clean = remove_accents(client_name).lower()
        car_model = parsed.get("car_model", "") or d.get("car_model", "")
        car_year = parsed.get("car_year", "") or d.get("car_year", "")
        car_color = parsed.get("car_color", "") or d.get("car_color", "")
        visit_num = parsed.get("visit_num", "") or d.get("visit_num", "")
        entry_date = parsed.get("entry_date", "")
        entry_date_sort = parse_date_sortable(entry_date)
        odometer = parsed.get("odometer", "")
        odometer_int = parse_odometer_int(odometer)
        complaint = parsed.get("complaint", "")
        data_json = json.dumps(parsed, ensure_ascii=False)

        cur.execute("""
        INSERT OR REPLACE INTO files (
            file_path, file_name, file_mtime, file_size,
            plate, plate_clean, plate_display, client_name, client_clean,
            car_model, car_year, car_color, visit_num,
            entry_date, entry_date_sort, odometer, odometer_int,
            complaint, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fpath, parsed.get("file_name", os.path.basename(fpath)), mtime, fsize,
            plate_raw, plate_clean, plate_display, client_name, client_clean,
            car_model, car_year, car_color, visit_num,
            entry_date, entry_date_sort, odometer, odometer_int,
            complaint, data_json
        ))

        d.update({
            "plate": plate_raw,
            "plate_clean": plate_clean,
            "plate_display": plate_display,
            "client_name": client_name,
            "car_model": car_model,
            "car_year": car_year,
            "car_color": car_color,
            "visit_num": visit_num,
            "entry_date": entry_date,
            "entry_date_sort": entry_date_sort,
            "odometer": odometer,
            "odometer_int": odometer_int,
            "complaint": complaint,
            "data_json": data_json,
            "details": parsed
        })
        return d, True
    except Exception:
        d["details"] = None
        return d, False

def scan_and_index_folder(folder_path, db_path=None, progress_callback=None):
    if not folder_path or not os.path.isdir(folder_path):
        return {"error": "Pasta inválida", "indexed": 0, "total": 0}
        
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    # Collect all xlsx and xls files
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.startswith("~$"):  # Excel temporary file
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.xlsx', '.xls'):
                all_files.append(os.path.join(root, f))
                
    total_files = len(all_files)
    indexed_count = 0
    errors = []
    
    # Check existing mtimes and parser_version in batch
    cur.execute("SELECT file_path, file_mtime, data_json FROM files")
    cached_mtimes = {}
    for row_fp, row_mt, row_dj in cur.fetchall():
        is_current_schema = True
        if row_dj:
            try:
                is_current_schema = json.loads(row_dj).get("parser_version") == PARSER_VERSION
            except Exception:
                is_current_schema = False
        if is_current_schema:
            cached_mtimes[row_fp] = row_mt
    
    to_process = []
    for fpath in all_files:
        try:
            mtime = os.path.getmtime(fpath)
            if fpath in cached_mtimes and abs(cached_mtimes[fpath] - mtime) < 0.01:
                continue
            to_process.append((fpath, mtime, os.path.getsize(fpath)))
        except Exception as e:
            errors.append(f"{os.path.basename(fpath)}: {str(e)}")

    # Se houver muitas planilhas novas (ex.: milhares de fichas na pasta da oficina),
    # faz a indexação instantânea pelo nome do arquivo (< 0,1s) e lê o Excel sob demanda na busca!
    use_fast_filename_index = len(to_process) > FAST_INDEX_THRESHOLD

    for idx, (fpath, mtime, fsize) in enumerate(to_process):
        try:
            fname = os.path.basename(fpath)
            if use_fast_filename_index:
                meta = parse_filename(fname)
                plate_raw = meta.get("plate", "")
                plate_clean = clean_plate(plate_raw)
                plate_display = format_plate_display(plate_raw)
                client_name = meta.get("owner", "")
                client_clean = remove_accents(client_name).lower()
                car_model = meta.get("model", "")
                car_color = meta.get("color", "")
                visit_num = meta.get("visit_num", "")

                cur.execute("""
                INSERT OR REPLACE INTO files (
                    file_path, file_name, file_mtime, file_size,
                    plate, plate_clean, plate_display, client_name, client_clean,
                    car_model, car_year, car_color, visit_num,
                    entry_date, entry_date_sort, odometer, odometer_int,
                    complaint, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fpath, fname, mtime, fsize,
                    plate_raw, plate_clean, plate_display, client_name, client_clean,
                    car_model, "", car_color, visit_num,
                    "", "0000-00-00", "", 0,
                    "", ""
                ))
            else:
                parsed = parse_file(fpath)
                plate_raw = parsed.get("plate", "")
                plate_clean = clean_plate(plate_raw)
                plate_display = parsed.get("plate_display", "")
                client_name = parsed.get("client_name", "")
                client_clean = remove_accents(client_name).lower()
                entry_date = parsed.get("entry_date", "")
                entry_date_sort = parse_date_sortable(entry_date)
                odometer = parsed.get("odometer", "")
                odometer_int = parse_odometer_int(odometer)
                data_json = json.dumps(parsed, ensure_ascii=False)

                cur.execute("""
                INSERT OR REPLACE INTO files (
                    file_path, file_name, file_mtime, file_size,
                    plate, plate_clean, plate_display, client_name, client_clean,
                    car_model, car_year, car_color, visit_num,
                    entry_date, entry_date_sort, odometer, odometer_int,
                    complaint, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fpath, parsed.get("file_name", fname), mtime, fsize,
                    plate_raw, plate_clean, plate_display, client_name, client_clean,
                    parsed.get("car_model", ""), parsed.get("car_year", ""), parsed.get("car_color", ""), parsed.get("visit_num", ""),
                    entry_date, entry_date_sort, odometer, odometer_int,
                    parsed.get("complaint", ""), data_json
                ))

            indexed_count += 1
            if progress_callback:
                progress_callback(idx + 1, len(to_process), fname)
        except Exception as e:
            errors.append(f"{os.path.basename(fpath)}: {str(e)}")
            
    # Clean up deleted files from database
    existing_paths_set = set(all_files)
    for cached_path in cached_mtimes:
        if cached_path not in existing_paths_set:
            cur.execute("DELETE FROM files WHERE file_path = ?", (cached_path,))
            
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "total": total_files,
        "indexed": indexed_count,
        "fast_mode": use_fast_filename_index,
        "errors": errors
    }

def get_stats(db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM files")
    total_files = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT plate_clean) FROM files WHERE plate_clean != ''")
    total_cars = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT client_clean) FROM files WHERE client_clean != ''")
    total_clients = cur.fetchone()[0]
    
    conn.close()
    return {
        "total_files": total_files,
        "total_cars": total_cars,
        "total_clients": total_clients
    }

def get_all_cars(db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
    SELECT 
        plate_clean,
        plate_display,
        client_name,
        car_model,
        car_year,
        car_color,
        COUNT(*) as visit_count,
        MAX(entry_date_sort) as latest_date_sort,
        MAX(odometer_int) as latest_odometer
    FROM files
    WHERE plate_clean != ''
    GROUP BY plate_clean
    ORDER BY latest_date_sort DESC, plate_clean ASC
    """)
    
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results

def search_files(query, db_path=None):
    if not query or not query.strip():
        return []
        
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    query_raw = query.strip()
    query_clean = remove_accents(query_raw).lower()
    query_plate = clean_plate(query_raw)
    
    like_query = f"%{query_clean}%"
    
    cur.execute("""
    SELECT 
        file_path, file_name, plate, plate_clean, plate_display,
        client_name, car_model, car_year, car_color, visit_num,
        entry_date, entry_date_sort, odometer, odometer_int,
        complaint, data_json
    FROM files
    WHERE 
        plate_clean LIKE ? OR
        (? != '' AND plate_clean LIKE ?) OR
        client_clean LIKE ? OR
        LOWER(car_model) LIKE ? OR
        LOWER(file_name) LIKE ? OR
        LOWER(complaint) LIKE ?
    ORDER BY entry_date_sort DESC, odometer_int DESC, CAST(visit_num AS INTEGER) DESC
    LIMIT 60
    """, (
        f"%{query_clean.upper()}%",
        query_plate, f"%{query_plate}%" if query_plate else "%",
        like_query, like_query, like_query, like_query
    ))
    
    rows = [dict(r) for r in cur.fetchall()]
    unique_plates = {r.get("plate_clean") for r in rows if r.get("plate_clean")}

    # Se a busca já filtrou um único veículo (ou poucos arquivos), lê sob demanda as planilhas encontradas
    max_lazy_parse = len(rows) if len(unique_plates) <= 1 else min(len(rows), 20)
    dirty = False
    results = []
    for idx, d in enumerate(rows):
        if idx < max_lazy_parse:
            d, updated = _ensure_row_parsed(conn, cur, d)
            if updated:
                dirty = True
        else:
            if d.get("data_json"):
                try:
                    d["details"] = json.loads(d["data_json"])
                except Exception:
                    d["details"] = None
            else:
                d["details"] = None
        results.append(d)

    if dirty:
        conn.commit()
    conn.close()

    results.sort(
        key=lambda x: (
            x.get("entry_date_sort") or "0000-00-00",
            x.get("odometer_int") or 0,
            parse_visit_int(x.get("visit_num"))
        ),
        reverse=True
    )
    return results

def get_car_history(plate, db_path=None):
    if not plate:
        return []
        
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    p_clean = clean_plate(plate)
    
    cur.execute("""
    SELECT 
        file_path, file_name, plate, plate_clean, plate_display,
        client_name, car_model, car_year, car_color, visit_num,
        entry_date, entry_date_sort, odometer, odometer_int,
        complaint, data_json
    FROM files
    WHERE plate_clean = ? OR plate_clean LIKE ?
    ORDER BY entry_date_sort DESC, odometer_int DESC, CAST(visit_num AS INTEGER) DESC
    """, (p_clean, f"%{p_clean}%"))
    
    rows = [dict(r) for r in cur.fetchall()]
    results = []
    dirty = False
    for d in rows:
        d, updated = _ensure_row_parsed(conn, cur, d)
        if updated:
            dirty = True
        results.append(d)
        
    if dirty:
        conn.commit()
    conn.close()

    results.sort(
        key=lambda x: (
            x.get("entry_date_sort") or "0000-00-00",
            x.get("odometer_int") or 0,
            parse_visit_int(x.get("visit_num"))
        ),
        reverse=True
    )

    for d in results:
        d["nf_control"] = get_nf_control(file_path=d.get("file_path"), plate_clean=d.get("plate_clean"), visit_num=d.get("visit_num"), db_path=path)

    return results

# ==============================================================================
# GESTÃO DO PÁTIO DA OFICINA (patio_status) - CP-01
# ==============================================================================

def _format_patio_dict(row_dict):
    """
    Padroniza o dicionário de pátio garantindo apelidos e campos esperados pela interface.
    """
    if not row_dict:
        return None
    d = dict(row_dict)
    d.setdefault("box_mecanico", d.get("mechanic_name", ""))
    d.setdefault("authorized_name", d.get("third_party_name", ""))
    d.setdefault("authorized_doc", d.get("third_party_doc", ""))
    d.setdefault("authorized_phone", d.get("third_party_phone", ""))
    d.setdefault("updated_time", d.get("updated_at", ""))
    display = STATUS_DISPLAY_MAP.get(d.get("status"), d.get("status"))
    d["status_display"] = display
    d["status_key"] = d.get("status")
    d["status"] = d.get("status")
    row_dict.clear()
    row_dict.update(d)
    return row_dict

def list_patio_status(status=None, db_path=None):
    """
    Lista veículos no pátio com status operacional e dados cadastrais enriquecidos do veículo.
    Pode filtrar por status específico ou coleção de status.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
    SELECT 
        p.id,
        p.file_path,
        p.plate,
        p.plate_clean,
        p.status,
        p.mechanic_name,
        p.third_party_name,
        p.third_party_doc,
        '' AS third_party_phone,
        f.client_name AS client_name,
        f.car_model AS car_model,
        f.car_color AS car_color,
        p.updated_at,
        p.notes,
        f.car_year,
        f.plate_display,
        f.entry_date,
        f.odometer
    FROM patio_status p
    LEFT JOIN files f ON (p.file_path IS NOT NULL AND p.file_path != '' AND p.file_path = f.file_path)
    """
    params = []
    if status:
        if isinstance(status, (list, tuple, set)):
            norm_statuses = [normalize_patio_status(s) for s in status]
            placeholders = ",".join(["?"] * len(norm_statuses))
            query += f" WHERE p.status IN ({placeholders})"
            params.extend(norm_statuses)
        else:
            query += " WHERE p.status = ?"
            params.append(normalize_patio_status(status))

    query += " ORDER BY p.updated_at DESC, p.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        if not row.get("client_name") and row.get("plate_clean"):
            cur.execute("""
            SELECT client_name, car_model, car_year, car_color, plate_display, entry_date, odometer
            FROM files
            WHERE plate_clean = ?
            ORDER BY entry_date_sort DESC, odometer_int DESC
            LIMIT 1
            """, (row["plate_clean"],))
            f_match = cur.fetchone()
            if f_match:
                for k, v in dict(f_match).items():
                    if not row.get(k):
                        row[k] = v
        if not row.get("plate_display") and row.get("plate"):
            row["plate_display"] = format_plate_display(row["plate"])
        _format_patio_dict(row)

    conn.close()
    return rows

def get_patio_status(id=None, file_path=None, plate=None, db_path=None):
    """
    Obtém um registro do status do pátio por id, file_path ou placa.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = None
    if id is not None:
        cur.execute("SELECT * FROM patio_status WHERE id = ?", (id,))
        row = cur.fetchone()
    elif file_path:
        cur.execute("SELECT * FROM patio_status WHERE file_path = ?", (file_path,))
        row = cur.fetchone()
    elif plate:
        p_clean = clean_plate(plate)
        cur.execute("SELECT * FROM patio_status WHERE plate_clean = ? ORDER BY updated_at DESC, id DESC LIMIT 1", (p_clean,))
        row = cur.fetchone()

    if not row:
        conn.close()
        return None

    res = dict(row)
    if res.get("file_path"):
        cur.execute("SELECT client_name, car_model, car_year, car_color, plate_display, entry_date, odometer FROM files WHERE file_path = ?", (res["file_path"],))
        f_match = cur.fetchone()
        if f_match:
            for k, v in dict(f_match).items():
                res.setdefault(k, v)
    if not res.get("client_name") and res.get("plate_clean"):
        cur.execute("""
        SELECT client_name, car_model, car_year, car_color, plate_display, entry_date, odometer
        FROM files WHERE plate_clean = ? ORDER BY entry_date_sort DESC LIMIT 1
        """, (res["plate_clean"],))
        f_match = cur.fetchone()
        if f_match:
            for k, v in dict(f_match).items():
                if not res.get(k):
                    res[k] = v

    if not res.get("plate_display") and res.get("plate"):
        res["plate_display"] = format_plate_display(res["plate"])
    _format_patio_dict(res)

    conn.close()
    return res

def update_patio_status(
    file_path=None,
    plate=None,
    status=None,
    mechanic_name=None,
    third_party_name=None,
    third_party_doc=None,
    third_party_phone=None,
    client_name=None,
    car_model=None,
    car_color=None,
    notes=None,
    record_id=None,
    id=None,
    updated_at=None,
    db_path=None,
    **kwargs
):
    """
    Cria ou atualiza o status de pátio de um veículo (upsert).
    Pode identificar por record_id (ou id), file_path ou placa.
    Suporta apelidos legados como box_mecanico, authorized_name, authorized_doc via kwargs.
    """
    rec_id = record_id if record_id is not None else id
    mechanic = mechanic_name if mechanic_name is not None else kwargs.get("box_mecanico")
    third_name = third_party_name if third_party_name is not None else kwargs.get("authorized_name")
    third_doc = third_party_doc if third_party_doc is not None else kwargs.get("authorized_doc")
    third_phone = third_party_phone if third_party_phone is not None else kwargs.get("authorized_phone")
    client = client_name if client_name is not None else kwargs.get("client_name")
    model = car_model if car_model is not None else kwargs.get("car_model")
    color = car_color if car_color is not None else kwargs.get("car_color")

    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    plate_raw = plate or kwargs.get("car_plate", "")
    p_clean = clean_plate(plate_raw) if plate_raw else ""
    if not p_clean and file_path:
        cur.execute("SELECT plate, plate_clean FROM files WHERE file_path = ?", (file_path,))
        f_row = cur.fetchone()
        if f_row:
            plate_raw = plate_raw or f_row["plate"]
            p_clean = f_row["plate_clean"]

    now_str = updated_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    norm_status = normalize_patio_status(status) if status is not None else None

    existing = None
    if rec_id is not None:
        cur.execute("SELECT * FROM patio_status WHERE id = ?", (rec_id,))
        existing = cur.fetchone()
    elif file_path:
        cur.execute("SELECT * FROM patio_status WHERE file_path = ?", (file_path,))
        existing = cur.fetchone()
    elif p_clean:
        cur.execute("SELECT * FROM patio_status WHERE plate_clean = ? ORDER BY id DESC LIMIT 1", (p_clean,))
        existing = cur.fetchone()

    if existing:
        target_id = existing["id"]
        new_file_path = file_path if file_path is not None else existing["file_path"]
        new_plate = plate_raw if plate_raw else existing["plate"]
        new_plate_clean = p_clean if p_clean else existing["plate_clean"]
        new_status = norm_status if norm_status is not None else existing["status"]
        new_mechanic = mechanic if mechanic is not None else existing["mechanic_name"]
        new_third_name = third_name if third_name is not None else existing["third_party_name"]
        new_third_doc = third_doc if third_doc is not None else existing["third_party_doc"]
        new_third_phone = third_phone if third_phone is not None else (existing["third_party_phone"] if "third_party_phone" in existing.keys() else "")
        new_client = client if client is not None else (existing["client_name"] if "client_name" in existing.keys() else "")
        new_model = model if model is not None else (existing["car_model"] if "car_model" in existing.keys() else "")
        new_color = color if color is not None else (existing["car_color"] if "car_color" in existing.keys() else "")
        new_notes = notes if notes is not None else existing["notes"]

        cur.execute("""
        UPDATE patio_status SET
            file_path = ?,
            plate = ?,
            plate_clean = ?,
            status = ?,
            mechanic_name = ?,
            third_party_name = ?,
            third_party_doc = ?,
            updated_at = ?,
            notes = ?
        WHERE id = ?
        """, (
            new_file_path, new_plate, new_plate_clean, new_status,
            new_mechanic, new_third_name, new_third_doc,
            now_str, new_notes, target_id
        ))
        saved_id = target_id
    else:
        new_status = norm_status or "Em Diagnostico"
        cur.execute("""
        INSERT INTO patio_status (
            file_path, plate, plate_clean, status,
            mechanic_name, third_party_name, third_party_doc,
            updated_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_path or "", plate_raw or "", p_clean or "", new_status,
            mechanic or "", third_name or "", third_doc or "",
            now_str, notes or ""
        ))
        saved_id = cur.lastrowid

    conn.commit()
    conn.close()
    return get_patio_status(id=saved_id, db_path=path)

def delete_patio_status(record_id=None, file_path=None, plate=None, id=None, db_path=None):
    """
    Remove um veículo do status de pátio por id, file_path ou placa.
    """
    rec_id = record_id if record_id is not None else id
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    deleted = 0
    if rec_id is not None:
        cur.execute("DELETE FROM patio_status WHERE id = ?", (rec_id,))
        deleted = cur.rowcount
    elif file_path:
        cur.execute("DELETE FROM patio_status WHERE file_path = ?", (file_path,))
        deleted = cur.rowcount
    elif plate:
        cur.execute("DELETE FROM patio_status WHERE plate_clean = ?", (clean_plate(plate),))
        deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

set_patio_status = update_patio_status

# Aliases de compatibilidade para endpoints e módulos que usam nomenclatura legado/alternativa
def get_patio_cars(db_path=None):
    return list_patio_status(db_path=db_path)

def get_patio_car_by_id(car_id, db_path=None):
    return get_patio_status(id=car_id, db_path=db_path)

def get_patio_car_by_plate(plate, db_path=None):
    return get_patio_status(plate=plate, db_path=db_path)

def save_patio_car(data, db_path=None):
    return update_patio_status(
        file_path=data.get("file_path"),
        plate=data.get("plate"),
        status=data.get("status"),
        mechanic_name=data.get("mechanic_name") or data.get("box_mecanico"),
        third_party_name=data.get("third_party_name") or data.get("authorized_name"),
        third_party_doc=data.get("third_party_doc") or data.get("authorized_doc"),
        third_party_phone=data.get("third_party_phone") or data.get("authorized_phone"),
        client_name=data.get("client_name"),
        car_model=data.get("car_model"),
        car_color=data.get("car_color"),
        notes=data.get("notes"),
        record_id=data.get("id"),
        db_path=db_path
    )

def update_patio_car_status(car_id, status, authorized_name=None, authorized_doc=None, authorized_phone=None, db_path=None):
    return update_patio_status(
        record_id=car_id,
        status=status,
        third_party_name=authorized_name,
        third_party_doc=authorized_doc,
        third_party_phone=authorized_phone,
        db_path=db_path
    )

def delete_patio_car(car_id, db_path=None):
    return delete_patio_status(record_id=car_id, db_path=db_path)

def get_patio_summary(db_path=None):
    cars = list_patio_status(db_path=db_path)
    summary = {s: 0 for s in PATIO_STATUSES_DISPLAY}
    for c in cars:
        st = c.get("status") or c.get("status_display")
        if st in summary:
            summary[st] += 1
        else:
            summary[st] = summary.get(st, 0) + 1
    return {
        "total": len(cars),
        "by_status": summary,
        "cars": cars
    }


# ==============================================================================
# CONTROLE FISCAL / NOTAS FISCAIS (nf_control) - CP-01
# ==============================================================================

def _format_nf_dict(row_dict):
    """
    Padroniza o dicionário de controle fiscal garantindo campos compatíveis.
    """
    if not row_dict:
        return None
    d = dict(row_dict)
    d.setdefault("updated_time", d.get("updated_at", ""))
    d.setdefault("status_servico", d.get("nfse_status", ""))
    d.setdefault("nf_servico_num", d.get("nfse_number", ""))
    d.setdefault("status_pecas", d.get("nfe_status", ""))
    d.setdefault("nf_pecas_num", d.get("nfe_number", ""))
    d.setdefault("valor_servico", d.get("nfse_value", 0.0) or 0.0)
    d.setdefault("valor_pecas", d.get("nfe_value", 0.0) or 0.0)
    d.setdefault("data_emissao_servico", d.get("nfse_date", ""))
    d.setdefault("data_emissao_pecas", d.get("nfe_date", ""))
    d.setdefault("nfse_value", d.get("valor_servico", 0.0) or 0.0)
    d.setdefault("nfe_value", d.get("valor_pecas", 0.0) or 0.0)
    d.setdefault("nfse_date", d.get("data_emissao_servico", ""))
    d.setdefault("nfe_date", d.get("data_emissao_pecas", ""))
    return d

def list_nf_control(pending_only=False, nfse_status=None, nfe_status=None, plate=None, db_path=None):
    """
    Lista registros de controle de notas fiscais (NFS-e de Serviços e NF-e de Peças).
    Pode filtrar por notas pendentes (pending_only=True) ou status específicos.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
    SELECT 
        n.id,
        n.file_path,
        n.plate_clean,
        n.visit_num,
        n.nfse_status,
        n.nfse_number,
        n.nfe_status,
        n.nfe_number,
        n.updated_at,
        n.notes,
        f.client_name,
        f.car_model,
        f.car_year,
        f.car_color,
        f.plate_display,
        f.entry_date
    FROM nf_control n
    LEFT JOIN files f ON (n.file_path IS NOT NULL AND n.file_path != '' AND n.file_path = f.file_path)
    """
    clauses = []
    params = []

    if pending_only:
        clauses.append("(n.nfse_status = 'Pendente' OR n.nfe_status = 'Pendente' OR n.nfse_status = 'pendente' OR n.nfe_status = 'pendente')")
    if nfse_status:
        clauses.append("(n.nfse_status = ? OR LOWER(n.nfse_status) = ?)")
        params.extend([nfse_status, nfse_status.lower()])
    if nfe_status:
        clauses.append("(n.nfe_status = ? OR LOWER(n.nfe_status) = ?)")
        params.extend([nfe_status, nfe_status.lower()])
    if plate:
        clauses.append("n.plate_clean = ?")
        params.append(clean_plate(plate))

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY n.updated_at DESC, n.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        if not row.get("client_name") and row.get("plate_clean"):
            cur.execute("""
            SELECT client_name, car_model, car_year, car_color, plate_display, entry_date
            FROM files
            WHERE plate_clean = ?
            ORDER BY entry_date_sort DESC
            LIMIT 1
            """, (row["plate_clean"],))
            f_match = cur.fetchone()
            if f_match:
                for k, v in dict(f_match).items():
                    if not row.get(k):
                        row[k] = v
        _format_nf_dict(row)

    conn.close()
    return rows

def get_nf_control(id=None, file_path=None, plate_clean=None, visit_num=None, db_path=None):
    """
    Obtém registro de controle de nota fiscal por id, file_path ou par (plate_clean, visit_num).
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = None
    if id is not None:
        cur.execute("SELECT * FROM nf_control WHERE id = ?", (id,))
        row = cur.fetchone()
    elif file_path:
        cur.execute("SELECT * FROM nf_control WHERE file_path = ?", (file_path,))
        row = cur.fetchone()
    elif plate_clean and visit_num is not None:
        p_clean = clean_plate(plate_clean)
        cur.execute("SELECT * FROM nf_control WHERE plate_clean = ? AND visit_num = ?", (p_clean, str(visit_num)))
        row = cur.fetchone()
    elif plate_clean:
        p_clean = clean_plate(plate_clean)
        cur.execute("SELECT * FROM nf_control WHERE plate_clean = ? ORDER BY id DESC LIMIT 1", (p_clean,))
        row = cur.fetchone()

    if not row:
        conn.close()
        return None

    res = dict(row)
    if res.get("file_path"):
        cur.execute("SELECT client_name, car_model, car_year, car_color, plate_display, entry_date FROM files WHERE file_path = ?", (res["file_path"],))
        f_match = cur.fetchone()
        if f_match:
            for k, v in dict(f_match).items():
                res.setdefault(k, v)

    _format_nf_dict(res)
    conn.close()
    return res

def update_nf_control(
    file_path=None,
    plate_clean=None,
    visit_num=None,
    nfse_status=None,
    nfse_number=None,
    nfse_date=None,
    nfse_value=None,
    nfe_status=None,
    nfe_number=None,
    nfe_date=None,
    nfe_value=None,
    notes=None,
    record_id=None,
    id=None,
    updated_at=None,
    db_path=None,
    **kwargs
):
    """
    Cria ou atualiza o controle de notas fiscais de uma visita/ordem de serviço (upsert).
    Pode identificar por record_id (ou id), file_path ou par (plate_clean, visit_num).
    """
    rec_id = record_id if record_id is not None else id
    if nfse_status is None and "status_servico" in kwargs:
        nfse_status = kwargs["status_servico"]
    if nfse_number is None and "nf_servico_num" in kwargs:
        nfse_number = kwargs["nf_servico_num"]
    if nfse_date is None and "data_emissao_servico" in kwargs:
        nfse_date = kwargs["data_emissao_servico"]
    if nfse_value is None and "valor_servico" in kwargs:
        nfse_value = kwargs["valor_servico"]

    if nfe_status is None and "status_pecas" in kwargs:
        nfe_status = kwargs["status_pecas"]
    if nfe_number is None and "nf_pecas_num" in kwargs:
        nfe_number = kwargs["nf_pecas_num"]
    if nfe_date is None and "data_emissao_pecas" in kwargs:
        nfe_date = kwargs["data_emissao_pecas"]
    if nfe_value is None and "valor_pecas" in kwargs:
        nfe_value = kwargs["valor_pecas"]

    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    raw_plate = plate_clean or kwargs.get("plate", "")
    p_clean = clean_plate(raw_plate) if raw_plate else ""
    v_num = str(visit_num).strip() if visit_num is not None else ""

    client_name = kwargs.get("client_name", "")
    car_model = kwargs.get("car_model", "")
    entry_date = kwargs.get("entry_date", "")
    plate_disp = kwargs.get("plate_display", "")

    if file_path and (not p_clean or not v_num or not client_name):
        cur.execute("SELECT plate, plate_clean, plate_display, client_name, car_model, visit_num, entry_date FROM files WHERE file_path = ?", (file_path,))
        f_row = cur.fetchone()
        if f_row:
            p_clean = p_clean or f_row["plate_clean"]
            v_num = v_num or f_row["visit_num"]
            raw_plate = raw_plate or f_row["plate"]
            client_name = client_name or f_row["client_name"]
            car_model = car_model or f_row["car_model"]
            entry_date = entry_date or f_row["entry_date"]
            plate_disp = plate_disp or f_row["plate_display"]

    val_serv_f = parse_currency_float(nfse_value)
    val_pec_f = parse_currency_float(nfe_value)
    now_str = updated_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = None
    if rec_id is not None:
        cur.execute("SELECT * FROM nf_control WHERE id = ?", (rec_id,))
        existing = cur.fetchone()
    elif file_path:
        cur.execute("SELECT * FROM nf_control WHERE file_path = ?", (file_path,))
        existing = cur.fetchone()
    elif p_clean and v_num:
        cur.execute("SELECT * FROM nf_control WHERE plate_clean = ? AND visit_num = ?", (p_clean, v_num))
        existing = cur.fetchone()
    elif p_clean:
        cur.execute("SELECT * FROM nf_control WHERE plate_clean = ? ORDER BY id DESC LIMIT 1", (p_clean,))
        existing = cur.fetchone()

    if existing:
        existing = dict(existing)
        target_id = existing["id"]
        new_file_path = file_path if file_path is not None else existing["file_path"]
        new_plate = raw_plate if raw_plate else existing.get("plate", "")
        new_plate_clean = p_clean if p_clean else existing["plate_clean"]
        new_plate_disp = plate_disp if plate_disp else existing.get("plate_display", "")
        new_client = client_name if client_name else existing.get("client_name", "")
        new_model = car_model if car_model else existing.get("car_model", "")
        new_entry = entry_date if entry_date else existing.get("entry_date", "")
        new_visit_num = v_num if v_num else existing["visit_num"]

        new_nfse_status = nfse_status if nfse_status is not None else existing["nfse_status"]
        new_nfse_number = nfse_number if nfse_number is not None else existing["nfse_number"]
        new_nfse_date = nfse_date if nfse_date is not None else existing.get("nfse_date", "")
        new_nfse_val = val_serv_f if nfse_value is not None else (existing.get("nfse_value") or 0.0)

        new_nfe_status = nfe_status if nfe_status is not None else existing["nfe_status"]
        new_nfe_number = nfe_number if nfe_number is not None else existing["nfe_number"]
        new_nfe_date = nfe_date if nfe_date is not None else existing.get("nfe_date", "")
        new_nfe_val = val_pec_f if nfe_value is not None else (existing.get("nfe_value") or 0.0)

        new_notes = notes if notes is not None else existing["notes"]

    cur.execute("PRAGMA table_info(nf_control)")
    cols = {row[1] for row in cur.fetchall()}

    data_dict = {
        "file_path": file_path or (existing["file_path"] if existing else ""),
        "plate_clean": p_clean or (existing["plate_clean"] if existing else ""),
        "visit_num": v_num or (existing["visit_num"] if existing else ""),
        "nfse_status": nfse_status if nfse_status is not None else (existing["nfse_status"] if existing else "Pendente"),
        "nfse_number": nfse_number if nfse_number is not None else (existing["nfse_number"] if existing else ""),
        "nfe_status": nfe_status if nfe_status is not None else (existing["nfe_status"] if existing else "Pendente"),
        "nfe_number": nfe_number if nfe_number is not None else (existing["nfe_number"] if existing else ""),
        "updated_at": now_str,
        "notes": notes if notes is not None else (existing["notes"] if existing else "")
    }

    if "plate" in cols: data_dict["plate"] = raw_plate or (existing.get("plate", "") if existing else "")
    if "plate_display" in cols: data_dict["plate_display"] = plate_disp or (existing.get("plate_display", "") if existing else "")
    if "client_name" in cols: data_dict["client_name"] = client_name or (existing.get("client_name", "") if existing else "")
    if "car_model" in cols: data_dict["car_model"] = car_model or (existing.get("car_model", "") if existing else "")
    if "entry_date" in cols: data_dict["entry_date"] = entry_date or (existing.get("entry_date", "") if existing else "")
    if "nfse_date" in cols: data_dict["nfse_date"] = nfse_date if nfse_date is not None else (existing.get("nfse_date", "") if existing else "")
    if "nfse_value" in cols: data_dict["nfse_value"] = val_serv_f
    if "nfe_date" in cols: data_dict["nfe_date"] = nfe_date if nfe_date is not None else (existing.get("nfe_date", "") if existing else "")
    if "nfe_value" in cols: data_dict["nfe_value"] = val_pec_f
    if "status_servico" in cols: data_dict["status_servico"] = data_dict["nfse_status"]
    if "nf_servico_num" in cols: data_dict["nf_servico_num"] = data_dict["nfse_number"]
    if "valor_servico" in cols: data_dict["valor_servico"] = val_serv_f
    if "status_pecas" in cols: data_dict["status_pecas"] = data_dict["nfe_status"]
    if "nf_pecas_num" in cols: data_dict["nf_pecas_num"] = data_dict["nfe_number"]
    if "valor_pecas" in cols: data_dict["valor_pecas"] = val_pec_f
    if "updated_time" in cols: data_dict["updated_time"] = now_str

    valid_keys = [k for k in data_dict.keys() if k in cols]

    if existing:
        target_id = existing["id"]
        set_clause = ", ".join([f"{k} = ?" for k in valid_keys])
        vals = [data_dict[k] for k in valid_keys] + [target_id]
        cur.execute(f"UPDATE nf_control SET {set_clause} WHERE id = ?", tuple(vals))
        saved_id = target_id
    else:
        cols_clause = ", ".join(valid_keys)
        placeholders = ", ".join(["?"] * len(valid_keys))
        vals = [data_dict[k] for k in valid_keys]
        cur.execute(f"INSERT INTO nf_control ({cols_clause}) VALUES ({placeholders})", tuple(vals))
        saved_id = cur.lastrowid

    conn.commit()
    conn.close()
    return get_nf_control(id=saved_id, db_path=path)

def delete_nf_control(record_id=None, file_path=None, id=None, db_path=None):
    """
    Remove um registro de controle de nota fiscal por id ou file_path.
    """
    rec_id = record_id if record_id is not None else id
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    deleted = 0
    if rec_id is not None:
        cur.execute("DELETE FROM nf_control WHERE id = ?", (rec_id,))
        deleted = cur.rowcount
    elif file_path:
        cur.execute("DELETE FROM nf_control WHERE file_path = ?", (file_path,))
        deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def get_nf_queue(filter_type='pending', query='', db_path=None):
    """
    Retorna a fila de notas fiscais da oficina (pendentes, emitidas ou todas),
    cruzando dados de files com nf_control para garantir que nenhuma visita fique esquecida.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            f.file_path, f.file_name, f.plate, f.plate_clean, f.plate_display,
            f.client_name, f.client_clean, f.car_model, f.car_year, f.car_color,
            f.visit_num, f.entry_date, f.entry_date_sort, f.odometer, f.odometer_int,
            f.complaint, f.data_json,
            n.id as nf_id, n.notes, n.updated_at as updated_time,
            n.nfse_status, n.nfse_number,
            n.nfe_status, n.nfe_number
        FROM files f
        LEFT JOIN nf_control n ON (
            (n.file_path IS NOT NULL AND n.file_path != '' AND f.file_path = n.file_path) OR
            (n.plate_clean = f.plate_clean AND n.visit_num IS NOT NULL AND n.visit_num != '' AND f.visit_num = n.visit_num)
        )
        ORDER BY f.entry_date_sort DESC, f.odometer_int DESC, CAST(f.visit_num AS INTEGER) DESC
    """)
    rows = cur.fetchall()

    items = []
    total_visits = len(rows)
    pending_visits_count = 0
    pending_servicos_count = 0
    pending_pecas_count = 0
    emitted_count = 0
    total_pending_services_val = 0.0
    total_pending_pecas_val = 0.0

    q_clean = remove_accents(query or "").strip().lower()

    for r in rows:
        d_json = {}
        if r["data_json"]:
            try:
                d_json = json.loads(r["data_json"])
            except Exception:
                d_json = {}

        pecas = d_json.get("pecas_items") or []
        servicos = d_json.get("servicos_items") or []
        tot_pecas_str = d_json.get("total_pecas") or ""
        tot_serv_str = d_json.get("total_servicos") or ""
        tot_geral_str = d_json.get("total") or d_json.get("subtotal") or ""

        val_serv = parse_currency_float(tot_serv_str)
        val_pec = parse_currency_float(tot_pecas_str)
        val_tot = val_serv + val_pec if (val_serv + val_pec) > 0 else parse_currency_float(tot_geral_str)

        has_serv = len(servicos) > 0 or val_serv > 0
        has_pec = len(pecas) > 0 or val_pec > 0

        # Status Serviço (normaliza de nfse_status)
        raw_serv_status = r["nfse_status"]
        if raw_serv_status:
            st_serv = raw_serv_status.lower()
        else:
            st_serv = "pendente" if has_serv else "nao_se_aplica"

        # Status Peças (normaliza de nfe_status)
        raw_pec_status = r["nfe_status"]
        if raw_pec_status:
            st_pec = raw_pec_status.lower()
        else:
            st_pec = "pendente" if has_pec else "nao_se_aplica"

        num_serv = r["nfse_number"] or ""
        date_serv = ""
        num_pec = r["nfe_number"] or ""
        date_pec = ""

        is_pending_serv = (st_serv == "pendente")
        is_pending_pec = (st_pec == "pendente")
        is_pending = is_pending_serv or is_pending_pec
        is_emitted = (st_serv == "emitida" or st_pec == "emitida")

        if is_pending:
            pending_visits_count += 1
        if is_pending_serv:
            pending_servicos_count += 1
            total_pending_services_val += val_serv
        if is_pending_pec:
            pending_pecas_count += 1
            total_pending_pecas_val += val_pec
        if is_emitted:
            emitted_count += 1

        # Filtro de busca textual
        if q_clean:
            haystack = " ".join([
                r["plate"] or "",
                r["plate_clean"] or "",
                r["client_name"] or "",
                r["car_model"] or "",
                r["visit_num"] or "",
                num_serv,
                num_pec
            ])
            if q_clean not in remove_accents(haystack).lower():
                continue

        # Filtro por tipo de aba
        if filter_type == "pending" and not is_pending:
            continue
        elif filter_type == "pending_servico" and not is_pending_serv:
            continue
        elif filter_type == "pending_pecas" and not is_pending_pec:
            continue
        elif filter_type == "emitidas" and not is_emitted:
            continue

        item = {
            "file_path": r["file_path"],
            "file_name": r["file_name"],
            "plate": r["plate"],
            "plate_clean": r["plate_clean"],
            "plate_display": r["plate_display"] or format_plate_display(r["plate"]),
            "client_name": r["client_name"],
            "phone": d_json.get("phone") or "",
            "cpf": d_json.get("cpf") or "",
            "car_model": r["car_model"],
            "car_year": r["car_year"],
            "car_color": r["car_color"],
            "visit_num": r["visit_num"],
            "entry_date": r["entry_date"],
            "entry_date_sort": r["entry_date_sort"],
            "odometer": r["odometer"],
            "has_servicos": has_serv,
            "has_pecas": has_pec,
            "servicos_count": len(servicos),
            "pecas_count": len(pecas),
            "valor_servico": val_serv,
            "valor_servico_fmt": f"R$ {val_serv:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "valor_pecas": val_pec,
            "valor_pecas_fmt": f"R$ {val_pec:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "valor_total": val_tot,
            "valor_total_fmt": f"R$ {val_tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "nf_id": r["nf_id"],
            "status_servico": st_serv,
            "nfse_status": st_serv,
            "nf_servico_num": num_serv,
            "nfse_number": num_serv,
            "data_emissao_servico": date_serv,
            "nfse_date": date_serv,
            "status_pecas": st_pec,
            "nfe_status": st_pec,
            "nf_pecas_num": num_pec,
            "nfe_number": num_pec,
            "data_emissao_pecas": date_pec,
            "nfe_date": date_pec,
            "notes": r["notes"] or "",
            "updated_time": r["updated_time"] or "",
            "is_pending": is_pending,
            "is_pending_servico": is_pending_serv,
            "is_pending_pecas": is_pending_pec,
            "is_emitted": is_emitted
        }
        items.append(item)

    conn.close()

    stats = {
        "total_visits": total_visits,
        "pending_visits_count": pending_visits_count,
        "pending_servicos_count": pending_servicos_count,
        "pending_pecas_count": pending_pecas_count,
        "emitted_count": emitted_count,
        "total_pending_services_val": total_pending_services_val,
        "total_pending_services_fmt": f"R$ {total_pending_services_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "total_pending_pecas_val": total_pending_pecas_val,
        "total_pending_pecas_fmt": f"R$ {total_pending_pecas_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    }

    return {"queue": items, "stats": stats}

def get_pending_nf_list(db_path=None):
    """
    Atalho para listar todas as notas fiscais pendentes (NFS-e de Serviços ou NF-e de Peças).
    """
    return list_nf_control(pending_only=True, db_path=db_path)

set_nf_control = update_nf_control

# Aliases de compatibilidade para controle fiscal
def get_nf_records(db_path=None):
    return list_nf_control(db_path=db_path)

def get_nf_by_plate(plate, db_path=None):
    return get_nf_control(plate_clean=plate, db_path=db_path)

def save_nf_control(data, db_path=None):
    return update_nf_control(db_path=db_path, **data)

def get_pending_nfs(db_path=None):
    return get_nf_queue(filter_type='pending', db_path=db_path).get("queue", [])

def index_single_file(fpath, db_path=None, old_fpath=None):
    """
    Indexa imediatamente uma planilha criada ou editada sem necessidade de reindexação completa.
    """
    if not fpath or not os.path.exists(fpath):
        return None
        
    path = db_path or get_db_path()
    init_db(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    if old_fpath and old_fpath != fpath:
        cur.execute("DELETE FROM files WHERE file_path = ?", (old_fpath,))
        
    try:
        mtime = os.path.getmtime(fpath)
        fsize = os.path.getsize(fpath)
        parsed = parse_file(fpath)
        
        fname = os.path.basename(fpath)
        plate_raw = parsed.get("plate", "")
        plate_clean = clean_plate(plate_raw)
        plate_display = parsed.get("plate_display", "") or format_plate_display(plate_raw)
        client_name = parsed.get("client_name", "")
        client_clean = remove_accents(client_name).lower()
        car_model = parsed.get("car_model", "")
        car_year = parsed.get("car_year", "")
        car_color = parsed.get("car_color", "")
        visit_num = parsed.get("visit_num", "")
        entry_date = parsed.get("entry_date", "")
        entry_date_sort = parse_date_sortable(entry_date)
        odometer = parsed.get("odometer", "")
        odometer_int = parse_odometer_int(odometer)
        complaint = parsed.get("complaint", "")
        data_json = json.dumps(parsed, ensure_ascii=False)
        
        cur.execute("""
        INSERT OR REPLACE INTO files (
            file_path, file_name, file_mtime, file_size,
            plate, plate_clean, plate_display, client_name, client_clean,
            car_model, car_year, car_color, visit_num,
            entry_date, entry_date_sort, odometer, odometer_int,
            complaint, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fpath, fname, mtime, fsize,
            plate_raw, plate_clean, plate_display, client_name, client_clean,
            car_model, car_year, car_color, visit_num,
            entry_date, entry_date_sort, odometer, odometer_int,
            complaint, data_json
        ))
        
        conn.commit()
        conn.close()
        return parsed
    except Exception as e:
        conn.close()
        raise e

def get_car_lookup(plate, db_path=None):
    """
    Busca os dados cadastrais da última visita do veículo e calcula a próxima visita (N + 1).
    """
    if not plate or not str(plate).strip():
        return {
            "found": False,
            "plate": "",
            "plate_clean": "",
            "plate_display": "",
            "suggested_visit_num": 1,
            "max_visit_num": 0,
            "latest_visit": None,
            "visits_count": 0
        }
        
    p_clean = clean_plate(plate)
    p_display = format_plate_display(plate)
    history = get_car_history(p_clean, db_path=db_path)
    
    if not history:
        return {
            "found": False,
            "plate": plate,
            "plate_clean": p_clean,
            "plate_display": p_display,
            "suggested_visit_num": 1,
            "max_visit_num": 0,
            "latest_visit": None,
            "visits_count": 0
        }
        
    visit_numbers = []
    for h in history:
        v_num = h.get("visit_num")
        v_int = parse_visit_int(v_num)
        if v_int > 0:
            visit_numbers.append(v_int)
        d = h.get("details")
        if d and d.get("visit_num"):
            v2 = parse_visit_int(d.get("visit_num"))
            if v2 > 0:
                visit_numbers.append(v2)
                
    max_visit = max(visit_numbers) if visit_numbers else len(history)
    suggested_visit = max_visit + 1
    
    latest = history[0]
    details = latest.get("details") or {}
    
    client_info = {
        "client_name": details.get("client_name") or latest.get("client_name") or "",
        "phone": details.get("phone") or "",
        "phone_res": details.get("phone_res") or "",
        "phone_com": details.get("phone_com") or "",
        "cpf": details.get("cpf") or "",
        "rg": details.get("rg") or "",
        "email": details.get("email") or "",
        "address": details.get("address") or "",
        "address_num": details.get("address_num") or "",
        "address_compl": details.get("address_compl") or "",
        "neighborhood": details.get("neighborhood") or "",
        "city": details.get("city") or "Santos",
        "cep": details.get("cep") or ""
    }
    
    car_info = {
        "car_brand": details.get("car_brand") or "",
        "car_model": details.get("car_model") or latest.get("car_model") or "",
        "car_year": details.get("car_year") or latest.get("car_year") or "",
        "car_plate": p_display or latest.get("plate_display") or latest.get("plate") or "",
        "car_color": details.get("car_color") or latest.get("car_color") or "",
        "car_fuel": details.get("car_fuel") or "",
        "car_chassis": details.get("car_chassis") or ""
    }
    
    return {
        "found": True,
        "plate": plate,
        "plate_clean": p_clean,
        "plate_display": p_display or latest.get("plate_display") or "",
        "suggested_visit_num": suggested_visit,
        "max_visit_num": max_visit,
        "visits_count": len(history),
        "latest_visit": latest,
        "client": client_info,
        "car": car_info,
        "last_odometer": latest.get("odometer") or details.get("odometer") or ""
    }

def get_quick_suggestions(db_path=None):
    """
    Retorna sugestões de peças e serviços padrão e mais usados na oficina.
    """
    default_pecas = [
        "Óleo do Motor 5W30 Sintético",
        "Óleo do Motor 5W40 Sintético",
        "Óleo do Motor 10W40 Semissintético",
        "Filtro de Óleo do Motor",
        "Filtro de Ar do Motor",
        "Filtro de Combustível",
        "Filtro de Cabine / Ar Condicionado",
        "Pastilhas de Freio Dianteiras",
        "Discos de Freio Dianteiros",
        "Fluido de Freio DOT 4",
        "Velas de Ignição (Jogo)",
        "Líquido de Arrefecimento / Aditivo Radiador",
        "Kit Batente e Coifa Dianteiro",
        "Amortecedores Dianteiros (Par)",
        "Correia Dentada",
        "Tensor da Correia Dentada"
    ]
    
    default_servicos = [
        "Troca de Óleo do Motor e Filtros",
        "Revisão Geral Preventiva",
        "Diagnóstico Computadorizado (Scanner)",
        "Alinhamento 3D e Balanceamento",
        "Substituição de Pastilhas e Discos de Freio",
        "Sangria e Substituição do Fluido de Freio",
        "Limpeza e Equalização de Bicos Injetores",
        "Troca da Correia Dentada e Tensor",
        "Limpeza do Sistema de Arrefecimento e Aditivo",
        "Higienização do Ar Condicionado",
        "Troca de Velas de Ignição",
        "Substituição de Amortecedores e Batentes"
    ]
    
    path = db_path or get_db_path()
    pecas_db = []
    servicos_db = []
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT data_json FROM files WHERE data_json IS NOT NULL AND data_json != ''")
        for (dj,) in cur.fetchall():
            try:
                loaded = json.loads(dj)
                for p in loaded.get("pecas_items", []):
                    desc = str(p.get("description", "")).strip()
                    if desc and len(desc) > 2 and desc not in pecas_db and desc not in default_pecas:
                        pecas_db.append(desc)
                for s in loaded.get("servicos_items", []):
                    desc = str(s.get("description", "")).strip()
                    if desc and len(desc) > 2 and desc not in servicos_db and desc not in default_servicos:
                        servicos_db.append(desc)
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
        
    return {
        "pecas": default_pecas + pecas_db[:30],
        "servicos": default_servicos + servicos_db[:30]
    }
