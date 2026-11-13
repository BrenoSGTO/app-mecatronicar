# -*- coding: utf-8 -*-
import os
import sqlite3
import json
import re
import datetime
import logging
import threading
import time
import zipfile
from parser import parse_file, parse_filename, remove_accents, clean_plate, format_plate_display, PARSER_VERSION, parse_currency_float

DB_FILE = "oficina_cache.db"
FAST_INDEX_THRESHOLD = 15

log = logging.getLogger("mecatronicar.cache")

def get_db_path(base_dir=None):
    if base_dir:
        return os.path.join(base_dir, DB_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILE)


# ==============================================================================
# CONEXÕES SQLITE
# ==============================================================================
# - Toda conexão sai daqui com busy_timeout e synchronous=NORMAL (o banco usa WAL,
#   ativado uma única vez em init_db, e o modo fica gravado no arquivo).
# - Para o banco do aplicativo (registrado por enable_connection_pool) cada thread
#   reaproveita a sua conexão: abrir uma conexão SQLite no Windows custa ~4 ms
#   (arquivos -wal/-shm + antivírus), mais que a maioria das consultas.
# - Bancos não registrados (ex.: bancos temporários dos testes) continuam com uma
#   conexão nova por chamada, para que possam ser apagados logo depois no Windows.

_BUSY_TIMEOUT_S = 10.0
_INIT_LOCK = threading.Lock()
_initialized = {}          # path -> identidade do arquivo quando o schema foi garantido
_POOLED_PATHS = set()
_tls = threading.local()


def _norm_path(path):
    return os.path.normcase(os.path.abspath(path))


def _file_identity(path):
    try:
        st = os.stat(path)
        return (st.st_dev, st.st_ino, getattr(st, "st_birthtime_ns", st.st_ctime_ns))
    except OSError:
        return None


def _configure_connection(conn):
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")


def enable_connection_pool(db_path):
    """Ativa o reaproveitamento de conexões por thread para este banco."""
    _POOLED_PATHS.add(_norm_path(db_path))


def close_thread_connections():
    """Fecha as conexões reaproveitadas da thread atual (usado no desligamento/testes)."""
    conns = getattr(_tls, "conns", None)
    if not conns:
        return
    for raw, _ident, _state in list(conns.values()):
        try:
            raw.close()
        except Exception:
            pass
    conns.clear()


class _PooledConnection:
    """
    Fachada de uma conexão reaproveitada. Mantém a mesma interface usada no módulo
    (cursor/commit/close/row_factory), mas `close()` não fecha a conexão real:
    apenas desfaz uma transação pendente quando o último usuário da conexão sai,
    reproduzindo a semântica de "fechar sem commit = descartar".
    """
    __slots__ = ("_raw", "_state", "row_factory", "_closed")

    def __init__(self, raw, state):
        self._raw = raw
        self._state = state
        self.row_factory = None
        self._closed = False
        state["users"] += 1

    def cursor(self):
        cur = self._raw.cursor()
        cur.row_factory = self.row_factory
        return cur

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq):
        return self.cursor().executemany(sql, seq)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    @property
    def in_transaction(self):
        return self._raw.in_transaction

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._state["users"] -= 1
        if self._state["users"] <= 0 and self._raw.in_transaction:
            try:
                self._raw.rollback()
            except Exception:
                pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        return False


def _connect(path):
    key = _norm_path(path)
    if key in _POOLED_PATHS:
        conns = getattr(_tls, "conns", None)
        if conns is None:
            conns = _tls.conns = {}
        ident = _file_identity(path)
        entry = conns.get(key)
        if entry and entry[1] == ident and ident is not None:
            return _PooledConnection(entry[0], entry[2])
        if entry:
            try:
                entry[0].close()
            except Exception:
                pass
        raw = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_S)
        _configure_connection(raw)
        state = {"users": 0}
        conns[key] = (raw, _file_identity(path), state)
        return _PooledConnection(raw, state)
    raw = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_S)
    _configure_connection(raw)
    return raw


# Tabelas cujas mudanças são contadas (para ETag do pátio e cache de analytics).
_TRACKED_TABLES = ("files", "patio_status", "nf_control", "agendamentos", "agenda_events")


