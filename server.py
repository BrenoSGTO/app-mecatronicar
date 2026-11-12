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
import nf_copilot

@app.route("/api/nf/data", methods=["GET"])
@app.route("/api/nf/data/<plate>", methods=["GET"])
def nf_data_endpoint(plate=None):
    db_path = cache.get_db_path(BASE_DIR)
    file_path = request.args.get("file_path", "").strip()
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
        except Exception as e:
            print("Erro lendo planilha para copiloto fiscal:", e)

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
        return jsonify({"success": False, "error": "Visita ou veículo não encontrado"}), 404

    nf_rec = cache.get_nf_control(file_path=fpath, plate_clean=target_plate, visit_num=visit_num, db_path=db_path)
    copilot_payload = nf_copilot.build_copilot_payload(fpath, det or last_visit, nf_rec)

    # Campos compatíveis com versões legadas
    tot_servicos = copilot_payload.get("total_servicos", "R$ 0,00")
    tot_pecas = copilot_payload.get("total_pecas", "R$ 0,00")

    return jsonify({
        "success": True,
        "plate": copilot_payload.get("plate_display") or copilot_payload.get("plate"),
        "client_name": copilot_payload.get("client_name"),
        "car_model": copilot_payload.get("car_model"),
        "visit_num": copilot_payload.get("visit_num"),
        "discriminacao_nfse": copilot_payload["copilot_texts"]["nfse_discriminacao"],
        "dados_tomador": copilot_payload["copilot_texts"]["tomador_resumo"],
        "valor_servicos": tot_servicos,
        "valor_pecas": tot_pecas,
        "valor_total": copilot_payload.get("total_geral"),
        "pecas_nfe": [
            {
                "description": p.get("description"),
                "quantity": p.get("quantity"),
                "unit_price": p.get("unit_price"),
                "total_price": p.get("total_price"),
                "ncm": p.get("suggested_ncm"),
                "cfop": str(p.get("suggested_cfop", "5405")).replace(".", ""),
                "csosn": p.get("suggested_csosn")
            }
            for p in copilot_payload.get("pecas_items", [])
        ],
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
    data = request.json or {}
    db_path = cache.get_db_path(BASE_DIR)
    try:
        saved = cache.save_nf_control(data, db_path)
        stats = cache.get_nf_queue(filter_type="pending", db_path=db_path).get("stats", {})
        return jsonify({
            "success": True,
            "nf": saved,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/nf/copilot_text", methods=["GET"])
def nf_copilot_text_endpoint():
    file_path = request.args.get("file_path", "").strip()
    text_type = request.args.get("type", "nfse_discriminacao").strip()
    plate = request.args.get("plate", "").strip()

    if not file_path and plate:
        db_path = cache.get_db_path(BASE_DIR)
        hist = cache.get_car_history(plate, db_path)
        if hist:
            file_path = hist[0].get("file_path", "")

    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "Planilha não encontrada"}), 404

    try:
        import parser
        det = parser.parse_file(file_path)
        db_path = cache.get_db_path(BASE_DIR)
        nf_rec = cache.get_nf_control(file_path=file_path, db_path=db_path)
        payload = nf_copilot.build_copilot_payload(file_path, det, nf_rec)

        texts = payload.get("copilot_texts", {})
        tomador = payload.get("tomador", {})

        if text_type == "nfse_discriminacao":
            return texts.get("nfse_discriminacao", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "tomador_resumo":
            return texts.get("tomador_resumo", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "nfe_pecas_resumo":
            return texts.get("nfe_pecas_resumo", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "nfe_pecas_tsv":
            return texts.get("nfe_pecas_tsv", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "cpf_only":
            return tomador.get("cpf", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "cep_only":
            return tomador.get("cep", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        elif text_type == "endereco_only":
            return tomador.get("address_single_line", ""), 200, {"Content-Type": "text/plain; charset=utf-8"}
        else:
            return jsonify({"success": True, "texts": texts, "tomador": tomador})
    except Exception as e:
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
