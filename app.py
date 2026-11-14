# -*- coding: utf-8 -*-
"""
MecatroniCar - Aplicativo de Histórico de Veículos e Serviços
Inicia o servidor local e abre a janela do aplicativo no Windows com identidade própria na Barra de Tarefas.
"""
import os
import sys
import time
import uuid
import ctypes
from ctypes import wintypes
import subprocess
import webbrowser
import threading
import urllib.request
from server import app, BASE_DIR, get_local_ip
import server
import config
import cache

PORT = 54321
URL = f"http://127.0.0.1:{PORT}"
APP_USER_MODEL_ID = "MecatroniCar.Oficina.App.1"
WINDOW_TITLE_MATCH = "MecatroniCar - Histórico de Veículos e Serviços"

class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", ctypes.c_byte * 16), ("pid", wintypes.DWORD)]

class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("pwszVal", ctypes.c_wchar_p),
        ("padding", ctypes.c_ulonglong),
    ]

VT_LPWSTR = 31
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010

def set_process_app_id():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass

def apply_taskbar_identity_to_hwnd(hwnd):
    """
    Aplica o AppUserModelID, comando de reinicialização (MecatroniCar.exe),
    nome e ícone oficial diretamente na janela do Windows para que, ao clicar em
    'Fixar na barra de tarefas', o Windows fixe o MecatroniCar e não o Microsoft Edge.
    """
    if os.name != "nt" or not hwnd:
        return False
    try:
        exe_path = os.path.join(BASE_DIR, "MecatroniCar.exe")
        if not os.path.exists(exe_path):
            exe_path = os.path.join(BASE_DIR, "iniciar_app_silencioso.vbs")
        icon_path = os.path.join(BASE_DIR, "app_icon.ico")

        guid_bytes = uuid.UUID("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}").bytes_le
        iid_bytes = uuid.UUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}").bytes_le
        store_ptr = ctypes.c_void_p()

        hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd),
            (ctypes.c_byte * 16).from_buffer_copy(iid_bytes),
            ctypes.byref(store_ptr),
        )
        if hr != 0 or not store_ptr.value:
            return False

        vtable = ctypes.cast(
            ctypes.cast(store_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )
        SetValue = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(PROPERTYKEY),
            ctypes.POINTER(PROPVARIANT),
        )(vtable[6])
        Commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[7])
        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])

        props = [
            (5, APP_USER_MODEL_ID),
            (2, f'"{exe_path}"'),
            (4, "MecatroniCar - Oficina"),
        ]
        if os.path.exists(icon_path):
            props.append((3, f"{icon_path},0"))

        for pid, val in props:
            pk = PROPERTYKEY((ctypes.c_byte * 16).from_buffer_copy(guid_bytes), pid)
            pv = PROPVARIANT()
            pv.vt = VT_LPWSTR
            pv.pwszVal = val
            SetValue(store_ptr, ctypes.byref(pk), ctypes.byref(pv))

        Commit(store_ptr)
        Release(store_ptr)

        if os.path.exists(icon_path):
            hicon_big = ctypes.windll.user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE
            )
            hicon_small = ctypes.windll.user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )
            if hicon_big:
                ctypes.windll.user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_BIG, hicon_big)
            if hicon_small:
                ctypes.windll.user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_SMALL, hicon_small)

        return True
    except Exception:
        return False

def find_and_brand_app_windows():
    if os.name != "nt":
        return
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    styled_hwnds = set()

    for _ in range(30):
        found_any = False

        def enum_cb(hwnd, lparam):
            nonlocal found_any
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if "MecatroniCar" in title and "Histórico de Veículos" in title:
                        if hwnd not in styled_hwnds:
                            if apply_taskbar_identity_to_hwnd(hwnd):
                                styled_hwnds.add(hwnd)
                                found_any = True
            return True

        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        if found_any:
            time.sleep(1.0)
        else:
            time.sleep(0.35)

