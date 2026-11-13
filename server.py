# -*- coding: utf-8 -*-
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from flask import Flask, jsonify, request, send_from_directory, abort
from werkzeug.exceptions import HTTPException, InternalServerError
import gzip
import hashlib
import ipaddress
import logging
import logging.handlers
import mimetypes
import socket
import time
import datetime
import json
import urllib.parse
import parser
import cache
import config
import updater

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DEFAULT_PORT = 54321

log = logging.getLogger("mecatronicar.server")

# No Windows o mimetypes consulta o registro, que em algumas máquinas devolve
# text/plain para .js (o navegador então recusa ES modules) ou nada para .svg/.woff2.
# Fixa os tipos usados pelo front antes de qualquer arquivo ser servido.
for _ext, _type in (
    (".js", "text/javascript"),
    (".mjs", "text/javascript"),
    (".css", "text/css"),
    (".html", "text/html"),
    (".json", "application/json"),
    (".svg", "image/svg+xml"),
    (".png", "image/png"),
    (".ico", "image/x-icon"),
    (".webp", "image/webp"),
    (".woff", "font/woff"),
    (".woff2", "font/woff2"),
    (".map", "application/json"),
):
    mimetypes.add_type(_type, _ext)


def configure_logging(log_dir=LOG_DIR, level=logging.INFO):
    """
    Log em arquivo rotativo (logs/mecatronicar.log, 1 MB x 5) + console.
    Chamado pelo launcher (app.py) e por start_server; os testes não criam arquivos.
    """
    root = logging.getLogger("mecatronicar")
    if getattr(root, "_mecatronicar_configured", False):
        return root
    os.makedirs(log_dir, exist_ok=True)
    ignore_file = os.path.join(log_dir, ".gitignore")
    if not os.path.exists(ignore_file):
        try:
            with open(ignore_file, "w", encoding="utf-8") as f:
                f.write("*\n")
        except OSError:
            pass
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "mecatronicar.log"), maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    root.setLevel(level)
    root._mecatronicar_configured = True
    # Erros do waitress (ex.: exceção fora do Flask) também vão para o arquivo.
    wl = logging.getLogger("waitress")
    wl.addHandler(fh)
    wl.setLevel(logging.WARNING)
    return root


_local_ip_cache = {"ip": None, "at": 0.0}


def _detect_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def get_local_ip():
    """
    Descobre o IP local da máquina na rede da oficina (LAN/Wi-Fi).
    Fica em cache por 60 s: é chamado a cada polling da TV (/api/patio).
    """
    now = time.monotonic()
    if _local_ip_cache["ip"] is None or now - _local_ip_cache["at"] > 60:
        _local_ip_cache["ip"] = _detect_local_ip()
        _local_ip_cache["at"] = now
    return _local_ip_cache["ip"]


app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
# Estáticos: Cache-Control no-cache + ETag/Last-Modified. O navegador revalida a cada
# carga e recebe 304 quando o arquivo não mudou (o updater troca os arquivos no lugar,
# então não dá para usar max-age longo sem nomes versionados).
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = None
app.config["COMPRESS_MIN_SIZE"] = 1024
app.config["COMPRESS_LOOPBACK"] = False  # o Edge da secretária roda na mesma máquina

cache.enable_connection_pool(cache.get_db_path(BASE_DIR))


def _db_path_from_request(value=None):
    """
    O banco é sempre o do aplicativo. Os testes podem apontar outro banco pelo
    parâmetro db_path, mas só com app.config["TESTING"] ligado: em produção um
    cliente da rede não escolhe arquivo no disco.
    """
    if value and app.config.get("TESTING"):
        return value
    return cache.get_db_path(BASE_DIR)


def _is_loopback(addr):
    try:
        return ipaddress.ip_address((addr or "").split("%")[0]).is_loopback
    except ValueError:
        return False


def _client_is_local():
    return _is_loopback(request.remote_addr)


def local_only(fn):
    """
    Rotas que mexem na máquina da secretária (abrir arquivo, escolher pasta, aplicar
    atualização, mudar configuração) só atendem a própria máquina. O servidor escuta
    em 0.0.0.0 por causa da TV, então sem isso qualquer aparelho da rede poderia,
    por exemplo, mandar abrir um executável com os.startfile.
    """
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _client_is_local():
            log.warning("Acesso negado a %s vindo de %s", request.path, request.remote_addr)
            return jsonify({"success": False, "error": "Disponível apenas no computador da oficina."}), 403
        return fn(*args, **kwargs)
    return wrapper


def _json_body():
    """Corpo JSON da requisição como dict (400 se vier algo que não é objeto JSON)."""
    data = request.get_json(silent=True)
    if data is None:
        if request.data and request.data.strip():
            abort(400, description="Corpo da requisição não é um JSON válido.")
        return {}
    if not isinstance(data, dict):
        abort(400, description="O corpo da requisição deve ser um objeto JSON.")
    return data


def _opt_str(data, key, max_len=500):
    val = data.get(key)
    if val is None:
        return None
    if not isinstance(val, (str, int, float)) or isinstance(val, bool):
        abort(400, description=f"Campo '{key}' inválido.")
    val = str(val)
    if len(val) > max_len:
        abort(400, description=f"Campo '{key}' muito longo.")
    return val


def _etag_for(payload, exclude=("server_time",)):
    body = {k: v for k, v in payload.items() if k not in exclude} if isinstance(payload, dict) else payload
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=12).hexdigest()


def json_with_etag(payload, exclude=("server_time",)):
    """
    Resposta JSON com ETag calculado sem os campos voláteis (ex.: server_time).
    Se o cliente mandar If-None-Match igual, responde 304 sem corpo — a TV faz
    polling a cada 5 s e quase sempre nada mudou.
    """
    etag = _etag_for(payload, exclude)
    if etag in request.if_none_match:
        resp = app.response_class(status=304)
    else:
        resp = jsonify(payload)
    resp.set_etag(etag)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


_COMPRESSIBLE = {
    "application/json", "text/javascript", "application/javascript", "text/css",
    "text/html", "text/plain", "text/csv", "image/svg+xml",
}
_static_gzip_cache = {}
_static_gzip_lock = threading.Lock()


def _maybe_gzip(response):
    if response.status_code != 200 or "Content-Encoding" in response.headers:
        return response
    if response.mimetype not in _COMPRESSIBLE:
        return response
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return response
    if _is_loopback(request.remote_addr) and not app.config.get("COMPRESS_LOOPBACK"):
        return response
    if request.method == "HEAD":
        return response

    etag, weak = response.get_etag()
    is_static = response.direct_passthrough and etag
    if is_static:
        with _static_gzip_lock:
            data = _static_gzip_cache.get(etag)
        if data is None:
            response.direct_passthrough = False
            raw = response.get_data()
            if len(raw) < app.config["COMPRESS_MIN_SIZE"]:
                return response
            data = gzip.compress(raw, compresslevel=6, mtime=0)
            with _static_gzip_lock:
                if len(_static_gzip_cache) > 256:
                    _static_gzip_cache.clear()
                _static_gzip_cache[etag] = data
        else:
            if hasattr(response.response, "close"):
                response.response.close()  # libera o arquivo aberto pelo send_file
            response.direct_passthrough = False
    else:
        response.direct_passthrough = False
        raw = response.get_data()
        if len(raw) < app.config["COMPRESS_MIN_SIZE"]:
            return response
        data = gzip.compress(raw, compresslevel=5, mtime=0)

    response.set_data(data)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(data))
    response.vary.add("Accept-Encoding")
    if etag:
        # O corpo comprimido é outra representação: ETag próprio (o If-None-Match
        # do navegador volta com ele e o 304 continua funcionando).
        response.set_etag(etag + "-gz", weak=weak)
    return response