def _setup_change_tracking(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS change_counters (
        name TEXT PRIMARY KEY,
        gen INTEGER NOT NULL DEFAULT 0
    )
    """)
    for t in _TRACKED_TABLES:
        cur.execute("INSERT OR IGNORE INTO change_counters (name, gen) VALUES (?, 0)", (t,))
        for op in ("INSERT", "UPDATE", "DELETE"):
            cur.execute(f"""
            CREATE TRIGGER IF NOT EXISTS trg_gen_{t}_{op.lower()}
            AFTER {op} ON {t}
            BEGIN
                UPDATE change_counters SET gen = gen + 1 WHERE name = '{t}';
            END
            """)


_RESULT_CACHE = {}
_RESULT_CACHE_LOCK = threading.Lock()
_RESULT_CACHE_MAX = 32


def _cached_result(name, path, args, tables, compute):
    """Memoiza `compute()` pela geração das tabelas envolvidas (ver change_counters)."""
    gens = get_change_counters(path)
    # A identidade do arquivo entra na chave: um banco apagado e recriado no mesmo
    # caminho recomeça os contadores do zero e não pode reaproveitar o cache.
    key = (name, _norm_path(path), args, _file_identity(path), tuple(gens.get(t, 0) for t in tables))
    with _RESULT_CACHE_LOCK:
        hit = _RESULT_CACHE.get(key)
    if hit is not None:
        return hit
    result = compute()
    with _RESULT_CACHE_LOCK:
        stale = [k for k in _RESULT_CACHE if k[:3] == key[:3]]
        for k in stale:
            del _RESULT_CACHE[k]
        while len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            del _RESULT_CACHE[next(iter(_RESULT_CACHE))]
        _RESULT_CACHE[key] = result
    return result


def get_change_counters(db_path=None):
    """
    Retorna {tabela: geração}. A geração sobe a cada linha inserida/alterada/apagada
    (via triggers), inclusive por outros processos, e serve para ETag e caches.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, gen FROM change_counters")
        return {name: gen for name, gen in cur.fetchall()}
    finally:
        conn.close()

PATIO_STATUSES = [
    "Em Diagnostico",
    "Esperando Orcamento",
    "Esperando Aprovacao",
    "Esperando Pecas",
    "Em Execucao",
    "Esperando Cliente",
    "Liberado Terceiro",
    "Entregue"
]

VALID_PATIO_STATUSES = PATIO_STATUSES

PATIO_STATUSES_DISPLAY = [
    "Em Diagnóstico",
    "Esperando Orçamento",
    "Esperando Aprovação",
    "Esperando Peças",
    "Em Execução",
    "Esperando Cliente Buscar",
    "Liberado p/ Retirada por Terceiro",
    "Entregue"
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
    "Liberado p/ Retirada por Terceiro": "Liberado p/ Retirada por Terceiro",
    "Entregue": "Entregue"
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
        "liberado para retirada por terceiro": "Liberado p/ Retirada por Terceiro",
        "entregue": "Entregue",
        "entregue ao cliente": "Entregue"
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
        plate TEXT,
        plate_clean TEXT,
        plate_display TEXT,
        client_name TEXT,
        car_model TEXT,
        entry_date TEXT,
        visit_num TEXT,
        nfse_status TEXT DEFAULT 'Pendente',
        nfse_number TEXT DEFAULT '',
        nfse_date TEXT,
        nfse_value REAL DEFAULT 0.0,
        status_servico TEXT DEFAULT 'Pendente',
        nf_servico_num TEXT DEFAULT '',
        valor_servico REAL DEFAULT 0.0,
        data_emissao_servico TEXT,
        nfe_status TEXT DEFAULT 'Pendente',
        nfe_number TEXT DEFAULT '',
        nfe_date TEXT,
        nfe_value REAL DEFAULT 0.0,
        status_pecas TEXT DEFAULT 'Pendente',
        nf_pecas_num TEXT DEFAULT '',
        valor_pecas REAL DEFAULT 0.0,
        data_emissao_pecas TEXT,
        updated_at TEXT,
        updated_time TEXT,
        notes TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_file_path ON nf_control(file_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_plate ON nf_control(plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nf_plate_visit ON nf_control(plate_clean, visit_num)")

    # Garante migração de colunas adicionais para bancos já existentes
    cur.execute("PRAGMA table_info(nf_control)")
    cols = {row[1] for row in cur.fetchall()}
    extra_cols = [
        ("plate", "TEXT"),
        ("plate_display", "TEXT"),
        ("client_name", "TEXT"),
        ("car_model", "TEXT"),
        ("entry_date", "TEXT"),
        ("nfse_date", "TEXT"),
        ("nfse_value", "REAL DEFAULT 0.0"),
        ("status_servico", "TEXT DEFAULT 'Pendente'"),
        ("nf_servico_num", "TEXT DEFAULT ''"),
        ("valor_servico", "REAL DEFAULT 0.0"),
        ("data_emissao_servico", "TEXT"),
        ("nfe_date", "TEXT"),
        ("nfe_value", "REAL DEFAULT 0.0"),
        ("status_pecas", "TEXT DEFAULT 'Pendente'"),
        ("nf_pecas_num", "TEXT DEFAULT ''"),
        ("valor_pecas", "REAL DEFAULT 0.0"),
        ("data_emissao_pecas", "TEXT"),
        ("updated_time", "TEXT")
    ]
    for col_name, col_type in extra_cols:
        if col_name not in cols:
            try:
                cur.execute(f"ALTER TABLE nf_control ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

def _setup_agendamentos_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agendamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        phone TEXT,
        car_plate TEXT,
        car_plate_clean TEXT,
        car_model TEXT,
        title TEXT NOT NULL,
        description TEXT,
        scheduled_date TEXT NOT NULL,
        scheduled_time TEXT,
        status TEXT DEFAULT 'agendado',
        created_at TEXT,
        updated_at TEXT,
        notes TEXT,
        google_calendar_id TEXT,
        google_calendar_sync_status TEXT DEFAULT 'pending'
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agendamentos_date ON agendamentos(scheduled_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agendamentos_plate ON agendamentos(car_plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agendamentos_status ON agendamentos(status)")

    # Migração segura de colunas caso a tabela já exista
    cur.execute("PRAGMA table_info(agendamentos)")
    cols = {row[1] for row in cur.fetchall()}
    extra_cols = [
        ("car_plate_clean", "TEXT"),
        ("notes", "TEXT"),
        ("google_calendar_id", "TEXT"),
        ("google_calendar_sync_status", "TEXT DEFAULT 'pending'")
    ]
    for col_name, col_type in extra_cols:
        if col_name not in cols:
            try:
                cur.execute(f"ALTER TABLE agendamentos ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

def _setup_agenda_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agenda_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        client_name TEXT,
        plate TEXT,
        plate_clean TEXT,
        plate_display TEXT,
        car_model TEXT,
        service_type TEXT,
        event_date TEXT,
        event_time TEXT,
        notes TEXT,
        status TEXT DEFAULT 'Agendado',
        created_at TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agenda_date ON agenda_events(event_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agenda_plate ON agenda_events(plate_clean)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_agenda_status ON agenda_events(status)")

_FILE_COLUMNS = (
    "file_path", "file_name", "file_mtime", "file_size",
    "plate", "plate_clean", "plate_display", "client_name", "client_clean",
    "car_model", "car_year", "car_color", "visit_num",
    "entry_date", "entry_date_sort", "odometer", "odometer_int",
    "complaint", "data_json", "search_text",
)
_UPSERT_FILE_SQL = (
    f"INSERT OR REPLACE INTO files ({', '.join(_FILE_COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(_FILE_COLUMNS))})"
)
_SEARCH_SEP = "\x1f"  # separador que a busca nunca contém: impede casar "entre" campos


def build_search_text(plate_clean="", client_name="", car_model="", file_name="", complaint=""):
    """Texto de busca normalizado (minúsculo e sem acento) de uma planilha."""
    parts = [plate_clean or "", client_name or "", car_model or "", file_name or "", complaint or ""]
    return _SEARCH_SEP.join(remove_accents(p).lower() for p in parts)


def _upsert_file_row(cur, row):
    row["search_text"] = build_search_text(
        row.get("plate_clean"), row.get("client_name"), row.get("car_model"),
        row.get("file_name"), row.get("complaint"),
    )
    cur.execute(_UPSERT_FILE_SQL, tuple(row.get(c) for c in _FILE_COLUMNS))


def _setup_files_search_column(cur):
    cur.execute("PRAGMA table_info(files)")
    cols = {r[1] for r in cur.fetchall()}
    if "search_text" not in cols:
        cur.execute("ALTER TABLE files ADD COLUMN search_text TEXT")
    # Se outro código (ex.: gerar_massa_dados.py) alterar os campos pesquisáveis sem
    # recalcular search_text, invalida-o; backfill_search_text() o recalcula depois.
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_files_search_stale
    AFTER UPDATE OF plate_clean, client_name, car_model, file_name, complaint ON files
    WHEN NEW.search_text IS OLD.search_text
    BEGIN
        UPDATE files SET search_text = NULL WHERE file_path = NEW.file_path;
    END
    """)
    _backfill_search_text(cur)


def _backfill_search_text(cur):
    cur.execute("""
        SELECT file_path, plate_clean, client_name, car_model, file_name, complaint
        FROM files WHERE search_text IS NULL
    """)
    rows = cur.fetchall()
    if rows:
        cur.executemany(
            "UPDATE files SET search_text = ? WHERE file_path = ?",
            [(build_search_text(pc, cn, cm, fn, cp), fp) for fp, pc, cn, cm, fn, cp in rows],
        )
    return len(rows)


def init_db(db_path=None):
    """
    Garante o schema do banco. É chamado no início de quase toda função do módulo,
    então só executa o DDL uma vez por arquivo (memoizado pela identidade do arquivo:
    se o banco for apagado e recriado, o schema é garantido de novo).
    """
    path = db_path or get_db_path()
    key = _norm_path(path)
    ident = _file_identity(path)
    if ident is not None and _initialized.get(key) == ident:
        return
    with _INIT_LOCK:
        ident = _file_identity(path)
        if ident is not None and _initialized.get(key) == ident:
            return
        _init_db_schema(path)
        _initialized[key] = _file_identity(path)


def _init_db_schema(path):
    conn = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_S)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError as e:
        log.warning("Não foi possível ativar WAL em %s: %s", path, e)
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
    _setup_files_search_column(cur)

    # Estruturas do CP-01 (patio_status, nf_control e templates), Issue #15 (agendamentos) e Agenda
    _setup_patio_table(cur)
    _setup_nf_table(cur)
    _setup_agendamentos_table(cur)
    _setup_agenda_table(cur)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patio_updated ON patio_status(updated_at)")
    _setup_change_tracking(cur)

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

# Erros típicos de planilha aberta/sendo salva pelo Excel (arquivo bloqueado ou
# gravado pela metade). São tratados como transitórios: a linha fica pendente e
# a próxima varredura tenta de novo.
_TRANSIENT_FILE_ERRORS = (PermissionError, zipfile.BadZipFile, EOFError)


class FileBusyError(Exception):
    """Planilha bloqueada ou incompleta (normalmente aberta/sendo salva no Excel)."""


def _parse_file_resilient(fpath, retries=0, delay=0.3):
    attempt = 0
    while True:
        try:
            return parse_file(fpath)
        except _TRANSIENT_FILE_ERRORS as e:
            if attempt >= retries:
                raise FileBusyError(f"arquivo em uso ou incompleto (aberto no Excel?): {e}") from e
            attempt += 1
            time.sleep(delay)


def _row_from_parsed(fpath, parsed, mtime, fsize, fallback=None):
    fb = fallback or {}
    plate_raw = parsed.get("plate", "") or fb.get("plate", "") or ""
    client_name = parsed.get("client_name", "") or fb.get("client_name", "") or ""
    entry_date = parsed.get("entry_date", "") or ""
    odometer = parsed.get("odometer", "") or ""
    return {
        "file_path": fpath,
        "file_name": parsed.get("file_name") or os.path.basename(fpath),
        "file_mtime": mtime,
        "file_size": fsize,
        "plate": plate_raw,
        "plate_clean": clean_plate(plate_raw),
        "plate_display": parsed.get("plate_display", "") or format_plate_display(plate_raw),
        "client_name": client_name,
        "client_clean": remove_accents(client_name).lower(),
        "car_model": parsed.get("car_model", "") or fb.get("car_model", "") or "",
        "car_year": parsed.get("car_year", "") or fb.get("car_year", "") or "",
        "car_color": parsed.get("car_color", "") or fb.get("car_color", "") or "",
        "visit_num": parsed.get("visit_num", "") or fb.get("visit_num", "") or "",
        "entry_date": entry_date,
        "entry_date_sort": parse_date_sortable(entry_date),
        "odometer": odometer,
        "odometer_int": parse_odometer_int(odometer),
        "complaint": parsed.get("complaint", "") or "",
        "data_json": json.dumps(parsed, ensure_ascii=False),
    }


def _row_from_filename(fpath, mtime, fsize):
    fname = os.path.basename(fpath)
    meta = parse_filename(fname)
    plate_raw = meta.get("plate", "")
    client_name = meta.get("owner", "")
    return {
        "file_path": fpath,
        "file_name": fname,
        "file_mtime": mtime,
        "file_size": fsize,
        "plate": plate_raw,
        "plate_clean": clean_plate(plate_raw),
        "plate_display": format_plate_display(plate_raw),
        "client_name": client_name,
        "client_clean": remove_accents(client_name).lower(),
        "car_model": meta.get("model", ""),
        "car_year": "",
        "car_color": meta.get("color", ""),
        "visit_num": meta.get("visit_num", ""),
        "entry_date": "",
        "entry_date_sort": "0000-00-00",
        "odometer": "",
        "odometer_int": 0,
        "complaint": "",
        "data_json": "",
    }


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
        except ValueError:
            log.warning("data_json inválido no cache para %s; relendo a planilha", fpath)

    if not fpath or not os.path.exists(fpath):
        d["details"] = None
        return d, False

    try:
        st = os.stat(fpath)
        parsed = _parse_file_resilient(fpath)
    except FileBusyError as e:
        log.info("Leitura sob demanda adiada (%s): %s", os.path.basename(fpath), e)
        d["details"] = None
        return d, False
    except Exception:
        log.exception("Falha ao ler a planilha %s", fpath)
        d["details"] = None
        return d, False

    row = _row_from_parsed(fpath, parsed, st.st_mtime, st.st_size, fallback=d)
    _upsert_file_row(cur, row)
    row.pop("search_text", None)
    d.update(row)
    d["details"] = parsed
    return d, True


def _iter_spreadsheets(folder_path):
    """
    Lista (caminho, mtime, tamanho) das planilhas .xlsx/.xls da pasta, recursivamente.
    Usa os.scandir: no Windows o stat vem junto da listagem do diretório (sem
    uma chamada extra por arquivo), o que torna a reindexação sem mudanças barata.
    """
    stack = [folder_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    name = entry.name
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if name.startswith("~$"):  # arquivo de bloqueio do Excel
                            continue
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in (".xlsx", ".xls"):
                            continue
                        st = entry.stat()
                        yield os.path.join(current, name), st.st_mtime, st.st_size
                    except OSError as e:
                        log.warning("Não foi possível ler %s: %s", entry.path, e)
        except OSError as e:
            log.warning("Não foi possível listar a pasta %s: %s", current, e)


def _pending_parse_where():
    return ("(data_json IS NULL OR data_json = '' "
            "OR json_extract(data_json, '$.parser_version') IS NOT ?)")


def scan_and_index_folder(folder_path, db_path=None, progress_callback=None, full_parse=None):
    """
    Varredura incremental da pasta de planilhas.

    - Só olha planilhas novas ou alteradas (mtime ou tamanho diferentes do cache).
    - Poucas mudanças (até FAST_INDEX_THRESHOLD) são lidas por completo na hora;
      muitas (ex.: primeira indexação) entram pelo nome do arquivo, em milissegundos,
      e o conteúdo fica pendente para parse_pending_rows() (rodado em segundo plano
      por start_background_index).
    - Remove do cache planilhas que não existem mais na pasta.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return {"error": "Pasta inválida", "indexed": 0, "total": 0}

    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    try:
        cur = conn.cursor()
        all_files = list(_iter_spreadsheets(folder_path))
        total_files = len(all_files)
        indexed_count = 0
        errors = []

        cur.execute("SELECT file_path, file_mtime, file_size FROM files")
        cached = {fp: (mt, sz) for fp, mt, sz in cur.fetchall()}

        to_process = []
        for fpath, mtime, fsize in all_files:
            prev = cached.get(fpath)
            if prev is not None and prev[0] is not None and abs(prev[0] - mtime) < 0.01 \
                    and (prev[1] is None or prev[1] == fsize):
                continue
            to_process.append((fpath, mtime, fsize))

        if full_parse is None:
            use_fast_filename_index = len(to_process) > FAST_INDEX_THRESHOLD
        else:
            use_fast_filename_index = not full_parse

        for idx, (fpath, mtime, fsize) in enumerate(to_process):
            fname = os.path.basename(fpath)
            try:
                if use_fast_filename_index:
                    row = _row_from_filename(fpath, mtime, fsize)
                else:
                    try:
                        parsed = _parse_file_resilient(fpath, retries=1)
                        row = _row_from_parsed(fpath, parsed, mtime, fsize)
                    except FileBusyError as e:
                        # Planilha aberta/sendo salva: entra pelo nome e fica pendente.
                        errors.append(f"{fname}: {e}")
                        row = _row_from_filename(fpath, mtime, fsize)
                _upsert_file_row(cur, row)
                indexed_count += 1
                if progress_callback:
                    progress_callback(idx + 1, len(to_process), fname)
            except Exception as e:
                log.exception("Falha ao indexar %s", fpath)
                errors.append(f"{fname}: {e}")

        existing = {fp for fp, _, _ in all_files}
        stale = [(fp,) for fp in cached if fp not in existing]
        if stale:
            cur.executemany("DELETE FROM files WHERE file_path = ?", stale)
        _backfill_search_text(cur)
        conn.commit()

        cur.execute(f"SELECT COUNT(*) FROM files WHERE {_pending_parse_where()}", (PARSER_VERSION,))
        pending = cur.fetchone()[0]
    finally:
        conn.close()

    return {
        "success": True,
        "total": total_files,
        "indexed": indexed_count,
        "removed": len(stale),
        "fast_mode": use_fast_filename_index,
        "pending_parse": pending,
        "errors": errors
    }


def parse_pending_rows(db_path=None, progress_callback=None, should_stop=None, batch_size=20, retries=2):
    """
    Lê o conteúdo das planilhas que estão no cache só pelo nome do arquivo (ou com
    versão antiga do parser). As planilhas são lidas FORA de transação e gravadas em
    lotes curtos, para nunca segurar o lock de escrita do banco enquanto o Excel é lido.
    Arquivos bloqueados pelo Excel ficam pendentes para a próxima rodada.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    parsed_count = 0
    errors = []
    busy = 0
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT file_path, client_name, car_model, car_year, car_color, visit_num, plate "
            f"FROM files WHERE {_pending_parse_where()} ORDER BY file_mtime DESC",
            (PARSER_VERSION,),
        )
        keys = ("file_path", "client_name", "car_model", "car_year", "car_color", "visit_num", "plate")
        pending = [dict(zip(keys, r)) for r in cur.fetchall()]
        total = len(pending)
        if progress_callback:
            progress_callback(0, total, "")

        for start in range(0, total, batch_size):
            if should_stop and should_stop():
                break
            rows = []
            for i, d in enumerate(pending[start:start + batch_size], start=start):
                fpath = d["file_path"]
                fname = os.path.basename(fpath)
                try:
                    st = os.stat(fpath)
                    parsed = _parse_file_resilient(fpath, retries=retries)
                    rows.append(_row_from_parsed(fpath, parsed, st.st_mtime, st.st_size, fallback=d))
                except FileNotFoundError:
                    pass  # foi apagada; a próxima varredura remove do cache
                except FileBusyError as e:
                    busy += 1
                    errors.append(f"{fname}: {e}")
                except Exception as e:
                    log.warning("Falha ao ler %s: %s", fpath, e)
                    errors.append(f"{fname}: {e}")
                if progress_callback:
                    progress_callback(i + 1, total, fname)
            if rows:
                for row in rows:
                    _upsert_file_row(cur, row)
                conn.commit()
                parsed_count += len(rows)
    finally:
        conn.close()
    return {"parsed": parsed_count, "pending": total, "busy": busy, "errors": errors}


# ------------------------------------------------------------------------------
# Indexação em segundo plano (não trava a UI) com progresso consultável
# ------------------------------------------------------------------------------

_JOB_LOCK = threading.Lock()
_job = {
    "running": False,
    "phase": "idle",          # idle | scan | parse | done | error
    "folder": "",
    "total": 0,
    "done": 0,
    "current_file": "",
    "started_at": None,
    "finished_at": None,
    "scan_result": None,
    "parse_result": None,
    "error": None,
}
_job_rerun = {"requested": False, "scan": False, "folder": None}
_job_thread = None
_job_stop = threading.Event()


def get_index_status():
    """Retrato do progresso da indexação em segundo plano (para /api/index_status)."""
    with _JOB_LOCK:
        snap = dict(_job)
    total = snap.get("total") or 0
    if total:
        snap["percent"] = round(100.0 * snap.get("done", 0) / total, 1)
    else:
        snap["percent"] = 100.0 if snap["phase"] == "done" else 0.0
    for key in ("scan_result", "parse_result"):
        if snap.get(key):
            res = dict(snap[key])
            res["errors"] = list(res.get("errors", []))[:50]
            snap[key] = res
    return snap


def _job_update(**kw):
    with _JOB_LOCK:
        _job.update(kw)


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_index_job(folder, db_path, do_scan):
    global _job_thread
    try:
        while True:
            _job_update(running=True, phase="scan" if do_scan else "parse", folder=folder or "",
                        total=0, done=0, current_file="", error=None,
                        started_at=_now_str(), finished_at=None)
            if do_scan and folder:
                _job_update(scan_result=scan_and_index_folder(folder, db_path, full_parse=False))

            def progress(done, total, fname):
                _job_update(phase="parse", done=done, total=total, current_file=fname)

            pres = parse_pending_rows(db_path, progress_callback=progress, should_stop=_job_stop.is_set)
            _job_update(parse_result=pres)
            with _JOB_LOCK:
                if _job_rerun["requested"] and not _job_stop.is_set():
                    do_scan = _job_rerun["scan"]
                    folder = _job_rerun["folder"] or folder
                    _job_rerun["folder"] = None
                    _job_rerun["requested"] = False
                    _job_rerun["scan"] = False
                    continue
                _job.update(running=False, phase="done", current_file="", finished_at=_now_str())
                _job_thread = None
                break
    except Exception as e:
        log.exception("Falha na indexação em segundo plano")
        with _JOB_LOCK:
            _job.update(running=False, phase="error", error=str(e), finished_at=_now_str())
            _job_thread = None
    finally:
        close_thread_connections()


def start_background_index(folder=None, db_path=None, scan=True):
    """
    Dispara (ou reagenda) a indexação em segundo plano: varredura incremental da
    pasta (se scan=True) seguida da leitura do conteúdo das planilhas pendentes.
    Se já houver uma rodada em andamento, pede outra ao final dela.
    Retorna o status atual.
    """
    global _job_thread
    path = db_path or get_db_path()
    with _JOB_LOCK:
        if _job_thread is not None and _job_thread.is_alive():
            _job_rerun["requested"] = True
            _job_rerun["scan"] = _job_rerun["scan"] or bool(scan)
            if folder:
                _job_rerun["folder"] = folder
        else:
            _job_stop.clear()
            _job.update(running=True, phase="scan" if scan else "parse", folder=folder or "")
            _job_thread = threading.Thread(
                target=_run_index_job, args=(folder, path, bool(scan)),
                name="mecatronicar-indexer", daemon=True,
            )
            _job_thread.start()
    return get_index_status()


def wait_for_background_index(timeout=None):
    """Espera a indexação em segundo plano terminar (útil em testes e scripts)."""
    th = _job_thread
    if th is not None:
        th.join(timeout)
    return get_index_status()


def stop_background_index(timeout=5.0):
    _job_stop.set()
    return wait_for_background_index(timeout)


def get_stats(db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
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
    conn = _connect(path)
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
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    query_raw = query.strip()
    query_clean = remove_accents(query_raw).lower()
    query_plate = clean_plate(query_raw)
    
    def _like(s):
        return "%" + s.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"

    # search_text = placa + cliente + modelo + nome do arquivo + reclamação, já em
    # minúsculas e sem acento (calculado na indexação). Linhas sem search_text (gravadas
    # por código externo) caem no filtro antigo, campo a campo.
    like_query = _like(query_clean)
    plate_like = _like(query_plate) if query_plate else None
    cur.execute("""
    SELECT 
        file_path, file_name, plate, plate_clean, plate_display,
        client_name, car_model, car_year, car_color, visit_num,
        entry_date, entry_date_sort, odometer, odometer_int,
        complaint, data_json
    FROM files
    WHERE
        (? IS NOT NULL AND plate_clean LIKE ? ESCAPE '!') OR
        (search_text IS NOT NULL AND search_text LIKE ? ESCAPE '!') OR
        (search_text IS NULL AND (
            plate_clean LIKE ? ESCAPE '!' OR
            client_clean LIKE ? ESCAPE '!' OR
            LOWER(car_model) LIKE ? ESCAPE '!' OR
            LOWER(file_name) LIKE ? ESCAPE '!' OR
            LOWER(complaint) LIKE ? ESCAPE '!'
        ))
    ORDER BY entry_date_sort DESC, odometer_int DESC, CAST(visit_num AS INTEGER) DESC
    LIMIT 60
    """, (
        plate_like, plate_like,
        like_query,
        _like(query_clean.upper()), like_query, like_query, like_query, like_query
    ))

    rows = [dict(r) for r in cur.fetchall()]
    unique_plates = {r.get("plate_clean") for r in rows if r.get("plate_clean")}

    # Se a busca já filtrou um único veículo (ou poucos arquivos), lê sob demanda as planilhas encontradas
    max_lazy_parse = len(rows) if len(unique_plates) <= 1 else min(len(rows), 20)
    try:
        results = _ensure_rows_parsed(conn, cur, rows, max_parse=max_lazy_parse)
    finally:
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

def _ensure_rows_parsed(conn, cur, rows, max_parse=None):
    """
    Versão em lote de _ensure_row_parsed: decodifica o data_json de cada linha e, para
    as que ainda não têm conteúdo lido (até max_parse), lê a planilha FORA de transação
    e grava tudo de uma vez no final.
    """
    to_write = []
    parsed_budget = len(rows) if max_parse is None else max_parse
    for d in rows:
        dj = d.get("data_json")
        if dj:
            try:
                loaded = json.loads(dj)
                if loaded.get("parser_version") == PARSER_VERSION and "servicos_items" in loaded:
                    d["details"] = loaded
                    continue
            except ValueError:
                log.warning("data_json inválido no cache para %s", d.get("file_path"))
            if parsed_budget <= 0:
                try:
                    d["details"] = json.loads(dj)
                except ValueError:
                    d["details"] = None
                continue
        if parsed_budget <= 0:
            d["details"] = None
            continue
        fpath = d.get("file_path", "")
        if not fpath or not os.path.exists(fpath):
            d["details"] = None
            continue
        parsed_budget -= 1
        try:
            st = os.stat(fpath)
            parsed = _parse_file_resilient(fpath)
        except FileBusyError as e:
            log.info("Leitura sob demanda adiada (%s): %s", os.path.basename(fpath), e)
            d["details"] = None
            continue
        except Exception:
            log.exception("Falha ao ler a planilha %s", fpath)
            d["details"] = None
            continue
        row = _row_from_parsed(fpath, parsed, st.st_mtime, st.st_size, fallback=d)
        to_write.append(row)
        d.update(row)
        d["details"] = parsed
    if to_write:
        for row in to_write:
            _upsert_file_row(cur, row)
            row.pop("search_text", None)
        conn.commit()
    for d in rows:
        d.pop("search_text", None)
    return rows


def _nf_controls_by_file_path(cur, file_paths):
    """{file_path: linha de nf_control (a primeira, como get_nf_control)} em lote."""
    paths = [p for p in dict.fromkeys(file_paths) if p]
    found = {}
    for i in range(0, len(paths), 500):
        chunk = paths[i:i + 500]
        cur.execute(
            f"SELECT * FROM nf_control WHERE file_path IN ({','.join('?' * len(chunk))}) ORDER BY id",
            chunk,
        )
        cols = [c[0] for c in cur.description]
        for r in cur.fetchall():
            rd = dict(zip(cols, r))
            found.setdefault(rd["file_path"], rd)
    return found


def get_car_history(plate, db_path=None):
    if not plate:
        return []
        
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    p_clean = clean_plate(plate)
    if not p_clean:
        conn.close()
        return []

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
    try:
        results = _ensure_rows_parsed(conn, cur, rows)
        nf_map = _nf_controls_by_file_path(cur, [d.get("file_path") for d in results])
    finally:
        conn.close()

    results.sort(
        key=lambda x: (
            x.get("entry_date_sort") or "0000-00-00",
            x.get("odometer_int") or 0,
            parse_visit_int(x.get("visit_num"))
        ),
        reverse=True
    )

    # Equivalente a get_nf_control(file_path=...) por visita, mas numa única consulta.
    for d in results:
        nf = nf_map.get(d.get("file_path"))
        if nf is not None:
            nf = dict(nf)
            for k in ("client_name", "car_model", "car_year", "car_color", "plate_display", "entry_date"):
                nf.setdefault(k, d.get(k))
            nf = _format_nf_dict(nf)
        d["nf_control"] = nf

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
    conn = _connect(path)
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
    conn = _connect(path)
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
    conn = _connect(path)
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
    conn = _connect(path)
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
    raw_p = d.get("plate") or d.get("plate_display") or d.get("plate_clean") or ""
    if not d.get("plate"):
        d["plate"] = raw_p
    if not d.get("plate_clean"):
        d["plate_clean"] = clean_plate(raw_p) if raw_p else ""
    if not d.get("plate_display"):
        d["plate_display"] = format_plate_display(raw_p) if raw_p else ""
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
    conn = _connect(path)
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
    raw_rows = [dict(r) for r in cur.fetchall()]

    rows = []
    for row in raw_rows:
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
        rows.append(_format_nf_dict(row))

    conn.close()
    return rows

def get_nf_control(id=None, file_path=None, plate_clean=None, visit_num=None, db_path=None):
    """
    Obtém registro de controle de nota fiscal por id, file_path ou par (plate_clean, visit_num).
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = None
    if id is not None:
        cur.execute("SELECT * FROM nf_control WHERE id = ?", (id,))
        row = cur.fetchone()
    elif file_path:
        cur.execute("SELECT * FROM nf_control WHERE file_path = ?", (file_path,))
        row = cur.fetchone()
    elif plate_clean and visit_num is not None and str(visit_num).strip() != "":
        p_clean = clean_plate(plate_clean)
        cur.execute("SELECT * FROM nf_control WHERE plate_clean = ? AND visit_num = ?", (p_clean, str(visit_num).strip()))
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

    formatted_res = _format_nf_dict(res)
    conn.close()
    return formatted_res

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
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    raw_plate = plate_clean or kwargs.get("plate", "")
    p_clean = clean_plate(raw_plate) if raw_plate else ""
    v_num = str(visit_num).strip() if visit_num is not None else ""

    client_name = kwargs.get("client_name", "")
    car_model = kwargs.get("car_model", "")
    entry_date = kwargs.get("entry_date", "")
    plate_disp = kwargs.get("plate_display", "") or (format_plate_display(raw_plate) if raw_plate else "")

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
    conn = _connect(path)
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
    Fila de notas fiscais. O resultado fica em cache até alguma planilha ou registro
    fiscal mudar (contadores de mudança do banco). Não modifique o dict retornado.
    """
    path = db_path or get_db_path()
    return _cached_result("nf_queue", path, (filter_type, query or ""), ("files", "nf_control"),
                          lambda: _compute_nf_queue(filter_type, query, path))


def _compute_nf_queue(filter_type='pending', query='', db_path=None):
    """
    Retorna a fila de notas fiscais da oficina (pendentes, emitidas ou todas),
    cruzando dados de files com nf_control para garantir que nenhuma visita fique esquecida.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            f.file_path, f.file_name, f.plate, f.plate_clean, f.plate_display,
            f.client_name, f.client_clean, f.car_model, f.car_year, f.car_color,
            f.visit_num, f.entry_date, f.entry_date_sort, f.odometer, f.odometer_int,
            f.complaint, f.data_json,
            n.id as nf_id, n.notes, n.updated_at as updated_time,
            n.nfse_status, n.nfse_number, n.valor_servico, n.data_emissao_servico,
            n.nfe_status, n.nfe_number, n.valor_pecas, n.data_emissao_pecas
        FROM files f
        LEFT JOIN nf_control n ON (
            (n.file_path IS NOT NULL AND n.file_path != '' AND f.file_path = n.file_path) OR
            (n.plate_clean = f.plate_clean AND n.visit_num IS NOT NULL AND n.visit_num != '' AND f.visit_num = n.visit_num)
        )
        UNION ALL
        SELECT 
            n.file_path, '' as file_name, n.plate, n.plate_clean, n.plate_display,
            n.client_name, '' as client_clean, n.car_model, '' as car_year, '' as car_color,
            n.visit_num, n.entry_date, '' as entry_date_sort, '' as odometer, 0 as odometer_int,
            '' as complaint, '' as data_json,
            n.id as nf_id, n.notes, n.updated_at as updated_time,
            n.nfse_status, n.nfse_number, n.valor_servico, n.data_emissao_servico,
            n.nfe_status, n.nfe_number, n.valor_pecas, n.data_emissao_pecas
        FROM nf_control n
        WHERE (n.file_path IS NULL OR n.file_path = '' OR n.file_path NOT IN (SELECT file_path FROM files WHERE file_path IS NOT NULL AND file_path != ''))
          AND (n.plate_clean NOT IN (SELECT plate_clean FROM files WHERE plate_clean IS NOT NULL AND plate_clean != ''))
        ORDER BY entry_date_sort DESC, odometer_int DESC
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
        if val_serv == 0.0 and r["valor_servico"]:
            try:
                val_serv = float(r["valor_servico"])
            except Exception:
                pass

        val_pec = parse_currency_float(tot_pecas_str)
        if val_pec == 0.0 and r["valor_pecas"]:
            try:
                val_pec = float(r["valor_pecas"])
            except Exception:
                pass

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
        date_serv = r["data_emissao_servico"] or ""
        num_pec = r["nfe_number"] or ""
        date_pec = r["data_emissao_pecas"] or ""

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

    return {"queue": items, "items": items, "stats": stats}

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

def save_nf_control(data=None, db_path=None, **kwargs):
    payload = {}
    if isinstance(data, dict):
        payload.update(data)
    elif data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return update_nf_control(db_path=db_path, **payload)

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
    conn = _connect(path)
    cur = conn.cursor()
    
    # Lê a planilha antes de abrir a transação (não segura o lock de escrita no parse).
    st = os.stat(fpath)
    parsed = parse_file(fpath)
    row = _row_from_parsed(fpath, parsed, st.st_mtime, st.st_size)
    row["file_name"] = os.path.basename(fpath)
    try:
        if old_fpath and old_fpath != fpath:
            cur.execute("DELETE FROM files WHERE file_path = ?", (old_fpath,))
        _upsert_file_row(cur, row)
        conn.commit()
    finally:
        conn.close()
    return parsed

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
        conn = _connect(path)
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

# ==============================================================================
# ANALYTICS E MÉTRICAS DA OFICINA (Issue #16)
# ==============================================================================

def parse_any_date(date_val):
    """Converte valores variados de data (strings DD/MM/AAAA, AAAA-MM-DD, DD/MM/AA ou objetos date) em datetime.date."""
    if not date_val:
        return None
    if isinstance(date_val, datetime.date):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    s = str(date_val).strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', s)
    if m:
        d, mo, y = map(int, m.groups())
        y += 2000 if y < 50 else 1900
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None
    return None


def get_analytics(period='30', db_path=None, ref_date=None):
    """
    Métricas da oficina (ver _compute_analytics). O resultado fica em cache até alguma
    planilha ou registro fiscal mudar, ou o dia virar. Não modifique o dict retornado.
    """
    path = db_path or get_db_path()
    key = (str(period), ref_date or "", datetime.date.today().isoformat())
    return _cached_result("analytics", path, key, ("files", "nf_control"),
                          lambda: _compute_analytics(period, path, ref_date))


def _compute_analytics(period='30', db_path=None, ref_date=None):
    """
    Agregação e cálculo de métricas analíticas da oficina mecânica (Issue #16):
    - Volume de carros atendidos (total e médias por dia, semana e mês)
    - Tempo médio de permanência (dias desde a data de entrada até a saída/entrega)
    - Médias financeiras (valor médio de peças por OS, valor médio de mão de obra por serviço/visita)
    - Filtros por período: '30' (últimos 30 dias), '90' (últimos 90 dias) ou 'all' (geral)
    """
    path = db_path or get_db_path()
    init_db(path)
    
    # Define a data de referência
    if ref_date:
        today = parse_any_date(ref_date) or datetime.date.today()
    else:
        today = datetime.date.today()
        
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Carrega lookup fiscal de nf_control para complementar eventuais ordens sem preços no json
    nf_lookup = {}
    try:
        cur.execute("SELECT file_path, plate_clean, visit_num, valor_servico, valor_pecas FROM nf_control")
        for row in cur.fetchall():
            fp = row["file_path"] or ""
            pc = row["plate_clean"] or ""
            vn = str(row["visit_num"] or "")
            vs = float(row["valor_servico"] or 0.0)
            vp = float(row["valor_pecas"] or 0.0)
            if fp:
                nf_lookup[fp] = (vs, vp)
            if pc:
                nf_lookup[(pc, vn)] = (vs, vp)
    except Exception:
        pass
        
    cur.execute("""
    SELECT file_path, file_name, plate, plate_clean, plate_display,
           client_name, car_model, car_year, car_color, visit_num,
           entry_date, entry_date_sort, data_json
    FROM files
    """)
    rows = cur.fetchall()
    conn.close()
    
    all_records = []
    
    for r in rows:
        dj_str = r["data_json"]
        d = {}
        if dj_str:
            try:
                d = json.loads(dj_str)
            except Exception:
                d = {}
                
        # Data de entrada
        entry_raw = r["entry_date"] or d.get("entry_date") or r["entry_date_sort"]
        ed = parse_any_date(entry_raw)
        
        # Data de saída / entrega
        exit_raw = d.get("exit_date") or d.get("delivery_date") or d.get("data_saida") or d.get("data_entrega") or ""
        exd = parse_any_date(exit_raw)
        
        # Tempo de permanência em dias
        stay_days = None
        if ed and exd and exd >= ed:
            stay_days = (exd - ed).days
            
        # Valores financeiros de autopeças
        tp = parse_currency_float(d.get("total_pecas"))
        if tp == 0.0:
            for item in d.get("pecas_items", []):
                t_item = parse_currency_float(item.get("total_price"))
                if t_item > 0:
                    tp += t_item
                else:
                    u_item = parse_currency_float(item.get("unit_price"))
                    q_val = item.get("quantity") or 1
                    try:
                        q_num = float(q_val)
                    except Exception:
                        q_num = 1.0
                    if u_item > 0:
                        tp += u_item * q_num
                        
        # Valores financeiros de mão de obra (serviços)
        ts = parse_currency_float(d.get("total_servicos"))
        if ts == 0.0:
            for item in d.get("servicos_items", []):
                t_item = parse_currency_float(item.get("total_price"))
                if t_item > 0:
                    ts += t_item
                else:
                    u_item = parse_currency_float(item.get("unit_price"))
                    q_val = item.get("quantity") or 1
                    try:
                        q_num = float(q_val)
                    except Exception:
                        q_num = 1.0
                    if u_item > 0:
                        ts += u_item * q_num
                        
        # Fallback de valores via nf_control se zerados
        if tp == 0.0 and ts == 0.0:
            fp = r["file_path"] or ""
            pc = r["plate_clean"] or ""
            vn = str(r["visit_num"] or "")
            if fp in nf_lookup:
                ts, tp = nf_lookup[fp]
            elif (pc, vn) in nf_lookup:
                ts, tp = nf_lookup[(pc, vn)]
                
        tot = parse_currency_float(d.get("total"))
        if tot == 0.0:
            tot = tp + ts
            
        record = {
            "file_path": r["file_path"],
            "file_name": r["file_name"],
            "plate": r["plate"] or "",
            "plate_clean": r["plate_clean"] or "",
            "plate_display": r["plate_display"] or r["plate"] or "",
            "client_name": r["client_name"] or "",
            "car_model": r["car_model"] or "",
            "visit_num": r["visit_num"] or "1",
            "entry_date": ed,
            "entry_date_str": ed.strftime("%d/%m/%Y") if ed else (r["entry_date"] or ""),
            "exit_date": exd,
            "exit_date_str": exd.strftime("%d/%m/%Y") if exd else (exit_raw or ""),
            "stay_days": stay_days,
            "parts_val": round(tp, 2),
            "labor_val": round(ts, 2),
            "total_val": round(tot, 2)
        }
        all_records.append(record)
        
    # Filtro por período
    p = str(period).lower().strip()
    if p in ("30", "30d", "30_days", "30dias"):
        cutoff = today - datetime.timedelta(days=30)
        filtered = [rec for rec in all_records if rec["entry_date"] and rec["entry_date"] >= cutoff]
        days_span = 30
        period_label = "Últimos 30 Dias"
        period_key = "30"
    elif p in ("90", "90d", "90_days", "90dias"):
        cutoff = today - datetime.timedelta(days=90)
        filtered = [rec for rec in all_records if rec["entry_date"] and rec["entry_date"] >= cutoff]
        days_span = 90
        period_label = "Últimos 90 Dias"
        period_key = "90"
    else:
        filtered = list(all_records)
        dates_with_values = [rec["entry_date"] for rec in all_records if rec["entry_date"]]
        if dates_with_values:
            min_d = min(dates_with_values)
            max_d = max(dates_with_values)
            days_span = max(1, (max_d - min_d).days + 1)
        else:
            days_span = 30
        period_label = "Geral (Todo o Período)"
        period_key = "all"
        
    # 1. Métricas de Volume de Carros
    total_cars = len(set(r["plate_clean"] for r in filtered if r["plate_clean"]))
    total_orders = len(filtered)
    weeks_span = max(1.0, days_span / 7.0)
    months_span = max(1.0, days_span / 30.0)
    
    avg_cars_per_day = round(total_cars / days_span, 2) if days_span > 0 else 0.0
    avg_cars_per_week = round(total_cars / weeks_span, 2) if weeks_span > 0 else 0.0
    avg_cars_per_month = round(total_cars / months_span, 2) if months_span > 0 else 0.0
    
    avg_orders_per_day = round(total_orders / days_span, 2) if days_span > 0 else 0.0
    avg_orders_per_week = round(total_orders / weeks_span, 2) if weeks_span > 0 else 0.0
    avg_orders_per_month = round(total_orders / months_span, 2) if months_span > 0 else 0.0
    
    active_days = set(r["entry_date"] for r in filtered if r["entry_date"])
    active_days_count = len(active_days)
    
    # 2. Tempo Médio de Permanência
    stays = [r["stay_days"] for r in filtered if r["stay_days"] is not None]
    stays_count = len(stays)
    avg_stay_days = round(sum(stays) / stays_count, 1) if stays_count > 0 else 0.0
    min_stay = min(stays) if stays_count > 0 else 0
    max_stay = max(stays) if stays_count > 0 else 0
    
    stay_dist = {
        "same_day": sum(1 for s in stays if s == 0),
        "days_1_to_3": sum(1 for s in stays if 1 <= s <= 3),
        "days_4_to_7": sum(1 for s in stays if 4 <= s <= 7),
        "days_over_7": sum(1 for s in stays if s > 7)
    }
    
    if stays_count == 0:
        avg_stay_text = "Sem registros finalizados"
    elif avg_stay_days == 1.0:
        avg_stay_text = "1,0 dia"
    else:
        avg_stay_text = f"{avg_stay_days:.1f}".replace(".", ",") + " dias"
        
    # 3. Métricas Financeiras Médias
    tot_parts = round(sum(r["parts_val"] for r in filtered), 2)
    tot_labor = round(sum(r["labor_val"] for r in filtered), 2)
    tot_revenue = round(tot_parts + tot_labor, 2)
    
    orders_with_parts = [r for r in filtered if r["parts_val"] > 0]
    orders_with_labor = [r for r in filtered if r["labor_val"] > 0]
    orders_billed = [r for r in filtered if r["total_val"] > 0]
    
    avg_parts_order = round(tot_parts / total_orders, 2) if total_orders > 0 else 0.0
    avg_parts_billed = round(tot_parts / len(orders_with_parts), 2) if orders_with_parts else 0.0
    
    avg_labor_order = round(tot_labor / total_orders, 2) if total_orders > 0 else 0.0
    avg_labor_billed = round(tot_labor / len(orders_with_labor), 2) if orders_with_labor else 0.0
    
    avg_ticket_order = round(tot_revenue / total_orders, 2) if total_orders > 0 else 0.0
    avg_ticket_billed = round(tot_revenue / len(orders_billed), 2) if orders_billed else 0.0
    
    parts_pct = round((tot_parts / tot_revenue) * 100, 1) if tot_revenue > 0 else 0.0
    labor_pct = round((tot_labor / tot_revenue) * 100, 1) if tot_revenue > 0 else 0.0
    
    # 4. Tendência Mensal (Monthly Trend)
    months_map = {}
    month_names = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    for r in filtered:
        ed = r["entry_date"]
        if not ed:
            continue
        m_key = ed.strftime("%Y-%m")
        if m_key not in months_map:
            lbl = f"{month_names[ed.month]}/{ed.year}"
            months_map[m_key] = {
                "month": m_key,
                "label": lbl,
                "cars_set": set(),
                "orders": 0,
                "parts": 0.0,
                "labor": 0.0,
                "total": 0.0
            }
        m_entry = months_map[m_key]
        if r["plate_clean"]:
            m_entry["cars_set"].add(r["plate_clean"])
        m_entry["orders"] += 1
        m_entry["parts"] += r["parts_val"]
        m_entry["labor"] += r["labor_val"]
        m_entry["total"] += r["total_val"]
        
    monthly_trend = []
    for m_key in sorted(months_map.keys()):
        item = months_map[m_key]
        monthly_trend.append({
            "month": item["month"],
            "label": item["label"],
            "cars": len(item["cars_set"]),
            "orders": item["orders"],
            "parts": round(item["parts"], 2),
            "labor": round(item["labor"], 2),
            "total": round(item["total"], 2)
        })
        
    # 5. Ordens Recentes (para visualização detalhada no dashboard)
    sorted_recent = sorted(
        filtered,
        key=lambda x: (x["entry_date"] or datetime.date(2000, 1, 1), x["visit_num"]),
        reverse=True
    )
    recent_orders = []
    for r in sorted_recent[:15]:
        recent_orders.append({
            "plate": r["plate"],
            "plate_clean": r["plate_clean"],
            "plate_display": r["plate_display"],
            "client_name": r["client_name"],
            "car_model": r["car_model"],
            "visit_num": r["visit_num"],
            "entry_date": r["entry_date_str"],
            "exit_date": r["exit_date_str"],
            "stay_days": r["stay_days"],
            "parts_val": r["parts_val"],
            "labor_val": r["labor_val"],
            "total_val": r["total_val"]
        })
        
    return {
        "period": period_key,
        "period_label": period_label,
        "days_span": days_span,
        "volume": {
            "total_cars": total_cars,
            "total_orders": total_orders,
            "avg_cars_per_day": avg_cars_per_day,
            "avg_cars_per_week": avg_cars_per_week,
            "avg_cars_per_month": avg_cars_per_month,
            "avg_orders_per_day": avg_orders_per_day,
            "avg_orders_per_week": avg_orders_per_week,
            "avg_orders_per_month": avg_orders_per_month,
            "active_days_count": active_days_count
        },
        "stay_time": {
            "avg_stay_days": avg_stay_days,
            "avg_stay_text": avg_stay_text,
            "min_stay_days": min_stay,
            "max_stay_days": max_stay,
            "stays_measured_count": stays_count,
            "distribution": stay_dist
        },
        "financials": {
            "total_parts": tot_parts,
            "total_labor": tot_labor,
            "total_revenue": tot_revenue,
            "avg_parts_per_order": avg_parts_order,
            "avg_parts_per_billed_order": avg_parts_billed,
            "avg_labor_per_order": avg_labor_order,
            "avg_labor_per_billed_order": avg_labor_billed,
            "avg_ticket_order": avg_ticket_order,
            "avg_ticket_billed_order": avg_ticket_billed,
            "parts_percentage": parts_pct,
            "labor_percentage": labor_pct,
            "orders_with_parts_count": len(orders_with_parts),
            "orders_with_labor_count": len(orders_with_labor),
            "orders_billed_count": len(orders_billed)
        },
        "monthly_trend": monthly_trend,
        "recent_orders": recent_orders
    }

# ==============================================================================
# MÓDULO DE AGENDAMENTOS / CALENDÁRIO (Issue #15)
# ==============================================================================

VALID_AGENDAMENTO_STATUSES = [
    "agendado",
    "confirmado",
    "concluido",
    "cancelado"
]

def _normalize_date_iso(date_str):
    """
    Normaliza datas no formato DD/MM/AAAA ou AAAA-MM-DD para AAAA-MM-DD.
    """
    if not date_str:
        return datetime.date.today().isoformat()
    s = str(date_str).strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        day, month, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    m2 = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
    if m2:
        year, month, day = m2.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return s

def _format_date_br(date_iso_str):
    """
    Converte AAAA-MM-DD para DD/MM/AAAA.
    """
    if not date_iso_str:
        return ""
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(date_iso_str).strip())
    if m:
        year, month, day = m.groups()
        return f"{day}/{month}/{year}"
    return str(date_iso_str)

def _format_agendamento_dict(row_dict):
    """
    Garante chaves e formatações padronizadas para agendamentos.
    """
    if not row_dict:
        return None
    d = dict(row_dict)
    sched_date = d.get("scheduled_date") or ""
    d["scheduled_date_iso"] = sched_date
    d["scheduled_date_display"] = _format_date_br(sched_date)
    
    plate = d.get("car_plate") or ""
    clean = clean_plate(plate)
    d["car_plate_clean"] = clean
    d["car_plate_display"] = format_plate_display(plate) if plate else ""
    
    if not d.get("scheduled_time"):
        d["scheduled_time"] = "08:00"

    status = (d.get("status") or "agendado").lower().strip()
    if status in ["atendido", "finalizado"]:
        status = "concluido"
    d["status"] = status
    
    return d

def create_agendamento(data, db_path=None):
    """
    Insere um novo agendamento no banco de dados SQLite.
    """
    if not data:
        raise ValueError("Dados do agendamento não podem ser vazios.")
    
    client_name = str(data.get("client_name") or "").strip()
    title = str(data.get("title") or "").strip()
    if not client_name:
        raise ValueError("Nome do cliente é obrigatório.")
    if not title:
        raise ValueError("Título do problema / serviço é obrigatório.")
        
    phone = str(data.get("phone") or "").strip()
    raw_plate = str(data.get("car_plate") or data.get("plate") or "").strip()
    plate_clean = clean_plate(raw_plate)
    plate_disp = format_plate_display(raw_plate) if raw_plate else ""
    car_model = str(data.get("car_model") or data.get("model") or "").strip()
    description = str(data.get("description") or data.get("complaint") or "").strip()
    
    sched_date = _normalize_date_iso(data.get("scheduled_date") or data.get("date"))
    sched_time = str(data.get("scheduled_time") or data.get("time") or "08:00").strip()
    status = str(data.get("status") or "agendado").strip().lower()
    if status in ["atendido", "finalizado"]:
        status = "concluido"
    notes = str(data.get("notes") or "").strip()
    gcal_id = str(data.get("google_calendar_id") or "").strip()
    gcal_status = str(data.get("google_calendar_sync_status") or "pending").strip()

    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO agendamentos (
        client_name, phone, car_plate, car_plate_clean, car_model,
        title, description, scheduled_date, scheduled_time,
        status, created_at, updated_at, notes,
        google_calendar_id, google_calendar_sync_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_name, phone, plate_disp or raw_plate, plate_clean, car_model,
        title, description, sched_date, sched_time,
        status, now_iso, now_iso, notes,
        gcal_id, gcal_status
    ))
    new_id = cur.lastrowid
    conn.commit()

    cur.execute("SELECT * FROM agendamentos WHERE id = ?", (new_id,))
    row = cur.fetchone()
    conn.close()

    return _format_agendamento_dict(dict(row))

def get_agendamento(agendamento_id, db_path=None):
    """
    Retorna um agendamento pelo ID.
    """
    path = db_path or get_db_path()
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agendamentos WHERE id = ?", (agendamento_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return _format_agendamento_dict(dict(row))

def list_agendamentos(date_from=None, date_to=None, date=None, status=None, query=None, limit=200, db_path=None):
    """
    Lista agendamentos com filtros opcionais de data, status e busca textual.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    conditions = []
    params = []

    if date:
        date_iso = _normalize_date_iso(date)
        conditions.append("scheduled_date = ?")
        params.append(date_iso)
    else:
        if date_from:
            date_from_iso = _normalize_date_iso(date_from)
            conditions.append("scheduled_date >= ?")
            params.append(date_from_iso)
        if date_to:
            date_to_iso = _normalize_date_iso(date_to)
            conditions.append("scheduled_date <= ?")
            params.append(date_to_iso)

    if status:
        if isinstance(status, (list, tuple)):
            placeholders = ",".join(["?"] * len(status))
            conditions.append(f"LOWER(status) IN ({placeholders})")
            params.extend([str(s).lower().strip() for s in status])
        else:
            s_clean = str(status).lower().strip()
            if s_clean not in ["todos", "all", ""]:
                conditions.append("LOWER(status) = ?")
                params.append(s_clean)

    if query:
        q_term = f"%{query.strip().lower()}%"
        q_plate = f"%{clean_plate(query)}%"
        conditions.append("(LOWER(client_name) LIKE ? OR LOWER(car_model) LIKE ? OR LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR car_plate_clean LIKE ?)")
        params.extend([q_term, q_term, q_term, q_term, q_plate])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM agendamentos
    {where_clause}
    ORDER BY scheduled_date ASC, scheduled_time ASC, id ASC
    LIMIT ?
    """
    params.append(limit)

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()

    return [_format_agendamento_dict(dict(r)) for r in rows]

def update_agendamento(agendamento_id, data, db_path=None):
    """
    Atualiza campos de um agendamento existente.
    """
    if not agendamento_id:
        return None
    
    path = db_path or get_db_path()
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM agendamentos WHERE id = ?", (agendamento_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        return None

    fields_map = {
        "client_name": "client_name",
        "phone": "phone",
        "car_plate": "car_plate",
        "car_model": "car_model",
        "title": "title",
        "description": "description",
        "scheduled_date": "scheduled_date",
        "scheduled_time": "scheduled_time",
        "status": "status",
        "notes": "notes",
        "google_calendar_id": "google_calendar_id",
        "google_calendar_sync_status": "google_calendar_sync_status"
    }

    updates = []
    params = []

    for key, col in fields_map.items():
        if key in data:
            val = data[key]
            if key == "scheduled_date":
                val = _normalize_date_iso(val)
            elif key == "car_plate":
                val = format_plate_display(val) if val else ""
                updates.append("car_plate_clean = ?")
                params.append(clean_plate(val))
            elif key == "status" and val:
                val = str(val).lower().strip()
                if val in ["atendido", "finalizado"]:
                    val = "concluido"
            updates.append(f"{col} = ?")
            params.append(val)

    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates.append("updated_at = ?")
    params.append(now_iso)

    params.append(agendamento_id)
    cur.execute(f"UPDATE agendamentos SET {', '.join(updates)} WHERE id = ?", tuple(params))
    conn.commit()

    cur.execute("SELECT * FROM agendamentos WHERE id = ?", (agendamento_id,))
    updated = cur.fetchone()
    conn.close()

    return _format_agendamento_dict(dict(updated))

def update_agendamento_status(agendamento_id, status, db_path=None):
    """
    Helper rápido para transição de status do agendamento.
    """
    return update_agendamento(agendamento_id, {"status": status}, db_path=db_path)

def delete_agendamento(agendamento_id, db_path=None):
    """
    Remove um agendamento do banco de dados.
    """
    if not agendamento_id:
        return False
    path = db_path or get_db_path()
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("DELETE FROM agendamentos WHERE id = ?", (agendamento_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# ==============================================================================
# CALENDÁRIO / AGENDAMENTOS DA OFICINA (agenda_events) - Issue #11
# ==============================================================================

def list_agenda_events(start_date=None, end_date=None, status=None, db_path=None):
    """
    Lista agendamentos e eventos futuros da oficina, ordenados por data e horário.
    """
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = "SELECT * FROM agenda_events WHERE 1=1"
    params = []
    if start_date:
        query += " AND event_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND event_date <= ?"
        params.append(end_date)
    if status:
        query += " AND (status = ? OR LOWER(status) = ?)"
        params.extend([status, status.lower()])

    query += " ORDER BY event_date ASC, event_time ASC, id ASC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_agenda_event(event_id, db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agenda_events WHERE id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def save_agenda_event(data, db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    cur = conn.cursor()

    rec_id = data.get("id")
    title = (data.get("title") or "").strip()
    client_name = (data.get("client_name") or "").strip()
    plate = (data.get("plate") or "").strip().upper()
    p_clean = clean_plate(plate) if plate else ""
    p_disp = format_plate_display(plate) if plate else ""
    car_model = (data.get("car_model") or "").strip()
    service_type = (data.get("service_type") or "").strip()
    event_date = (data.get("event_date") or "").strip() or datetime.date.today().strftime("%Y-%m-%d")
    event_time = (data.get("event_time") or "").strip() or "09:00"
    notes = (data.get("notes") or "").strip()
    status = (data.get("status") or "Agendado").strip()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Se car_model ou client_name estiverem vazios mas tiver placa, busca no cache de arquivos
    if p_clean and (not car_model or not client_name):
        cur.execute("SELECT client_name, car_model FROM files WHERE plate_clean = ? LIMIT 1", (p_clean,))
        matched = cur.fetchone()
        if matched:
            if not client_name and matched[0]:
                client_name = matched[0]
            if not car_model and matched[1]:
                car_model = matched[1]

    if not title:
        title = service_type or f"Atendimento {car_model or plate or 'Veículo'}"

    if rec_id:
        cur.execute("""
        UPDATE agenda_events SET
            title = ?, client_name = ?, plate = ?, plate_clean = ?, plate_display = ?,
            car_model = ?, service_type = ?, event_date = ?, event_time = ?,
            notes = ?, status = ?
        WHERE id = ?
        """, (
            title, client_name, plate, p_clean, p_disp,
            car_model, service_type, event_date, event_time,
            notes, status, rec_id
        ))
        saved_id = rec_id
    else:
        cur.execute("""
        INSERT INTO agenda_events (
            title, client_name, plate, plate_clean, plate_display,
            car_model, service_type, event_date, event_time,
            notes, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, client_name, plate, p_clean, p_disp,
            car_model, service_type, event_date, event_time,
            notes, status, now_str
        ))
        saved_id = cur.lastrowid

    conn.commit()
    conn.close()
    return get_agenda_event(saved_id, db_path=path)

def update_agenda_event_status(event_id, status, db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("UPDATE agenda_events SET status = ? WHERE id = ?", (status, event_id))
    conn.commit()
    conn.close()
    return get_agenda_event(event_id, db_path=path)

def delete_agenda_event(event_id, db_path=None):
    path = db_path or get_db_path()
    init_db(path)
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("DELETE FROM agenda_events WHERE id = ?", (event_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def seed_sample_agenda_if_empty(db_path=None):
    path = db_path or get_db_path()
    events = list_agenda_events(db_path=path)
    if len(events) > 0:
        return events
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    day_after = today + datetime.timedelta(days=2)
    next_week = today + datetime.timedelta(days=4)

    samples = [
        {
            "title": "Revisão Preventiva e Troca de Óleo",
            "client_name": "Danilo Pereira",
            "plate": "FNB-1A77",
            "car_model": "VW Fox 1.0 - Prata",
            "service_type": "Troca de Óleo / Revisão",
            "event_date": today.strftime("%Y-%m-%d"),
            "event_time": "14:30",
            "notes": "Cliente solicitou verificar barulho no freio ao parar no sinal.",
            "status": "Confirmado"
        },
        {
            "title": "Alinhamento 3D e Balanceamento",
            "client_name": "Marcos Antônio",
            "plate": "FQE-5724",
            "car_model": "Nissan Sentra - Prata",
            "service_type": "Alinhamento / Balanceamento",
            "event_date": today.strftime("%Y-%m-%d"),
            "event_time": "16:00",
            "notes": "Volante puxando levemente para a direita.",
            "status": "Agendado"
        },
        {
            "title": "Diagnóstico de Injeção Eletrônica",
            "client_name": "Cauê Raquel",
            "plate": "EVI-2484",
            "car_model": "Nissan Sentra - Prata",
            "service_type": "Diagnóstico Scanner",
            "event_date": tomorrow.strftime("%Y-%m-%d"),
            "event_time": "09:00",
            "notes": "Luz da injeção acendendo em marcha lenta.",
            "status": "Agendado"
        },
        {
            "title": "Substituição de Correia Dentada e Tensor",
            "client_name": "Natanael Santos",
            "plate": "DTZ-9080",
            "car_model": "Peugeot Partner - Branco",
            "service_type": "Correia Dentada",
            "event_date": day_after.strftime("%Y-%m-%d"),
            "event_time": "10:30",
            "notes": "Revisão preventiva por tempo de uso (5 anos).",
            "status": "Agendado"
        },
        {
            "title": "Revisão Geral e Suspensão",
            "client_name": "Juliana Lima",
            "plate": "BRA-2E19",
            "car_model": "Honda Civic - Preto",
            "service_type": "Suspensão",
            "event_date": next_week.strftime("%Y-%m-%d"),
            "event_time": "13:30",
            "notes": "Troca de buchas e batentes dianteiros.",
            "status": "Agendado"
        }
    ]
    for s in samples:
        save_agenda_event(s, db_path=path)
    return list_agenda_events(db_path=path)

def seed_sample_patio_if_empty(db_path=None):
    """
    Inicializa carros de exemplo ativos e entregues no pátio caso a base esteja com poucos registros.
    """
    path = db_path or get_db_path()
    cars = list_patio_status(db_path=path)
    if len(cars) >= 4:
        return cars

    now = datetime.datetime.now()
    samples = [
        {
            "plate": "FNB-1A77",
            "client_name": "Danilo Pereira",
            "car_model": "VW Fox 1.0 - Prata",
            "car_color": "Prata",
            "status": "Em Execução",
            "mechanic_name": "Elevador 1 - Mestre Tonho",
            "notes": "Troca de óleo 5W40, filtro e correia dentada",
            "updated_at": (now - datetime.timedelta(hours=3, minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "plate": "FQE-5724",
            "client_name": "Natanael",
            "car_model": "Nissan Sentra 2.0 - Prata",
            "car_color": "Prata",
            "status": "Em Diagnóstico",
            "mechanic_name": "Box Scanner",
            "notes": "Luz de injeção acesa e oscilação na marcha lenta",
            "updated_at": (now - datetime.timedelta(hours=1, minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "plate": "DTZ-9080",
            "client_name": "Natanael novo dono",
            "car_model": "Peugeot Partner - Branco",
            "car_color": "Branco",
            "status": "Esperando Peças",
            "mechanic_name": "Elevador 2",
            "notes": "Aguardando kit amortecedores e batentes dianteiros",
            "updated_at": (now - datetime.timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "plate": "EVI-2484",
            "client_name": "Cauê Raquel (cunhados ) NovoDono",
            "car_model": "Nissan Sentra - Prata",
            "car_color": "Prata",
            "status": "Esperando Cliente Buscar",
            "mechanic_name": "Vaga Pátio 2",
            "notes": "Serviço de freios concluído. Aguardando retirada.",
            "updated_at": (now - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "plate": "ABC-1D23",
            "client_name": "Carlos Irmão do Marcos",
            "car_model": "Honda Civic - Preto",
            "car_color": "Preto",
            "status": "Entregue",
            "mechanic_name": "Entrega",
            "notes": "Veículo entregue com nota e checklist conferido.",
            "updated_at": (now - datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    for s in samples:
        existing = get_patio_status(plate=s["plate"], db_path=path)
        if not existing:
            update_patio_status(
                plate=s["plate"],
                client_name=s["client_name"],
                car_model=s["car_model"],
                car_color=s["car_color"],
                status=s["status"],
                mechanic_name=s["mechanic_name"],
                notes=s["notes"],
                updated_at=s["updated_at"],
                db_path=path
            )
    return list_patio_status(db_path=path)

