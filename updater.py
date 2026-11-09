# -*- coding: utf-8 -*-
"""
MecatroniCar - Sistema de Verificação e Atualização Automática
Permite que qualquer pessoa (mesmo sem conhecimento técnico) atualize o sistema com 1 clique.
Preserva as configurações do usuário (config.json) e o banco de dados local (oficina_cache.db).
"""
import os
import sys
import json
import urllib.request
import zipfile
import shutil
import subprocess
import tempfile
import threading

CURRENT_VERSION = "1.0.4"
REPO_OWNER = "BrenoSGTO"
REPO_NAME = "app-mecatronicar"

VERSION_JSON_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/version.json"
GITHUB_API_RELEASE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

def parse_version_tuple(v_str):
    if not v_str:
        return (0, 0, 0)
    cleaned = v_str.strip().lstrip("vV")
    parts = []
    for p in cleaned.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])

def check_for_updates():
    """
    Verifica se há uma versão mais recente no GitHub.
    Retorna um dicionário com os detalhes da atualização.
    """
    latest_info = None

    # Método 1: Tentar ler o version.json do repositório (rápido e sem limite de requisição)
    try:
        req = urllib.request.Request(
            VERSION_JSON_URL,
            headers={"User-Agent": "MecatroniCar-Updater"}
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                latest_info = {
                    "version": data.get("version", "1.0.0"),
                    "download_url": data.get("download_url", ""),
                    "release_notes": data.get("release_notes", "Melhorias de estabilidade e novas funcionalidades."),
                    "published_at": data.get("published_at", "")
                }
    except Exception as e:
        print(f"Aviso ao consultar version.json: {e}")

    # Método 2: Fallback para a API de Releases do GitHub
    if not latest_info or not latest_info.get("download_url"):
        try:
            req = urllib.request.Request(
                GITHUB_API_RELEASE_URL,
                headers={"User-Agent": "MecatroniCar-Updater"}
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag = data.get("tag_name", "").lstrip("vV")
                    
                    # Localizar asset zip
                    download_url = ""
                    for asset in data.get("assets", []):
                        if asset.get("name", "").lower().endswith(".zip"):
                            download_url = asset.get("browser_download_url", "")
                            break
                    if not download_url:
                        download_url = data.get("zipball_url", "")

                    latest_info = {
                        "version": tag or "1.0.0",
                        "download_url": download_url,
                        "release_notes": data.get("body", "Melhorias e correções no sistema."),
                        "published_at": data.get("published_at", "")
                    }
        except Exception as e:
            print(f"Aviso ao consultar API do GitHub: {e}")

    if not latest_info:
        return {
            "success": False,
            "error": "Não foi possível conectar aos servidores de atualização. Verifique a conexão com a internet.",
            "current_version": CURRENT_VERSION,
            "update_available": False
        }

    current_tuple = parse_version_tuple(CURRENT_VERSION)
    latest_tuple = parse_version_tuple(latest_info["version"])

    is_newer = latest_tuple > current_tuple

    return {
        "success": True,
        "current_version": CURRENT_VERSION,
        "latest_version": latest_info["version"],
        "update_available": is_newer,
        "download_url": latest_info["download_url"],
        "release_notes": latest_info["release_notes"],
        "published_at": latest_info["published_at"]
    }

def apply_update_process(download_url, base_dir, progress_callback=None):
    """
    Baixa o arquivo zip da nova versão, prepara o lote de atualização e reinicia o aplicativo.
    """
    if not download_url:
        raise ValueError("URL de download não fornecida.")

    temp_dir = tempfile.mkdtemp(prefix="mecatronicar_update_")
    zip_path = os.path.join(temp_dir, "update.zip")
    extract_path = os.path.join(temp_dir, "extracted")

    if progress_callback:
        progress_callback("Baixando nova versão do sistema...", 10)

    # Download do arquivo
    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "MecatroniCar-Updater"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as out_f:
        total_len = resp.headers.get("content-length")
        if total_len:
            total_len = int(total_len)
            downloaded = 0
            while True:
                chunk = resp.read(16384)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                pct = int(10 + (downloaded / total_len) * 50)
                if progress_callback:
                    progress_callback(f"Baixando atualização: {pct}%", pct)
        else:
            out_f.write(resp.read())

    if progress_callback:
        progress_callback("Extraindo arquivos...", 65)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_path)

    # Identificar diretório raiz descompactado (caso o zip contenha uma subpasta raiz)
    contents = os.listdir(extract_path)
    source_dir = extract_path
    if len(contents) == 1 and os.path.isdir(os.path.join(extract_path, contents[0])):
        source_dir = os.path.join(extract_path, contents[0])

    if progress_callback:
        progress_callback("Preparando script de instalação...", 85)

    # Criar script batch temporário para fechar o processo atual, copiar os arquivos preservando config e reabrir
    batch_script_path = os.path.join(temp_dir, "executar_atualizacao.bat")
    current_pid = os.getpid()

    # Preservar arquivos de usuário: config.json, oficina_cache.db, planilhas_exemplo
    script_content = f"""@echo off
chcp 65001 > nul
echo ===================================================
echo   Atualizando MecatroniCar para a nova versão...
echo   Por favor, aguarde alguns instantes.
echo ===================================================
echo.

:: Aguarda processo anterior encerrar
timeout /t 2 /nobreak > nul

:: Copiar arquivos novos substituindo os antigos
xcopy /E /Y /I "{source_dir}" "{base_dir}" > nul

:: Limpar pasta temporaria
timeout /t 1 /nobreak > nul

:: Reabrir o aplicativo atualizado
cd /d "{base_dir}"
if exist "MecatroniCar.exe" (
    start "" "MecatroniCar.exe"
) else (
    start "" python app.py
)

exit
"""

    with open(batch_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    if progress_callback:
        progress_callback("Concluído! Reiniciando o aplicativo...", 100)

    # Executar script em segundo plano e encerrar este processo
    subprocess.Popen(["cmd.exe", "/c", batch_script_path], close_fds=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    # Encerrar aplicativo após breve delay para liberar arquivos
    def _exit():
        time.sleep(1.0)
        os._exit(0)

    import time
    threading.Thread(target=_exit, daemon=True).start()
    return True