@app.after_request
def finalize_response(response):
    if request.path.startswith("/api/"):
        # APIs: nada de cache, exceto as que definem a própria política (ETag).
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
    elif response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-cache"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return _maybe_gzip(response)


@app.before_request
def strip_gzip_etag_suffix():
    # Revalidação de um estático que foi servido comprimido: o If-None-Match vem
    # com o sufixo -gz; tira para o send_file do Flask comparar com o ETag do arquivo.
    inm = request.headers.get("If-None-Match")
    if inm and "-gz" in inm:
        request.environ["HTTP_IF_NONE_MATCH"] = inm.replace("-gz\"", "\"")


@app.before_request
def check_api_method():
    if request.path.startswith("/api/"):
        allowed_methods = set()
        matched_any = False
        for rule in app.url_map.iter_rules():
            if rule.endpoint != "static" and rule.rule == request.path:
                matched_any = True
                allowed_methods.update(rule.methods or [])
        if matched_any and request.method not in allowed_methods:
            from werkzeug.exceptions import MethodNotAllowed
            raise MethodNotAllowed(valid_methods=list(allowed_methods))


# Tratamento centralizado de erros: toda rota /api/* responde
# {"success": false, "error": "..."} com o status HTTP correto, e todo erro 500
# vai com traceback para logs/mecatronicar.log.
_DEFAULT_HTTP_MESSAGES = {
    400: "Requisição inválida (400)",
    403: "Acesso negado (403)",
    404: "Recurso não encontrado (404)",
    405: "Método HTTP não permitido (405)",
    413: "Requisição grande demais (413)",
    500: "Erro interno no servidor (500)",
}


def _api_error(status, message):
    return jsonify({"success": False, "error": message}), status


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    if e.code and e.code >= 500:
        log.error("HTTP %s em %s %s: %s", e.code, request.method, request.path, e.description)
    if request.path.startswith("/api/"):
        desc = e.description
        if not desc or desc == type(e).description:
            desc = _DEFAULT_HTTP_MESSAGES.get(e.code, desc or str(e))
        return _api_error(e.code or 500, desc)
    return e


@app.errorhandler(Exception)
def handle_general_exception(e):
    if isinstance(e, HTTPException):
        return handle_http_exception(e)
    log.exception("Erro não tratado em %s %s", request.method, request.path)
    if request.path.startswith("/api/"):
        return _api_error(500, str(e) or "Erro interno do servidor")
    return InternalServerError()


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/tv")
def tv_route():
    return send_from_directory(STATIC_DIR, "tv.html")


# Os estáticos são servidos na raiz (static_url_path=""), mas o front também usa
# caminhos /static/... (ex.: /static/brands/*.svg), que davam 404. Este alias serve
# os mesmos arquivos, com o mesmo ETag/MIME/compressão.
@app.route("/static/<path:filename>")
def static_alias(filename):
    return app.send_static_file(filename)


@app.route("/api/health", methods=["GET"])
def health_endpoint():
    """Usado pelo launcher para abrir a janela assim que o servidor responde."""
    return jsonify({"success": True, "version": updater.CURRENT_VERSION})


@app.route("/api/index_status", methods=["GET"])
def index_status_endpoint():
    """Progresso da indexação em segundo plano (leitura do conteúdo das planilhas)."""
    status = cache.get_index_status()
    status["success"] = True
    return jsonify(status)


@app.route("/api/config", methods=["GET"])
def get_config_endpoint():
    cfg = config.load_config(BASE_DIR)
    db_path = cache.get_db_path(BASE_DIR)
    stats = cache.get_stats(db_path)
    local_ip = get_local_ip()
    return jsonify({
        "config": cfg,
        "stats": stats,
        "version": updater.CURRENT_VERSION,
        "local_ip": local_ip,
        "tv_url": f"http://{local_ip}:54321/tv"
    })

def _index_folder_now(folder):
    """
    Varredura incremental síncrona (rápida: só compara mtime/tamanho e, para muitas
    planilhas novas, indexa pelo nome do arquivo) + leitura do conteúdo pendente em
    segundo plano. Retorna (scan_result, index_status).
    """
    db_path = cache.get_db_path(BASE_DIR)
    scan_res = cache.scan_and_index_folder(folder, db_path)
    status = None
    if scan_res.get("pending_parse"):
        status = cache.start_background_index(folder, db_path, scan=False)
    return scan_res, status


_VALID_SORT_ORDERS = ("asc", "desc")


@app.route("/api/config", methods=["POST"])
@local_only
def update_config_endpoint():
    data = _json_body()
    cfg = config.load_config(BASE_DIR)
    old_folder = cfg.get("spreadsheet_folder", "")

    new_folder = _opt_str(data, "spreadsheet_folder", max_len=1024)
    if new_folder is not None:
        new_folder = new_folder.strip()
        if new_folder and not os.path.isdir(new_folder):
            return jsonify({"success": False, "error": "A pasta informada não existe."}), 400
        cfg["spreadsheet_folder"] = os.path.normpath(new_folder) if new_folder else ""
    theme = _opt_str(data, "theme", max_len=20)
    if theme is not None:
        cfg["theme"] = theme
    sort_order = _opt_str(data, "sort_order", max_len=10)
    if sort_order is not None:
        if sort_order not in _VALID_SORT_ORDERS:
            return jsonify({"success": False, "error": "Ordenação inválida (use 'asc' ou 'desc')."}), 400
        cfg["sort_order"] = sort_order
    if "ui_zoom" in data:
        try:
            cfg["ui_zoom"] = max(50, min(150, int(data["ui_zoom"])))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Zoom inválido."}), 400

    if not config.save_config(cfg, BASE_DIR):
        return jsonify({"success": False, "error": "Não foi possível salvar a configuração."}), 500

    # Reindexa (incremental) se a pasta existir. Antes isso relia tudo de forma
    # síncrona a cada mudança de zoom/tema; agora a varredura só olha mtime/tamanho
    # e o conteúdo novo é lido em segundo plano.
    scan_res = None
    index_status = None
    folder = cfg.get("spreadsheet_folder")
    if folder and os.path.isdir(folder):
        if folder != old_folder or new_folder is not None:
            scan_res, index_status = _index_folder_now(folder)
        else:
            index_status = cache.start_background_index(folder, cache.get_db_path(BASE_DIR), scan=True)

    db_path = cache.get_db_path(BASE_DIR)
    stats = cache.get_stats(db_path)
    return jsonify({
        "success": True,
        "config": cfg,
        "stats": stats,
        "scan_result": scan_res,
        "index_status": index_status,
        "version": updater.CURRENT_VERSION
    })

@app.route("/api/select_folder", methods=["POST"])
@local_only
def select_folder_endpoint():
    cfg = config.load_config(BASE_DIR)
    current_folder = cfg.get("spreadsheet_folder", "")
    
    selected_folder = ""
    def _open_dialog():
        nonlocal selected_folder
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            initial = current_folder if current_folder and os.path.isdir(current_folder) else os.path.expanduser("~")
            selected_folder = filedialog.askdirectory(
                initialdir=initial,
                title="Selecione a pasta onde estão as planilhas da oficina"
            )
            root.destroy()
        except Exception:
            log.exception("Erro ao abrir a janela de seleção de pasta")

    t = threading.Thread(target=_open_dialog, name="mecatronicar-folder-dialog")
    t.start()
    t.join(timeout=60)
    
    if selected_folder:
        selected_folder = os.path.normpath(selected_folder)
        cfg["spreadsheet_folder"] = selected_folder
        config.save_config(cfg, BASE_DIR)
        
        scan_res, index_status = _index_folder_now(selected_folder)
        stats = cache.get_stats(cache.get_db_path(BASE_DIR))
        
        return jsonify({
            "success": True,
            "folder": selected_folder,
            "scan_result": scan_res,
            "index_status": index_status,
            "stats": stats
        })
    else:
        return jsonify({"success": False, "folder": current_folder})