def get_browser_app_cmd(url):
    profile_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", BASE_DIR),
        "MecatroniCar_AppProfile"
    )
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for exe in candidates:
        if os.path.exists(exe):
            return [
                exe,
                f"--app={url}",
                f"--user-data-dir={profile_dir}",
                "--window-size=1280,850",
                "--no-first-run",
                "--no-default-browser-check",
            ]
    return None

def wait_for_server(timeout=15.0, interval=0.05):
    """Espera o servidor responder em /api/health (em vez de um sleep fixo)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def launch_ui(wait_server=True):
    """Abre a janela do app assim que o servidor responde. Retorna a thread de 'branding'."""
    if wait_server and not wait_for_server():
        print("Aviso: o servidor demorou a responder; abrindo a janela mesmo assim.")
    cmd = get_browser_app_cmd(URL)
    if cmd:
        try:
            subprocess.Popen(cmd)
            t = threading.Thread(target=find_and_brand_app_windows, daemon=True)
            t.start()
            return t
        except Exception as e:
            print(f"Não foi possível abrir em modo app: {e}")
    webbrowser.open(URL)
    return None

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def get_running_server_version(port):
    import urllib.request
    import json
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("version")
    except Exception:
        return None

def kill_process_on_port(port):
    if os.name != "nt":
        return
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr :{port}',
            shell=True
        ).decode("cp1252", errors="ignore")
        pids = set()
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in line.upper():
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    pids.add(int(pid))
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        # Espera a porta liberar (em vez de um sleep fixo).
        deadline = time.monotonic() + 5.0
        while pids and is_port_in_use(port) and time.monotonic() < deadline:
            time.sleep(0.1)
    except Exception as e:
        print(f"Aviso ao encerrar o servidor antigo: {e}")

def main():
    server.configure_logging()
    set_process_app_id()
    print("=" * 60)
    print("  MecatroniCar - Sistema de Histórico da Oficina Mecânica")
    print("=" * 60)
    
    # Ensure local cache DB and Desktop/Start Menu shortcuts are initialized
    db_path = cache.get_db_path(BASE_DIR)
    cache.init_db(db_path)
    try:
        import criar_atalho_desktop
        threading.Thread(target=criar_atalho_desktop.create_desktop_shortcut, daemon=True).start()
    except Exception:
        pass

    # If server is already running in background, check if its version matches
    if is_port_in_use(PORT):
        import updater
        running_ver = get_running_server_version(PORT)
        if running_ver == updater.CURRENT_VERSION:
            print(f"Servidor v{running_ver} já em execução em {URL}. Abrindo janela...")
            brand_thread = launch_ui(wait_server=False)
            if brand_thread is not None:
                brand_thread.join(timeout=6.0)  # aplica o ícone/identidade na barra de tarefas
            return
        else:
            print(f"Reiniciando servidor antigo (v{running_ver}) para nova versão (v{updater.CURRENT_VERSION})...")
            kill_process_on_port(PORT)

    # O servidor sobe primeiro (o waitress já escuta a porta ao ser criado) e a
    # indexação das planilhas roda em segundo plano: a janela abre na hora e a
    # busca já funciona pelo nome dos arquivos enquanto o conteúdo é lido.
    # Escuta em todas as interfaces para a TV da oficina acessar pela LAN.
    http_server = server.create_http_server(host="0.0.0.0", port=PORT)
    if server.start_background_indexing() is None:
        print("Nenhuma pasta de planilhas configurada. Você poderá selecioná-la na tela do aplicativo.")

    local_ip = get_local_ip()
    print(f"\nAbrindo aplicativo em {URL}...")
    print(f"Painel de TV da Oficina (LAN): http://{local_ip}:{PORT}/tv")
    threading.Thread(target=launch_ui, daemon=True, name="mecatronicar-ui").start()

    try:
        http_server.run()
    finally:
        cache.stop_background_index(timeout=2.0)

if __name__ == "__main__":
    main()


