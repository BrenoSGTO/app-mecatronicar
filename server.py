# -*- coding: utf-8 -*-
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from flask import Flask, jsonify, request, send_from_directory
import cache
import config
import updater

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/api/config", methods=["GET"])
def get_config_endpoint():
    cfg = config.load_config(BASE_DIR)
    db_path = cache.get_db_path(BASE_DIR)
    stats = cache.get_stats(db_path)
    return jsonify({
        "config": cfg,
        "stats": stats,
        "version": updater.CURRENT_VERSION
    })

@app.route("/api/config", methods=["POST"])
def update_config_endpoint():
    data = request.json or {}
    cfg = config.load_config(BASE_DIR)
    
    new_folder = data.get("spreadsheet_folder")
    if new_folder is not None:
        cfg["spreadsheet_folder"] = new_folder.strip()
    if "theme" in data:
        cfg["theme"] = data["theme"]
    if "sort_order" in data:
        cfg["sort_order"] = data["sort_order"]
    if "ui_zoom" in data:
        try:
            cfg["ui_zoom"] = max(50, min(150, int(data["ui_zoom"])))
        except Exception:
            pass
        
    config.save_config(cfg, BASE_DIR)
    
    # Auto re-index if folder exists
    scan_res = None
    if cfg.get("spreadsheet_folder") and os.path.isdir(cfg["spreadsheet_folder"]):
        db_path = cache.get_db_path(BASE_DIR)
        scan_res = cache.scan_and_index_folder(cfg["spreadsheet_folder"], db_path)
        
    db_path = cache.get_db_path(BASE_DIR)
    stats = cache.get_stats(db_path)
    return jsonify({
        "success": True,
        "config": cfg,
        "stats": stats,
        "scan_result": scan_res,
        "version": updater.CURRENT_VERSION
    })

@app.route("/api/select_folder", methods=["POST"])
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
        except Exception as e:
            print("Erro no filedialog:", e)

    t = threading.Thread(target=_open_dialog)
    t.start()
    t.join(timeout=60)
    
    if selected_folder:
        selected_folder = os.path.normpath(selected_folder)
        cfg["spreadsheet_folder"] = selected_folder
        config.save_config(cfg, BASE_DIR)
        
        db_path = cache.get_db_path(BASE_DIR)
        scan_res = cache.scan_and_index_folder(selected_folder, db_path)
        stats = cache.get_stats(db_path)
        
        return jsonify({
            "success": True,
            "folder": selected_folder,
            "scan_result": scan_res,
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
        
    db_path = cache.get_db_path(BASE_DIR)
    scan_res = cache.scan_and_index_folder(folder, db_path)
    stats = cache.get_stats(db_path)
    return jsonify({
        "success": True,
        "scan_result": scan_res,
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

@app.route("/api/open_file", methods=["POST"])
def open_file_endpoint():
    data = request.json or {}
    fpath = data.get("file_path", "")
    if not fpath or not os.path.exists(fpath):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
        
    try:
        os.startfile(fpath)
        return jsonify({"success": True, "message": "Arquivo aberto no Excel com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Documentos PDF Profissionais (CP-04 e CP-05)
@app.route("/api/orcamento_pdf", methods=["GET"])
def orcamento_pdf_endpoint():
    import pdf_generator
    fpath = request.args.get("file_path", "")
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
        return f"Erro gerando orçamento: {str(e)}", 500

@app.route("/api/checklist_pdf", methods=["GET"])
def checklist_pdf_endpoint():
    import pdf_generator
    fpath = request.args.get("file_path", "")
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
        html_content = pdf_generator.generate_checklist_from_file(fpath, auto_print=auto_print)
        return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return f"Erro gerando checklist: {str(e)}", 500

# Updater API endpoints
@app.route("/api/check_update", methods=["GET"])
def check_update_endpoint():
    update_data = updater.check_for_updates()
    return jsonify(update_data)

@app.route("/api/apply_update", methods=["POST"])
def apply_update_endpoint():
    data = request.json or {}
    download_url = data.get("download_url", "")
    if not download_url:
        return jsonify({"success": False, "error": "URL de download ausente"}), 400
        
    try:
        # Run in thread so response can be sent to browser
        threading.Thread(
            target=updater.apply_update_process,
            args=(download_url, BASE_DIR),
            daemon=True
        ).start()
        return jsonify({"success": True, "message": "Atualização iniciada com sucesso. O sistema irá reiniciar automaticamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def start_server(port=5000):
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if folder and os.path.isdir(folder):
        db_path = cache.get_db_path(BASE_DIR)
        print(f"Indexando planilhas em {folder}...")
        cache.scan_and_index_folder(folder, db_path)
        
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_server()