@app.route("/api/reindex", methods=["POST"])
def reindex_endpoint():
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if not folder or not os.path.isdir(folder):
        return jsonify({"success": False, "error": "Pasta não configurada ou inexistente"}), 400
        
    scan_res, index_status = _index_folder_now(folder)
    stats = cache.get_stats(cache.get_db_path(BASE_DIR))
    return jsonify({
        "success": True,
        "scan_result": scan_res,
        "index_status": index_status,
        "stats": stats
    })

@app.route("/api/cars", methods=["GET"])
def get_cars_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    cars = cache.get_all_cars(db_path)
    return jsonify({"cars": cars})

@app.route("/api/search", methods=["GET"])
def search_endpoint():
    q = request.args.get("q", "").strip()
    db_path = cache.get_db_path(BASE_DIR)
    if not q:
        cars = cache.get_all_cars(db_path)
        return jsonify({"results": [], "cars": cars})
        
    results = cache.search_files(q, db_path)
    return jsonify({"results": results})

@app.route("/api/car_history/<plate>", methods=["GET"])
def car_history_endpoint(plate):
    db_path = cache.get_db_path(BASE_DIR)
    history = cache.get_car_history(plate, db_path)
    return jsonify({
        "plate": plate,
        "visits": history
    })

@app.route("/api/car_lookup/<plate>", methods=["GET"])
def car_lookup_endpoint(plate):
    db_path = cache.get_db_path(BASE_DIR)
    info = cache.get_car_lookup(plate, db_path)
    return jsonify(info)

@app.route("/api/quick_suggestions", methods=["GET"])
def quick_suggestions_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    suggestions = cache.get_quick_suggestions(db_path)
    return jsonify(suggestions)

_SPREADSHEET_EXTS = (".xlsx", ".xls")


def _spreadsheet_roots():
    roots = []
    folder = config.load_config(BASE_DIR).get("spreadsheet_folder", "")
    if folder and os.path.isdir(folder):
        roots.append(folder)
    sample_dir = os.path.join(BASE_DIR, "planilhas_exemplo")
    if os.path.isdir(sample_dir):
        roots.append(sample_dir)
    return roots


def _is_within(path, root):
    try:
        root_real = os.path.normcase(os.path.realpath(root))
        path_real = os.path.normcase(os.path.realpath(path))
        return os.path.commonpath([root_real, path_real]) == root_real
    except (ValueError, OSError):
        return False  # ex.: drives diferentes no Windows


def resolve_spreadsheet_path(fpath, db_path=None, must_exist=True):
    """
    Valida um caminho de planilha vindo do cliente. Só aceita .xlsx/.xls que estejam
    dentro da pasta de planilhas configurada (ou de planilhas_exemplo/) ou que já
    estejam no índice. Retorna o caminho (como recebido) ou None.
    """
    if not fpath or not isinstance(fpath, str) or chr(0) in fpath:
        return None
    if os.path.splitext(fpath)[1].lower() not in _SPREADSHEET_EXTS:
        return None
    if must_exist and not os.path.isfile(fpath):
        return None
    if any(_is_within(fpath, root) for root in _spreadsheet_roots()):
        return fpath
    try:
        if cache.is_indexed_file(fpath, db_path or cache.get_db_path(BASE_DIR)):
            return fpath
    except Exception:
        log.exception("Falha ao consultar o índice para %s", fpath)
    return None


@app.route("/api/save_order", methods=["POST"])
def save_order_endpoint():
    import excel_writer
    data = _json_body()
    order_data = data.get("order_data") or data
    if not isinstance(order_data, dict):
        return jsonify({"success": False, "error": "Dados da ordem de serviço inválidos."}), 400
    existing_file_path = data.get("existing_file_path") or data.get("existing_filepath") or None

    if not order_data:
        return jsonify({"success": False, "error": "Dados da ordem de serviço não fornecidos."}), 400

    # Validação antecipada dos dados essenciais
    car_info = order_data.get("car") if isinstance(order_data.get("car"), dict) else {}
    plate = car_info.get("plate") or order_data.get("car_plate") or order_data.get("plate")
    if not plate or not str(plate).strip():
        return jsonify({"success": False, "error": "A placa do veículo é obrigatória."}), 400

    client_info = order_data.get("client") if isinstance(order_data.get("client"), dict) else {}
    client_name = client_info.get("name") or client_info.get("client_name") or order_data.get("client_name")
    if not client_name or not str(client_name).strip():
        return jsonify({"success": False, "error": "O nome do cliente é obrigatório."}), 400

    car_model = car_info.get("model") or order_data.get("car_model")
    if not car_model or not str(car_model).strip():
        return jsonify({"success": False, "error": "O modelo do veículo é obrigatório."}), 400

    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if not folder or not os.path.isdir(folder):
        sample_dir = os.path.join(BASE_DIR, "planilhas_exemplo")
        folder = sample_dir if os.path.isdir(sample_dir) else BASE_DIR

    db_path = _db_path_from_request(data.get("db_path") or app.config.get("TEST_DB_PATH"))
    if existing_file_path and not resolve_spreadsheet_path(existing_file_path, db_path):
        # Editar uma OS só pode regravar uma planilha da própria oficina.
        return jsonify({"success": False, "error": "Planilha da OS a editar não encontrada na pasta de planilhas."}), 400

    try:
        res = excel_writer.save_order_to_excel(order_data, folder_path=folder, existing_filepath=existing_file_path, db_path=db_path)
        file_path = res.get("file_path")
        file_name = res.get("file_name") or res.get("filename")

        parsed = cache.index_single_file(file_path, db_path, old_fpath=existing_file_path)
        stats = cache.get_stats(db_path)

        return jsonify({
            "success": True,
            "message": "Ordem de serviço salva com sucesso!",
            "file_path": file_path,
            "file_name": file_name,
            "plate": (parsed.get("plate_display") or parsed.get("plate")) if parsed else (res.get("plate") or plate),
            "plate_clean": parsed.get("plate_clean", "") if parsed else cache.clean_plate(plate),
            "visit_num": parsed.get("visit_num", "") if parsed else (res.get("visit_num") or "1"),
            "details": parsed,
            "stats": stats
        }), 200
    except ValueError as ve:
        log.info("OS recusada: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except PermissionError as e:
        log.warning("Planilha bloqueada ao salvar OS: %s", e)
        return jsonify({"success": False, "error": "A planilha está aberta em outro programa (Excel?). Feche-a e tente de novo."}), 409
    except Exception as e:
        log.exception("Erro ao salvar OS")
        return jsonify({"success": False, "error": f"Erro interno ao salvar planilha: {str(e)}"}), 500

@app.route("/api/open_file", methods=["POST"])
@local_only
def open_file_endpoint():
    data = _json_body()
    fpath = data.get("file_path", "")
    if not fpath or not isinstance(fpath, str) or not os.path.exists(fpath):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    if not resolve_spreadsheet_path(fpath):
        log.warning("open_file recusado para caminho fora da pasta de planilhas: %r", fpath)
        return jsonify({"success": False, "error": "Só é possível abrir planilhas da pasta da oficina."}), 403

    try:
        os.startfile(fpath)
        return jsonify({"success": True, "message": "Arquivo aberto no Excel com sucesso!"})
    except Exception as e:
        log.exception("Falha ao abrir %s", fpath)
        return jsonify({"success": False, "error": str(e)}), 500

# Documentos PDF Profissionais (CP-04 e CP-05)
@app.route("/api/orcamento_pdf", methods=["GET"])
def orcamento_pdf_endpoint():
    import pdf_generator
    fpath = resolve_spreadsheet_path(request.args.get("file_path", "")) or ""
    auto_print = request.args.get("print", "0") in ("1", "true", "True")
    
    if not fpath or not os.path.exists(fpath):
        plate = request.args.get("plate", "")
        if plate:
            db_path = cache.get_db_path(BASE_DIR)
            history = cache.get_car_history(plate, db_path)
            if history:
                fpath = history[0].get("file_path", "")
                
    if not fpath or not os.path.exists(fpath):
        return "Arquivo de planilha não encontrado.", 404
        
    try:
        html_content = pdf_generator.generate_orcamento_from_file(fpath, auto_print=auto_print)
        return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        log.exception("Erro gerando orçamento de %s", fpath)
        return f"Erro gerando orçamento: {str(e)}", 500

@app.route("/api/checklist_pdf", methods=["GET", "POST"])
def checklist_pdf_endpoint():
    import pdf_generator
    
    data = {}
    if request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True) or {}
        elif "config_json" in request.form:
            try:
                data = json.loads(request.form["config_json"])
            except ValueError:
                data = request.form.to_dict()
        else:
            data = request.form.to_dict()
    if not isinstance(data, dict):
        abort(400, description="Dados do checklist inválidos.")

    fpath = resolve_spreadsheet_path(data.get("file_path") or request.args.get("file_path", "")) or ""
    
    # Auto print
    auto_print_param = data.get("print", data.get("auto_print", request.args.get("print", "0")))
    auto_print = auto_print_param in ("1", "true", "True", True)
    
    # Toggle do Scanner OBD2
    scanner_param = data.get("include_scanner", request.args.get("include_scanner", "1"))
    if isinstance(scanner_param, str):
        include_scanner = scanner_param.lower() not in ("0", "false", "no", "nao", "não")
    else:
        include_scanner = bool(scanner_param)

    # Itens customizados / filtrados
    custom_items = data.get("items")
    custom_pecas = data.get("pecas")
    custom_servicos = data.get("servicos")
    manual_items = data.get("manual_items")

    if not fpath or not os.path.exists(fpath):
        plate = data.get("plate") or request.args.get("plate", "")
        if plate:
            db_path = cache.get_db_path(BASE_DIR)
            history = cache.get_car_history(plate, db_path)
            if history:
                fpath = history[0].get("file_path", "")
                
    if not fpath or not os.path.exists(fpath):
        return "Arquivo de planilha não encontrado.", 404
        
    try:
        parsed = parser.parse_file(fpath)
        if manual_items:
            parsed["manual_items"] = manual_items
        html_content = pdf_generator.render_checklist_html(
            parsed,
            auto_print=auto_print,
            include_scanner=include_scanner,
            custom_items=custom_items,
            pecas=custom_pecas,
            servicos=custom_servicos
        )
        return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        log.exception("Erro gerando checklist de %s", fpath)
        return f"Erro gerando checklist: {str(e)}", 500

