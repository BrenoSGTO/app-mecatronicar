# -*- coding: utf-8 -*-
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from flask import Flask, jsonify, request, send_from_directory
import socket
import datetime
import cache
import config
import updater

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

def get_local_ip():
    """
    Descobre o IP local da máquina na rede da oficina (LAN/Wi-Fi).
    """
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

@app.route("/tv")
def tv_route():
    return send_from_directory(STATIC_DIR, "tv.html")

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

@app.route("/api/save_order", methods=["POST"])
def save_order_endpoint():
    import excel_writer
    data = request.json or {}
    order_data = data.get("order_data") or data
    existing_file_path = data.get("existing_file_path") or None
    
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if not folder or not os.path.isdir(folder):
        sample_dir = os.path.join(BASE_DIR, "planilhas_exemplo")
        folder = sample_dir if os.path.isdir(sample_dir) else BASE_DIR
        
    try:
        res = excel_writer.save_order_to_excel(order_data, folder, existing_filepath=existing_file_path)
        db_path = cache.get_db_path(BASE_DIR)
        parsed = cache.index_single_file(res["file_path"], db_path, old_fpath=existing_file_path)
        stats = cache.get_stats(db_path)
        
        return jsonify({
            "success": True,
            "message": "Ordem de serviço salva com sucesso!",
            "file_path": res["file_path"],
            "file_name": res["file_name"],
            "plate": parsed.get("plate", "") if parsed else order_data.get("car_plate", ""),
            "visit_num": parsed.get("visit_num", "") if parsed else order_data.get("visit_num", ""),
            "details": parsed,
            "stats": stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

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

# ==========================================
# ROTAS DO PÁTIO / TV DA OFICINA (CP-06)
# ==========================================
@app.route("/api/patio", methods=["GET"])
def get_patio_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    summary = cache.get_patio_summary(db_path)
    local_ip = get_local_ip()
    return jsonify({
        "success": True,
        "total": summary["total"],
        "by_status": summary["by_status"],
        "cars": summary["cars"],
        "statuses": cache.PATIO_STATUSES,
        "local_ip": local_ip,
        "tv_url": f"http://{local_ip}:54321/tv",
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/patio", methods=["POST"])
def save_patio_endpoint():
    data = request.json or {}
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_patio_car(data, db_path)
        return jsonify({"success": True, "car": saved})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/patio/status", methods=["POST"])
def update_patio_status_endpoint():
    data = request.json or {}
    car_id = data.get("car_id") or data.get("id")
    status = data.get("status")
    if not car_id or not status:
        return jsonify({"success": False, "error": "ID e status são obrigatórios"}), 400
    
    auth_name = data.get("authorized_name")
    auth_doc = data.get("authorized_doc")
    auth_phone = data.get("authorized_phone")
    
    db_path = cache.get_db_path(BASE_DIR)
    try:
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
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/patio/<int:car_id>", methods=["DELETE"])
def delete_patio_car_endpoint(car_id):
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_patio_car(car_id, db_path)
    if success:
        return jsonify({"success": True, "message": "Veículo removido do pátio com sucesso."})
    return jsonify({"success": False, "error": "Veículo não encontrado no pátio"}), 404

@app.route("/api/patio/remove", methods=["POST"])
def remove_patio_car_post_endpoint():
    data = request.json or {}
    car_id = data.get("car_id") or data.get("id")
    if not car_id:
        return jsonify({"success": False, "error": "ID do veículo ausente"}), 400
    db_path = cache.get_db_path(BASE_DIR)
    success = cache.delete_patio_car(car_id, db_path)
    return jsonify({"success": success})

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
    data = request.json or {}
    existing_fpath = data.get("existing_file_path") or data.get("existing_filepath") or None
    db_path = cache.get_db_path(BASE_DIR)
    cfg = config.load_config(BASE_DIR)
    target_folder = cfg.get("spreadsheet_folder") or os.path.join(BASE_DIR, "planilhas_exemplo")
    try:
        res = excel_writer.save_new_or_updated_os(data, target_folder=target_folder, db_path=db_path, existing_filepath=existing_fpath)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ==========================================
# COPILOTO FISCAL (CP-07)
# ==========================================

@app.route("/api/nf/data/<plate>", methods=["GET"])
def nf_data_endpoint(plate):
    db_path = cache.get_db_path(BASE_DIR)
    history = cache.get_car_history(plate, db_path)
    if not history:
        return jsonify({"success": False, "error": "Histórico do veículo não encontrado"}), 404
        
    last = history[0]
    det = last.get("details") or {}
    
    # Extrai peças e serviços da última visita
    pecas = det.get("pecas_items") or []
    servicos = det.get("servicos_items") or []
    
    tot_pecas = sum(float(p.get("total", 0) or 0) for p in pecas)
    tot_servicos = sum(float(s.get("total", 0) or 0) for s in servicos)
    
    # Formata texto da discriminação para NFS-e Santos (Item 14.01)
    servicos_nomes = ", ".join([str(s.get("desc", "")).strip() for s in servicos if s.get("desc")])
    if not servicos_nomes:
        servicos_nomes = "REVISÃO GERAL / MANUTENÇÃO PREVENTIVA E CORRETIVA"
        
    client_name = last.get("client_name") or ""
    car_model = last.get("car_model") or ""
    odometer = last.get("odometer") or ""
    plate_fmt = last.get("plate_display") or last.get("plate")
    
    discriminacao_nfse = (
        f"PRESTAÇÃO DE SERVIÇOS MECÂNICOS AUTOMOTIVOS EM VEÍCULO:\n"
        f"PLACA: {plate_fmt} | MODELO: {car_model} | KM: {odometer}\n"
        f"SERVIÇOS EXECUTADOS: {servicos_nomes}.\n"
        f"LOCAL DA PRESTAÇÃO: SANTOS/SP | ENQUADRAMENTO: SUBITEM 14.01 (SERVIÇOS MECÂNICOS)"
    )
    
    dados_tomador = (
        f"Nome/Razão Social: {client_name}\n"
        f"CPF/CNPJ: {det.get('cpf', '')}\n"
        f"Endereço: {det.get('address', '')}, nº {det.get('address_num', '')} {det.get('address_compl', '')}\n"
        f"Bairro: {det.get('neighborhood', '')} - {det.get('city', 'Santos')}/SP\n"
        f"CEP: {det.get('cep', '')}\n"
        f"Telefone: {det.get('phone', '')}\n"
        f"Email: {det.get('email', '')}"
    )
    
    pecas_nfe = []
    for p in pecas:
        pecas_nfe.append({
            "desc": p.get("desc", ""),
            "qty": p.get("qty", 1),
            "unit_price": p.get("unit_price", 0),
            "total": p.get("total", 0),
            "cfop": "5405",
            "ncm_sugerido": "8708.29.99",
            "cst_icms": "060"
        })
        
    nf_rec = cache.get_nf_by_plate(plate, db_path)
    
    return jsonify({
        "success": True,
        "plate": plate_fmt,
        "client_name": client_name,
        "car_model": car_model,
        "visit_num": last.get("visit_num"),
        "discriminacao_nfse": discriminacao_nfse,
        "dados_tomador": dados_tomador,
        "valor_servicos": tot_servicos,
        "pecas_nfe": pecas_nfe,
        "valor_pecas": tot_pecas,
        "valor_total": tot_servicos + tot_pecas,
        "nf_control": nf_rec
    })

@app.route("/api/nf/pending", methods=["GET"])
def nf_pending_endpoint():
    db_path = cache.get_db_path(BASE_DIR)
    pending = cache.get_pending_nfs(db_path)
    return jsonify({"success": True, "pending": pending, "total": len(pending)})

@app.route("/api/nf/status", methods=["POST"])
def nf_update_status_endpoint():
    data = request.json or {}
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_nf_control(data, db_path)
        return jsonify({"success": True, "nf": saved})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


def start_server(port=5000):
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if folder and os.path.isdir(folder):
        db_path = cache.get_db_path(BASE_DIR)
        print(f"Indexando planilhas em {folder}...")
        cache.scan_and_index_folder(folder, db_path)
        
    local_ip = get_local_ip()
    print(f"Iniciando servidor na rede local (LAN): http://{local_ip}:{port}")
    print(f"Painel de TV da oficina acessível em: http://{local_ip}:{port}/tv")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_server()
