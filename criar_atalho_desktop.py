# -*- coding: utf-8 -*-
"""
Cria um atalho do MecatroniCar na Área de Trabalho do Windows.
"""
import os
import sys

def create_desktop_shortcut():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    target_vbs = os.path.join(app_dir, "iniciar_app_silencioso.vbs")
    target_bat = os.path.join(app_dir, "iniciar_app.bat")
    
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop_dir):
        # Alternative Windows desktop path (e.g. OneDrive)
        onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        if os.path.exists(onedrive_desktop):
            desktop_dir = onedrive_desktop
            
    shortcut_path = os.path.join(desktop_dir, "MecatroniCar - Oficina.lnk")
    
    # Use powershell or wscript to create .lnk
    ps_cmd = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{target_vbs}"
    $Shortcut.WorkingDirectory = "{app_dir}"
    $Shortcut.Description = "MecatroniCar - Histórico da Oficina Mecânica"
    $Shortcut.IconLocation = "shell32.dll,13"
    $Shortcut.Save()
    """
    
    try:
        import subprocess
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print(f"Atalho criado com sucesso na Área de Trabalho: {shortcut_path}")
        return True
    except Exception as e:
        print(f"Erro criando atalho: {e}")
        return False

if __name__ == "__main__":
    create_desktop_shortcut()