@app.route("/api/history_pdf", methods=["GET", "POST"])
def history_pdf_endpoint():
    import pdf_generator
    data = {}
    if request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True) or {}
        elif "config_json" in request.form:
            try:
                data = json.loads(request.form["config_json"])
            except ValueError:
                data = request.form.to_dict()
        else:
            data = request.form.to_dict()
    if not isinstance(data, dict):
        abort(400, description="Dados do histórico inválidos.")

    plate = data.get("plate") or request.args.get("plate", "")
    selected_indices = data.get("selected_indices")
    selected_visit_nums = data.get("selected_visit_nums")
    
    without_prices_param = data.get("without_prices", request.args.get("without_prices", "0"))
    without_prices = without_prices_param in ("1", "true", "True", True)
    
    auto_print_param = data.get("auto_print", data.get("print", request.args.get("print", "0")))
    auto_print = auto_print_param in ("1", "true", "True", True)

    db_path = cache.get_db_path(BASE_DIR)
    history = cache.get_car_history(plate, db_path)
    if not history:
        return "Nenhum histórico encontrado para esta placa.", 404

    # Ordenação decrescente padrão (mais recente primeiro)
    sorted_history = sorted(history, key=lambda x: (x.get("entry_date_sort") or "", x.get("odometer_int") or 0), reverse=True)

    # Filtra visitas se selecionadas
    visits_to_render = sorted_history
    if selected_visit_nums is not None:
        v_nums_str = [str(x).strip() for x in (selected_visit_nums if isinstance(selected_visit_nums, list) else [selected_visit_nums])]
        visits_to_render = [v for v in sorted_history if str(v.get("visit_num", "")).strip() in v_nums_str]
    elif selected_indices is not None:
        idx_set = set(int(i) for i in (selected_indices if isinstance(selected_indices, list) else []) if str(i).isdigit())
        visits_to_render = [v for idx, v in enumerate(sorted_history) if idx in idx_set]

    if not visits_to_render:
        visits_to_render = sorted_history

    html_content = pdf_generator.render_consolidated_history_html(
        sorted_history[0],
        visits_to_render,
        without_prices=without_prices,
        auto_print=auto_print
    )
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}

# Updater API endpoints
@app.route("/api/check_update", methods=["GET"])
def check_update_endpoint():
    update_data = updater.check_for_updates()
    return jsonify(update_data)

_UPDATE_HOST_SUFFIXES = ("github.com", "githubusercontent.com")


def _is_trusted_update_url(url):
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in _UPDATE_HOST_SUFFIXES)


@app.route("/api/apply_update", methods=["POST"])
@local_only
def apply_update_endpoint():
    data = _json_body()
    download_url = data.get("download_url", "")
    if not download_url or not isinstance(download_url, str):
        return jsonify({"success": False, "error": "URL de download ausente"}), 400
    if not _is_trusted_update_url(download_url):
        log.warning("apply_update recusado para URL não confiável: %s", download_url)
        return jsonify({"success": False, "error": "URL de atualização não confiável (apenas GitHub via HTTPS)."}), 400
        
    try:
        # Run in thread so response can be sent to browser
        threading.Thread(
            target=updater.apply_update_process,
            args=(download_url, BASE_DIR),
            daemon=True
        ).start()
        return jsonify({"success": True, "message": "Atualização iniciada com sucesso. O sistema irá reiniciar automaticamente."})
    except Exception as e:
        log.exception("Falha ao iniciar a atualização")
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# ROTAS DO PÁTIO / TV DA OFICINA (CP-06)
# ==========================================
def _known_patio_status(status):
    """Aceita os nomes de status (com ou sem acento) que o pátio entende."""
    if not isinstance(status, str) or not status.strip() or len(status) > 60:
        return False
    norm = cache.normalize_patio_status(status)
    known = set(cache.PATIO_STATUSES) | set(cache.STATUS_DISPLAY_MAP) | set(cache.STATUS_DISPLAY_MAP.values())
    return norm in known or status.strip() in known


