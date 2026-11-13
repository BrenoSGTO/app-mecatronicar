# -*- coding: utf-8 -*-
"""
Script oficial de sincronização e geração de assets visuais:
1. Logos oficiais em SVG das montadoras automotivas obtidas da Wikimedia Commons e diretrizes de marca (/static/brands/)
2. Modelos fotorrealistas de alta definição baseados em fotografia de catálogo de estúdio automotivo (/static/models/)
"""

import os
import shutil
import urllib.request
import urllib.parse
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS_DIR = os.path.join(BASE_DIR, "static", "brands")
MODELS_DIR = os.path.join(BASE_DIR, "static", "models")

os.makedirs(BRANDS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'MecatroniCarApp/1.0 (contact: breno@mecatronicar.com.br)'}

def get_commons_url(title):
    api = f'https://commons.wikimedia.org/w/api.php?action=query&titles=File:{urllib.parse.quote(title)}&prop=imageinfo&iiprop=url&format=json'
    req = urllib.request.Request(api, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        pages = data['query']['pages']
        for k, v in pages.items():
            if 'imageinfo' in v:
                return v['imageinfo'][0]['url']
    return None

COMMONS_LOGOS = {
    'fiat': 'Fiat_Automobiles_logo.svg',
    'volkswagen': 'Volkswagen_logo_2019.svg',
    'chevrolet': 'Chevrolet-logo.svg',
    'toyota': 'Toyota_logo.svg',
    'hyundai': 'Hyundai_Motor_Company_logo.svg',
    'renault': 'Renault 2021.svg',
    'jeep': 'Jeep_logo.svg',
    'nissan': 'Nissan_2020_logo.svg',
    'honda': 'Honda_logo.svg',
    'ford': 'Ford_Motor_Company_Logo.svg',
    'peugeot': 'Peugeot_Logo.svg',
    'citroen': 'Citroen_2022.svg',
    'mitsubishi': 'Mitsubishi_logo.svg',
    'chery': 'Chery_symbol.svg',
    'bmw': 'BMW.svg',
    'mercedes': 'Mercedes-Benz_Logo_2010.svg',
    'audi': 'Audi-Logo_2016.svg',
    'kia': 'KIA_logo3.svg',
    'byd': 'BYD_Auto_2022_logo.svg'
}

def sync_official_logos():
    print("Sincronizando logos oficiais das montadoras...")
    for brand, filename in COMMONS_LOGOS.items():
        dest = os.path.join(BRANDS_DIR, f"{brand}.svg")
        try:
            url = get_commons_url(filename)
            if url:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req) as resp:
                    content = resp.read().decode('utf-8', errors='ignore')
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"  OK: {brand}.svg ({len(content)} bytes)")
        except Exception as e:
            print(f"  Erro ao baixar {brand}: {e}")

    # Logotipo oficial da MecatroniCar para generic.svg
    generic_src = r"C:\Users\breno\.t3\userdata\providers\antigravity\ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32\config\skills\mecatronicar-identidade-visual\assets\logo.svg"
    generic_dest = os.path.join(BRANDS_DIR, "generic.svg")
    if os.path.exists(generic_src):
        shutil.copyfile(generic_src, generic_dest)
        print("  OK: generic.svg (MecatroniCar Oficial)")

if __name__ == "__main__":
    sync_official_logos()
    # Executa o gerador de modelos fotorrealistas
    build_script = os.path.join(os.path.dirname(__file__), "build_photorealistic_models.py")
    if os.path.exists(build_script):
        os.system(f"python \"{build_script}\"")
