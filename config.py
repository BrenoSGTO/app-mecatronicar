# -*- coding: utf-8 -*-
import os
import json

CONFIG_FILE = "config.json"

def get_config_path(base_dir=None):
    if base_dir:
        return os.path.join(base_dir, CONFIG_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)

def load_config(base_dir=None):
    cpath = get_config_path(base_dir)
    default_sample_dir = r"C:\Users\breno\Documents\Projetos\APP Oficina\planilhas_exemplo"
    default_config = {
        "spreadsheet_folder": default_sample_dir if os.path.exists(default_sample_dir) else "",
        "theme": "light",
        "sort_order": "desc"
    }
    
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
            
    return default_config

def save_config(config_dict, base_dir=None):
    cpath = get_config_path(base_dir)
    try:
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("Erro salvando config:", e)
        return False