@app.route("/api/patio", methods=["GET"])
def get_patio_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    all_patio = cache.list_patio_status(db_path=db_path)
    if len(all_patio) < 3:
        cache.seed_sample_patio_if_empty(db_path=db_path)
        all_patio = None
    summary = cache.get_patio_summary(db_path, cars=all_patio)
    local_ip = get_local_ip()

    active_cars = []
    delivered_cars = []
    now = datetime.datetime.now()
    two_days_ago = now - datetime.timedelta(days=2)

    for c in summary.get("cars", []):
        st = (c.get("status") or "").strip()
        st_disp = (c.get("status_display") or "").strip()
        if st == "Entregue" or st_disp == "Entregue":
            up_time_str = c.get("updated_at") or c.get("updated_time") or ""
            is_recent = True
            if up_time_str:
                try:
                    dt = datetime.datetime.strptime(up_time_str[:19], "%Y-%m-%d %H:%M:%S")
                    if dt < two_days_ago:
                        is_recent = False
                except ValueError:
                    pass  # data em formato livre: mantém como recente
            if is_recent:
                delivered_cars.append(c)
        else:
            active_cars.append(c)

    # ETag (sem server_time): a TV faz polling a cada 5 s e recebe 304 quando nada mudou.
    return json_with_etag({
        "success": True,
        "total": summary["total"],
        "by_status": summary["by_status"],
        "cars": summary["cars"],
        "active_cars": active_cars,
        "delivered_cars": delivered_cars,
        "statuses": cache.PATIO_STATUSES,
        "local_ip": local_ip,
        "tv_url": f"http://{local_ip}:54321/tv",
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/patio", methods=["POST"])
def save_patio_endpoint():
    data = _json_body()
    if not (data.get("id") or data.get("plate") or data.get("file_path")):
        return jsonify({"success": False, "error": "Informe a placa (ou o id) do veículo."}), 400
    for key in ("plate", "client_name", "car_model", "car_color", "mechanic_name", "box_mecanico",
                "third_party_name", "authorized_name", "third_party_doc", "authorized_doc",
                "third_party_phone", "authorized_phone"):
        _opt_str(data, key, max_len=200)
    _opt_str(data, "notes", max_len=4000)
    if data.get("file_path") and not resolve_spreadsheet_path(data.get("file_path"), must_exist=False):
        return jsonify({"success": False, "error": "Planilha informada fora da pasta de planilhas."}), 400
    if data.get("status") is not None and not _known_patio_status(data.get("status")):
        return jsonify({"success": False, "error": f"Status de pátio desconhecido: {data.get('status')}"}), 400
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_patio_car(data, db_path)
        return jsonify({"success": True, "car": saved})
    except (ValueError, TypeError) as e:
        log.info("Pátio: dados recusados: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/patio/status", methods=["POST"])
def update_patio_status_endpoint():
    data = _json_body()
    car_id = data.get("car_id") or data.get("id")
    status = data.get("status")
    if not car_id or not status:
        return jsonify({"success": False, "error": "ID e status são obrigatórios"}), 400
    try:
        car_id = int(car_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "ID do veículo inválido"}), 400
    if not _known_patio_status(status):
        return jsonify({"success": False, "error": f"Status de pátio desconhecido: {status}"}), 400

    auth_name = _opt_str(data, "authorized_name", max_len=200)
    auth_doc = _opt_str(data, "authorized_doc", max_len=60)
    auth_phone = _opt_str(data, "authorized_phone", max_len=60)
    
    db_path = cache.get_db_path(BASE_DIR)
    updated = cache.update_patio_car_status(
        car_id, status,
        authorized_name=auth_name,
        authorized_doc=auth_doc,
        authorized_phone=auth_phone,
        db_path=db_path
    )
    if not updated:
        return jsonify({"success": False, "error": "Veículo não encontrado no pátio"}), 404
    return jsonify({"success": True, "car": updated})

@app.route("/api/patio/<int:car_id>", methods=["DELETE"])
def delete_patio_car_endpoint(car_id):
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_patio_car(car_id, db_path)
    if success:
        return jsonify({"success": True, "message": "Veículo removido do pátio com sucesso."})
    return jsonify({"success": False, "error": "Veículo não encontrado no pátio"}), 404

@app.route("/api/patio/remove", methods=["POST"])
def remove_patio_car_post_endpoint():
    data = _json_body()
    car_id = data.get("car_id") or data.get("id")
    if not car_id:
        return jsonify({"success": False, "error": "ID do veículo ausente"}), 400
    try:
        car_id = int(car_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "ID do veículo inválido"}), 400
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_patio_car(car_id, db_path)
    return jsonify({"success": success})

# ==============================================================================
# ROTAS DE AGENDAMENTOS E CALENDÁRIO (Issue #15)
# ==============================================================================

