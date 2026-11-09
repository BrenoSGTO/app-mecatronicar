# -*- coding: utf-8 -*-
import os
import sqlite3
import json
import re
import datetime
from parser import parse_file, parse_filename, remove_accents, clean_plate, format_plate_display

DB_FILE = "oficina_cache.db"
FAST_INDEX_THRESHOLD = 15

def get_db_path(base_dir=None):
    if base_dir:
        return os.path.join(base_dir, DB_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILE)

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
            if "extra_sheets_data" in loaded:
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
    
    # Check existing mtimes in batch
    cur.execute("SELECT file_path, file_mtime FROM files")
    cached_mtimes = dict(cur.fetchall())
    
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
    return results

