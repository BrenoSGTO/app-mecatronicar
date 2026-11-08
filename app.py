# -*- coding: utf-8 -*-
"""
MecatroniCar - Aplicativo de Histórico de Veículos e Serviços
Inicia o servidor local e abre a janela do aplicativo no Windows.
"""
import os
import sys
import time
import subprocess
import webbrowser
import threading
from server import app, BASE_DIR
import config
import cache

PORT = 54321
URL = f"http://127.0.0.1:{PORT}"

def get_browser_app_cmd(url):
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for exe in candidates:
        if os.path.exists(exe):
            return [exe, f"--app={url}", "--window-size=1280,850"]
    return None

def launch_ui():
    time.sleep(0.8) # Wait briefly for Flask to bind
    cmd = get_browser_app_cmd(URL)
    if cmd:
        try:
            subprocess.Popen(cmd)
            return
        except Exception as e:
            print(f"Não foi possível abrir em modo app: {e}")
    # Fallback to default browser
    webbrowser.open(URL)

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def main():
    print("=" * 60)
    print("  MecatroniCar - Sistema de Histórico da Oficina Mecânica")
    print("=" * 60)
    
    # Ensure local cache DB is always initialized
    db_path = cache.get_db_path(BASE_DIR)
    cache.init_db(db_path)

    # If server is already running in background, just open the UI window and exit
    if is_port_in_use(PORT):
        print(f"Servidor já em execução em {URL}. Abrindo janela...")
        launch_ui()
        return

    # Check config
    cfg = config.load_config(BASE_DIR)
    folder = cfg.get("spreadsheet_folder", "")
    if folder and os.path.isdir(folder):
        print(f"Pasta de planilhas configurada: {folder}")
        print("Verificando índice de planilhas...")
        res = cache.scan_and_index_folder(folder, db_path)
        print(f"Índice atualizado: {res.get('total', 0)} planilhas carregadas.")
    else:
        print("Nenhuma pasta de planilhas configurada. Você poderá selecioná-la na tela do aplicativo.")
        
    print(f"\nAbrindo aplicativo em {URL}...")
    threading.Thread(target=launch_ui, daemon=True).start()
    
    # Run server
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()