@app.route("/api/agendamentos", methods=["GET"])
def list_agendamentos_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    date = request.args.get("date")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    status = request.args.get("status")
    query = request.args.get("query")
    
    try:
        limit = int(request.args.get("limit", 200))
    except Exception:
        limit = 200

    items = cache.list_agendamentos(
        date_from=date_from,
        date_to=date_to,
        date=date,
        status=status,
        query=query,
        limit=limit,
        db_path=db_path
    )
    
    today_iso = datetime.date.today().isoformat()
    today_items = [it for it in items if it.get("scheduled_date") == today_iso]
    today_count = len(today_items)
    
    return json_with_etag({
        "success": True,
        "agendamentos": items,
        "count": len(items),
        "today_count": today_count,
        "today_iso": today_iso,
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/agendamentos", methods=["POST"])
def create_agendamento_endpoint():
    data = _json_body()
    db_path = cache.get_db_path(BASE_DIR)
    try:
        agendamento = cache.create_agendamento(data, db_path=db_path)
        
        # Engatilha sincronização com Google Calendar
        import calendar_sync
        gcal_result = calendar_sync.sync_agendamento_to_gcal(agendamento)
        if gcal_result.get("synced") and gcal_result.get("google_calendar_id"):
            agendamento = cache.update_agendamento(
                agendamento["id"],
                {
                    "google_calendar_id": gcal_result["google_calendar_id"],
                    "google_calendar_sync_status": "synced"
                },
                db_path=db_path
            )

        return jsonify({
            "success": True,
            "agendamento": agendamento,
            "gcal": gcal_result,
            "message": "Agendamento cadastrado com sucesso!"
        }), 201
    except ValueError as ve:
        log.info("Agendamento recusado: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        log.exception("Erro ao criar agendamento")
        return jsonify({"success": False, "error": f"Erro interno ao criar agendamento: {str(e)}"}), 500

@app.route("/api/agendamentos/<int:agendamento_id>", methods=["GET"])
def get_agendamento_endpoint(agendamento_id):
    db_path = cache.get_db_path(BASE_DIR)
    agendamento = cache.get_agendamento(agendamento_id, db_path=db_path)
    if not agendamento:
        return jsonify({"success": False, "error": "Agendamento não encontrado."}), 404
    return jsonify({"success": True, "agendamento": agendamento})

@app.route("/api/agendamentos/<int:agendamento_id>", methods=["PUT", "POST"])
def update_agendamento_endpoint(agendamento_id):
    data = _json_body()
    db_path = cache.get_db_path(BASE_DIR)
    try:
        updated = cache.update_agendamento(agendamento_id, data, db_path=db_path)
        if not updated:
            return jsonify({"success": False, "error": "Agendamento não encontrado."}), 404
            
        import calendar_sync
        gcal_result = calendar_sync.sync_agendamento_to_gcal(updated)
        
        return jsonify({
            "success": True,
            "agendamento": updated,
            "gcal": gcal_result,
            "message": "Agendamento atualizado com sucesso!"
        })
    except (ValueError, TypeError) as e:
        log.info("Atualização de agendamento recusada: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/agendamentos/<int:agendamento_id>", methods=["DELETE"])
def delete_agendamento_endpoint(agendamento_id):
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_agendamento(agendamento_id, db_path=db_path)
    if not success:
        return jsonify({"success": False, "error": "Agendamento não encontrado."}), 404
    return jsonify({"success": True, "message": "Agendamento removido com sucesso."})

@app.route("/api/agendamentos/<int:agendamento_id>/status", methods=["POST"])
def update_agendamento_status_endpoint(agendamento_id):
    data = _json_body()
    status = data.get("status")
    if not status:
        return jsonify({"success": False, "error": "Status é obrigatório."}), 400
    db_path = cache.get_db_path(BASE_DIR)
    updated = cache.update_agendamento_status(agendamento_id, status, db_path=db_path)
    if not updated:
        return jsonify({"success": False, "error": "Agendamento não encontrado."}), 404
    return jsonify({"success": True, "agendamento": updated})

@app.route("/api/agendamentos/gcal/status", methods=["GET"])
def gcal_status_endpoint():
    import calendar_sync
    return jsonify(calendar_sync.get_gcal_status())

@app.route("/api/agendamentos/gcal/sync", methods=["POST"])
def gcal_sync_endpoint():
    data = _json_body()
    import calendar_sync
    result = calendar_sync.sync_agendamento_to_gcal(data)
    return jsonify(result)

# ==========================================
# ROTAS DO CALENDÁRIO / AGENDAMENTOS (Issue #11)
# ==========================================
@app.route("/api/agenda", methods=["GET"])
def get_agenda_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    cache.seed_sample_agenda_if_empty(db_path=db_path)
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    events = cache.list_agenda_events(start_date=start_date, status=status, db_path=db_path)
    return jsonify({
        "success": True,
        "events": events,
        "today": datetime.date.today().strftime("%Y-%m-%d"),
        "total": len(events)
    })

@app.route("/api/agenda", methods=["POST"])
def save_agenda_endpoint():
    data = _json_body()
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_agenda_event(data, db_path=db_path)
        return jsonify({"success": True, "event": saved})
    except (ValueError, TypeError) as e:
        log.info("Evento de agenda recusado: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/agenda/status", methods=["POST"])
def update_agenda_status_endpoint():
    data = _json_body()
    event_id = data.get("id") or data.get("event_id")
    status = data.get("status")
    if not event_id or not status:
        return jsonify({"success": False, "error": "ID e status são obrigatórios"}), 400
    db_path = cache.get_db_path(BASE_DIR)
    updated = cache.update_agenda_event_status(event_id, status, db_path=db_path)
    if not updated:
        return jsonify({"success": False, "error": "Agendamento não encontrado"}), 404
    return jsonify({"success": True, "event": updated})

@app.route("/api/agenda/<int:event_id>", methods=["DELETE"])
def delete_agenda_endpoint(event_id):
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_agenda_event(event_id, db_path=db_path)
    return jsonify({"success": success})

@app.route("/api/agenda/<int:event_id>/to_patio", methods=["POST"])
def agenda_to_patio_endpoint(event_id):
    db_path = cache.get_db_path(BASE_DIR)
    ev = cache.get_agenda_event(event_id, db_path=db_path)
    if not ev:
        return jsonify({"success": False, "error": "Agendamento não encontrado"}), 404
    data = _json_body()
    status = data.get("status") or "Em Diagnóstico"
    patio_car = cache.update_patio_status(
        plate=ev.get("plate") or ev.get("plate_clean"),
        client_name=ev.get("client_name"),
        car_model=ev.get("car_model"),
        status=status,
        notes=f"Agendamento: {ev.get('title', '')} - {ev.get('notes', '')}".strip(" -"),
        db_path=db_path
    )
    cache.update_agenda_event_status(event_id, "Em Atendimento", db_path=db_path)
    return jsonify({
        "success": True,
        "car": patio_car,
        "event": cache.get_agenda_event(event_id, db_path=db_path)
    })

# ==========================================
# CRIAÇÃO E EDIÇÃO DE OS / MOTOR EXCEL (CP-02 / CP-03)
# ==========================================

@app.route("/api/os/autocomplete", methods=["GET"])
def os_autocomplete_endpoint():
    import excel_writer
    q = request.args.get("q", "").strip()
    db_path = cache.get_db_path(BASE_DIR)
    suggestions = excel_writer.get_client_vehicle_autocomplete(q, db_path)
    return jsonify({"success": True, "suggestions": suggestions})

@app.route("/api/os/next_visit/<plate>", methods=["GET"])
def os_next_visit_endpoint(plate):
    import excel_writer
    db_path = cache.get_db_path(BASE_DIR)
    next_v = excel_writer.get_next_visit_num(plate, db_path)
    history = cache.get_car_history(plate, db_path)
    last_visit = history[0] if history else None
    return jsonify({
        "success": True,
        "next_visit_num": next_v,
        "last_visit": last_visit
    })

@app.route("/api/os/save", methods=["POST"])
def os_save_endpoint():
    import excel_writer
    data = _json_body()
    existing_fpath = data.get("existing_file_path") or data.get("existing_filepath") or None
    db_path = _db_path_from_request(data.get("db_path"))
    cfg = config.load_config(BASE_DIR)
    target_folder = cfg.get("spreadsheet_folder") or os.path.join(BASE_DIR, "planilhas_exemplo")
    # Pasta de destino vinda do cliente só nos testes: em produção a OS é sempre
    # gravada na pasta de planilhas configurada.
    if app.config.get("TESTING"):
        target_folder = data.get("folder") or data.get("target_folder") or target_folder
    if existing_fpath and not resolve_spreadsheet_path(existing_fpath, db_path):
        return jsonify({"success": False, "error": "Planilha da OS a editar não encontrada na pasta de planilhas."}), 400
    try:
        res = excel_writer.save_new_or_updated_os(data, target_folder=target_folder, db_path=db_path, existing_filepath=existing_fpath)
        return jsonify(res)
    except PermissionError as e:
        log.warning("Planilha bloqueada ao salvar OS: %s", e)
        return jsonify({"success": False, "error": "A planilha está aberta em outro programa (Excel?). Feche-a e tente de novo."}), 409
    except (ValueError, TypeError, KeyError) as e:
        log.info("OS recusada: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        log.exception("Erro ao salvar OS (/api/os/save)")
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# COPILOTO FISCAL (CP-07)
# ==========================================
import nf_copilot

@app.route("/api/nf/data", methods=["GET"])
@app.route("/api/nf/data/<plate>", methods=["GET"])
def nf_data_endpoint(plate=None):
    db_path = cache.get_db_path(BASE_DIR)
    file_path = resolve_spreadsheet_path(request.args.get("file_path", "").strip()) or ""
    target_plate = plate or request.args.get("plate", "").strip()
    visit_num = request.args.get("visit_num", "").strip()

    det = {}
    fpath = file_path
    last_visit = {}

    if fpath and os.path.exists(fpath):
        try:
            import parser
            det = parser.parse_file(fpath)
            last_visit = det
            target_plate = target_plate or det.get("plate", "")
            visit_num = visit_num or det.get("visit_num", "")
        except Exception:
            log.exception("Erro lendo planilha para copiloto fiscal: %s", fpath)

    if not det and target_plate:
        history = cache.get_car_history(target_plate, db_path)
        if history:
            if visit_num:
                matched = [v for v in history if str(v.get("visit_num", "")).strip() == str(visit_num)]
                last_visit = matched[0] if matched else history[0]
            else:
                last_visit = history[0]
            det = last_visit.get("details") or {}
            fpath = fpath or last_visit.get("file_path", "")

    if not det and not last_visit:
        nf_rec = cache.get_nf_control(file_path=fpath, plate_clean=target_plate, visit_num=visit_num, db_path=db_path)
        if nf_rec:
            val_s = float(nf_rec.get("valor_servico", 0.0) or 0.0)
            val_p = float(nf_rec.get("valor_pecas", 0.0) or 0.0)
            last_visit = {
                "plate": nf_rec.get("plate"),
                "plate_display": nf_rec.get("plate_display") or nf_rec.get("plate"),
                "car_model": nf_rec.get("car_model"),
                "client_name": nf_rec.get("client_name"),
                "entry_date": nf_rec.get("entry_date"),
                "visit_num": nf_rec.get("visit_num"),
                "total_servicos": f"R$ {val_s:.2f}".replace(".", ","),
                "total_pecas": f"R$ {val_p:.2f}".replace(".", ","),
                "total": f"R$ {(val_s + val_p):.2f}".replace(".", ","),
            }
            det = last_visit
            fpath = fpath or nf_rec.get("file_path", "")
        else:
            return jsonify({"success": False, "error": "Visita ou veículo não encontrado"}), 404

    nf_rec = cache.get_nf_control(file_path=fpath, plate_clean=target_plate, visit_num=visit_num, db_path=db_path)
    copilot_payload = nf_copilot.build_copilot_payload(fpath, det or last_visit, nf_rec)

    val_servicos_num = cache.parse_currency_float(copilot_payload.get("total_servicos", "0"))
    val_pecas_num = cache.parse_currency_float(copilot_payload.get("total_pecas", "0"))

    # Estrutura completa de nfse e nfe
    nfse_obj = {
        "status": (nf_rec.get("status_servico") if nf_rec else None) or copilot_payload["nf_status"]["nfse_status"],
        "numero_nfse": (nf_rec.get("nf_servico_num") if nf_rec else "") or copilot_payload["nf_status"]["nfse_number"],
        "data_emissao": (nf_rec.get("data_emissao_servico") if nf_rec else "") or copilot_payload["nf_status"]["nfse_date"],
        "valor_servicos": val_servicos_num,
        "discriminacao_completa": copilot_payload["copilot_texts"]["nfse_discriminacao"],
        "itens_servico": [
            {
                "desc": s.get("description", ""),
                "qty": s.get("quantity", "1"),
                "unit_price": cache.parse_currency_float(s.get("unit_price", 0)),
                "total": cache.parse_currency_float(s.get("total_price", 0))
            }
            for s in copilot_payload.get("servicos_items", [])
        ]
    }

    nfe_obj = {
        "status": (nf_rec.get("status_pecas") if nf_rec else None) or copilot_payload["nf_status"]["nfe_status"],
        "numero_nfe": (nf_rec.get("nf_pecas_num") if nf_rec else "") or copilot_payload["nf_status"]["nfe_number"],
        "data_emissao": (nf_rec.get("data_emissao_pecas") if nf_rec else "") or copilot_payload["nf_status"]["nfe_date"],
        "valor_pecas": val_pecas_num,
        "resumo_texto": copilot_payload["copilot_texts"]["nfe_pecas_resumo"],
        "tabela_tsv": copilot_payload["copilot_texts"]["nfe_pecas_tsv"],
        "itens_pecas": [
            {
                "desc": p.get("description", ""),
                "qty": p.get("quantity", "1"),
                "unit_price": cache.parse_currency_float(p.get("unit_price", 0)),
                "total": cache.parse_currency_float(p.get("total_price", 0)),
                "cfop": str(p.get("suggested_cfop", "5405")).replace(".", ""),
                "cfop_display": p.get("suggested_cfop", "5.405"),
                "ncm_sugerido": p.get("suggested_ncm", "8708.29.99"),
                "ncm_desc": p.get("suggested_ncm_desc", "")
            }
            for p in copilot_payload.get("pecas_items", [])
        ]
    }

    return jsonify({
        "success": True,
        "plate": copilot_payload.get("plate_display") or copilot_payload.get("plate"),
        "plate_display": copilot_payload.get("plate_display") or copilot_payload.get("plate"),
        "client_name": copilot_payload.get("client_name"),
        "car_model": copilot_payload.get("car_model"),
        "visit_num": copilot_payload.get("visit_num"),
        "entry_date": copilot_payload.get("entry_date"),
        "discriminacao_nfse": copilot_payload["copilot_texts"]["nfse_discriminacao"],
        "dados_tomador": copilot_payload["copilot_texts"]["tomador_resumo"],
        "valor_servicos": val_servicos_num,
        "valor_pecas": val_pecas_num,
        "valor_total": val_servicos_num + val_pecas_num,
        "nfse": nfse_obj,
        "nfe": nfe_obj,
        "tomador": copilot_payload.get("tomador"),
        "pecas_nfe": nfe_obj["itens_pecas"],
        "copilot": copilot_payload,
        "nf_control": nf_rec
    })

@app.route("/api/nf/queue", methods=["GET"])
def nf_queue_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    filter_type = request.args.get("filter", "pending").strip()
    query = request.args.get("q", "").strip()
    res = cache.get_nf_queue(filter_type=filter_type, query=query, db_path=db_path)
    return jsonify({
        "success": True,
        "queue": res.get("queue", []),
        "items": res.get("queue", []),
        "stats": res.get("stats", {})
    })

@app.route("/api/nf/pending", methods=["GET"])
def nf_pending_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    res = cache.get_nf_queue(filter_type="pending", db_path=db_path)
    pending = res.get("queue", [])
    return jsonify({
        "success": True,
        "pending": pending,
        "total": len(pending),
        "stats": res.get("stats", {})
    })

@app.route("/api/nf/status", methods=["POST"])
def nf_update_status_endpoint():
    data = _json_body()
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_nf_control(data, db_path)
        stats = cache.get_nf_queue(filter_type="pending", db_path=db_path).get("stats", {})
        return jsonify({
            "success": True,
            "nf": saved,
            "stats": stats
        })
    except (ValueError, TypeError) as e:
        log.info("Controle fiscal recusado: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/nf/copilot_text", methods=["GET"])
def nf_copilot_text_endpoint():
    file_path = resolve_spreadsheet_path(request.args.get("file_path", "").strip()) or ""
    text_type = request.args.get("type", "nfse_discriminacao").strip()
    plate = request.args.get("plate", "").strip()
    db_path = cache.get_db_path(BASE_DIR)

    det = None
    if file_path and os.path.exists(file_path):
        try:
            import parser
            det = parser.parse_file(file_path)
        except Exception:
            log.exception("Erro lendo planilha para texto fiscal: %s", file_path)
            det = None

    if not det and plate:
        hist = cache.get_car_history(plate, db_path)
        if hist:
            file_path = file_path or hist[0].get("file_path", "")
            det = hist[0].get("details") or hist[0]

    nf_rec = cache.get_nf_control(file_path=file_path, plate_clean=plate, db_path=db_path)

    if not det and nf_rec:
        val_s = float(nf_rec.get("valor_servico", 0.0) or 0.0)
        val_p = float(nf_rec.get("valor_pecas", 0.0) or 0.0)
        det = {
            "plate": nf_rec.get("plate"),
            "plate_display": nf_rec.get("plate_display") or nf_rec.get("plate"),
            "car_model": nf_rec.get("car_model"),
            "client_name": nf_rec.get("client_name"),
            "entry_date": nf_rec.get("entry_date"),
            "visit_num": nf_rec.get("visit_num"),
            "total_servicos": f"R$ {val_s:.2f}".replace(".", ","),
            "total_pecas": f"R$ {val_p:.2f}".replace(".", ","),
            "total": f"R$ {(val_s + val_p):.2f}".replace(".", ","),
        }
        file_path = file_path or nf_rec.get("file_path", "")

    if not det:
        return jsonify({"success": False, "error": "Visita ou planilha não encontrada"}), 404

    try:
        payload = nf_copilot.build_copilot_payload(file_path, det, nf_rec)
        texts = payload.get("copilot_texts", {})
        tomador = payload.get("tomador", {})

        target_text = ""
        if text_type == "nfse_discriminacao":
            target_text = texts.get("nfse_discriminacao", "")
        elif text_type == "tomador_resumo":
            target_text = texts.get("tomador_resumo", "")
        elif text_type == "nfe_pecas_resumo":
            target_text = texts.get("nfe_pecas_resumo", "")
        elif text_type == "nfe_pecas_tsv":
            target_text = texts.get("nfe_pecas_tsv", "")
        elif text_type == "cpf_only":
            target_text = tomador.get("cpf", "")
        elif text_type == "cep_only":
            target_text = tomador.get("cep", "")
        elif text_type == "endereco_only":
            target_text = tomador.get("address_single_line", "")
        else:
            return jsonify({"success": True, "texts": texts, "tomador": tomador})

        if request.args.get("raw") == "1" or request.headers.get("Accept") == "text/plain":
            return target_text, 200, {"Content-Type": "text/plain; charset=utf-8"}
        return jsonify({"success": True, "text": target_text, "type": text_type})
    except Exception as e:
        log.exception("Erro montando texto do copiloto fiscal")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/nf/export_batch", methods=["GET"])
def nf_export_batch_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    filter_type = request.args.get("filter", "pending").strip()
    fmt = request.args.get("format", "csv").strip().lower()

    res = cache.get_nf_queue(filter_type=filter_type, db_path=db_path)
    items = res.get("queue", [])

    if fmt == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "Placa", "Cliente", "CPF", "Telefone", "Modelo", "Data Visita",
            "Mão de Obra (R$)", "Status NFS-e", "Nº NFS-e",
            "Peças (R$)", "Status NF-e", "Nº NF-e", "Total Geral (R$)"
        ])
        for it in items:
            writer.writerow([
                it.get("plate_display") or it.get("plate"),
                it.get("client_name"),
                it.get("cpf"),
                it.get("phone"),
                it.get("car_model"),
                it.get("entry_date"),
                f"{it.get('valor_servico', 0.0):.2f}".replace(".", ","),
                it.get("status_servico"),
                it.get("nf_servico_num"),
                f"{it.get('valor_pecas', 0.0):.2f}".replace(".", ","),
                it.get("status_pecas"),
                it.get("nf_pecas_num"),
                f"{it.get('valor_total', 0.0):.2f}".replace(".", ",")
            ])
        content = output.getvalue()
        filename = f"MecatroniCar_Notas_{filter_type}.csv"
        return content, 200, {
            "Content-Type": "text/csv; charset=utf-8-sig",
            "Content-Disposition": f"attachment; filename={filename}"
        }
    else:
        # Formato TXT
        lines = [
            f"MECATRONICAR - FILA DE NOTAS FISCAIS ({filter_type.upper()})",
            f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "=" * 70
        ]
        for idx, it in enumerate(items, start=1):
            lines.append(f"{idx}. {it.get('plate_display') or it.get('plate')} | {it.get('client_name')} | {it.get('car_model')}")
            lines.append(f"   Data: {it.get('entry_date')} | Visita #{it.get('visit_num')}")
            lines.append(f"   NFS-e Santos (Serviços): R$ {it.get('valor_servico', 0.0):.2f} - Status: {it.get('status_servico')} (Nº {it.get('nf_servico_num') or '-'})")
            lines.append(f"   NF-e 55 (Peças): R$ {it.get('valor_pecas', 0.0):.2f} - Status: {it.get('status_pecas')} (Nº {it.get('nf_pecas_num') or '-'})")
            lines.append("-" * 70)
        content = "\n".join(lines)
        filename = f"MecatroniCar_Notas_{filter_type}.txt"
        return content, 200, {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Disposition": f"attachment; filename={filename}"
        }


@app.route("/api/analytics", methods=["GET"])
def get_analytics_endpoint():
    """
    Retorna métricas e indicadores de analytics da oficina MecatroniCar (Issue #16):
    - Volume de carros atendidos e médias por dia, semana e mês
    - Tempo médio de permanência (data entrada até entrega)
    - Médias financeiras de autopeças e mão de obra
    - Filtros por período: 30 dias (default), 90 dias, geral
    """
    period = request.args.get("period", "30")
    ref_date = request.args.get("ref_date", "")
    db_path = _db_path_from_request(request.args.get("db_path"))
    try:
        data = cache.get_analytics(period=period, db_path=db_path, ref_date=ref_date)
        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        log.exception("Erro calculando analytics")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


HTTP_THREADS = 8  # TV(s) em polling + secretária; o trabalho é I/O (SQLite/planilhas)


def create_http_server(host="0.0.0.0", port=DEFAULT_PORT, threads=HTTP_THREADS):
    """
    Servidor WSGI de produção. Usa o waitress (puro Python, roda no Windows) e, se ele
    não estiver instalado (instalações antigas atualizadas pelo updater sem pip),
    cai para o servidor do werkzeug com threads, avisando no log.
    O objeto retornado tem .run() (bloqueia) e .close().
    """
    try:
        from waitress.server import create_server
    except ImportError:
        log.warning("waitress não instalado; usando o servidor do werkzeug (rode: pip install waitress)")
        from werkzeug.serving import make_server

        srv = make_server(host, port, app, threaded=True)

        class _WerkzeugServer:
            def run(self):
                srv.serve_forever()

            def close(self):
                srv.shutdown()
                srv.server_close()

        return _WerkzeugServer()

    return create_server(
        app,
        host=host,
        port=port,
        threads=threads,
        ident="MecatroniCar",
        connection_limit=200,
        channel_timeout=60,
        cleanup_interval=30,
        clear_untrusted_proxy_headers=True,
    )


def start_background_indexing():
    """Indexação incremental + leitura do conteúdo em segundo plano (não atrasa o servidor)."""
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    db_path = cache.get_db_path(BASE_DIR)
    cache.init_db(db_path)
    if folder and os.path.isdir(folder):
        log.info("Indexando planilhas em segundo plano: %s", folder)
        return cache.start_background_index(folder, db_path, scan=True)
    log.info("Nenhuma pasta de planilhas configurada.")
    return None


def start_server(port=DEFAULT_PORT, host="0.0.0.0"):
    configure_logging()
    start_background_indexing()
    local_ip = get_local_ip()
    log.info("Iniciando servidor na rede local (LAN): http://%s:%s", local_ip, port)
    log.info("Painel de TV da oficina acessível em: http://%s:%s/tv", local_ip, port)
    server = create_http_server(host=host, port=port)
    try:
        server.run()
    finally:
        cache.stop_background_index(timeout=2.0)

if __name__ == "__main__":
    start_server()
