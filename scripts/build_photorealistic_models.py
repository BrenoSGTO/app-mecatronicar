# -*- coding: utf-8 -*-
"""
Processador de Renders Automotivos Fotorrealistas para MecatroniCar:
1. Converte fotos de estúdio para recortes PNG/WebP com fundo transparente e sombra de contato suave.
2. Mapeia e gera os 106 arquivos SVG em static/models/ com vetor SVG + base64 WebP de alta definição.
"""

import os
import io
import base64
from PIL import Image
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "static", "models")
BRAIN_DIR = r"C:\Users\breno\.t3\userdata\providers\antigravity\ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32\antigravity-acp\brain\b1ba06f1-a442-4e66-b753-18871a4ee9ef"

os.makedirs(MODELS_DIR, exist_ok=True)

SOURCE_IMAGES = {
    "strada": os.path.join(BRAIN_DIR, "fiat_strada_render_1794521020423.jpg"),
    "toro": os.path.join(BRAIN_DIR, "fiat_toro_render_1794521581482.jpg"),
    "hilux": os.path.join(BRAIN_DIR, "toyota_hilux_render_1794521511018.jpg"),
    "corolla": os.path.join(BRAIN_DIR, "toyota_corolla_render_1794521394611.jpg"),
    "civic": os.path.join(BRAIN_DIR, "honda_civic_render_1794521624557.jpg"),
    "onix": os.path.join(BRAIN_DIR, "chevrolet_onix_render_1794521448881.jpg"),
    "gol": os.path.join(BRAIN_DIR, "vw_gol_render_1794521479026.jpg"),
    "hb20": os.path.join(BRAIN_DIR, "hyundai_hb20_render_1794521545356.jpg"),
    "renegade": os.path.join(BRAIN_DIR, "jeep_renegade_render_1794521421193.jpg"),
    "compass": os.path.join(BRAIN_DIR, "jeep_compass_render_1794521709413.jpg"),
    "tcross": os.path.join(BRAIN_DIR, "vw_tcross_render_1794521755674.jpg"),
    "fiorino": os.path.join(BRAIN_DIR, "fiat_fiorino_render_1794521666722_clean.jpg")
}

def clean_and_convert(img_path):
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    # Cor de fundo padrão (canto superior esquerdo)
    bg = arr[10, 10, :]
    dist = np.linalg.norm(arr - bg, axis=2)

    # Transparência suave
    alpha = np.clip((dist - 20.0) / 18.0 * 255.0, 0, 255).astype(np.uint8)

    # Sombra de solo suave sob os pneus (preserva contato com o solo)
    h, w = arr.shape[:2]
    ground_zone = (np.arange(h)[:, None] > int(h * 0.72)) & (dist < 110) & (np.mean(arr, axis=2) < 210)
    alpha[ground_zone] = np.clip(alpha[ground_zone] * 1.6, 0, 170).astype(np.uint8)

    rgba = np.dstack([arr.astype(np.uint8), alpha])
    out_img = Image.fromarray(rgba, "RGBA")
    bbox = out_img.getbbox()
    if bbox:
        out_img = out_img.crop((max(0, bbox[0]-4), max(0, bbox[1]-4), min(w, bbox[2]+4), min(h, bbox[3]+4)))

    out_img.thumbnail((640, 360), Image.Resampling.LANCZOS)
    
    # Salva em WebP em memória
    buf = io.BytesIO()
    out_img.save(buf, format="WEBP", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return out_img.width, out_img.height, b64

print("Processando imagens geradas de alta definição...")
PROCESSED_RENDERS = {}
for key, path in SOURCE_IMAGES.items():
    if os.path.exists(path):
        w, h, b64 = clean_and_convert(path)
        PROCESSED_RENDERS[key] = (w, h, b64)
        print(f"  OK: {key} ({w}x{h})")
    else:
        print(f"  AVISO: {path} não encontrado")

# Mapeamento completo dos 106 arquivos para as melhores referências reais
MODEL_MAP = {
    # Pickups compactas
    "fiat-strada": "strada",
    "vw-saveiro": "strada",
    "chevrolet-montana": "strada",
    "pickup-generic": "strada",

    # Pickups médias e esportivas
    "fiat-toro": "toro",
    "renault-oroch": "toro",
    "ford-maverick": "toro",

    # Pickups 4x4 pesadas
    "toyota-hilux": "hilux",
    "chevrolet-s10": "hilux",
    "ford-ranger": "hilux",
    "nissan-frontier": "hilux",
    "jeep-gladiator": "hilux",
    "toyota-bandeirante": "hilux",

    # Sedans médios/executivos
    "toyota-corolla": "corolla",
    "toyota-corolla-cross": "compass",
    "toyota-yaris-sedan": "corolla",
    "toyota-prius": "corolla",
    "sedan-generic": "corolla",
    "fiat-cronos": "corolla",
    "renault-logan": "corolla",
    "nissan-versa": "corolla",
    "nissan-vdrive": "corolla",
    "ford-ka-sedan": "corolla",

    # Sedans esportivos / premium
    "honda-civic": "civic",
    "honda-city": "civic",
    "honda-accord": "civic",
    "honda-prelude": "civic",
    "chevrolet-cruze": "civic",
    "ford-fusion": "civic",
    "hyundai-azera": "civic",
    "hyundai-elantra": "civic",
    "nissan-sentra": "civic",
    "vw-virtus": "civic",
    "vw-voyage": "civic",
    "renault-megane": "civic",
    "chevrolet-prisma": "civic",
    "chevrolet-onix-plus": "civic",

    # Hatches modernos
    "chevrolet-onix": "onix",
    "chevrolet-celta": "onix",
    "chevrolet-corsa": "onix",
    "fiat-argo": "onix",
    "fiat-pulse": "tcross",
    "fiat-fastback": "tcross",
    "car-generic": "onix",
    "hatch-generic": "onix",

    # Hatches populares clássicos
    "vw-gol": "gol",
    "vw-polo": "gol",
    "vw-fox": "gol",
    "vw-up": "gol",
    "fiat-uno": "gol",
    "fiat-mobi": "gol",
    "fiat-palio": "gol",
    "renault-kwid": "gol",
    "renault-sandero": "gol",
    "renault-clio": "gol",
    "ford-ka": "gol",
    "ford-fiesta": "gol",
    "ford-focus": "gol",
    "nissan-march": "gol",
    "nissan-tiida": "gol",
    "peugeot-208": "gol",
    "citroen-c3": "gol",

    # Hatches asiáticos elegantes
    "hyundai-hb20": "hb20",
    "hyundai-hb20s": "corolla",
    "hyundai-i30": "hb20",
    "honda-fit": "hb20",
    "honda-city-hatchback": "hb20",
    "toyota-etios": "hb20",
    "toyota-yaris-hatch": "hb20",

    # SUVs compactos e robustos (estilo Jeep)
    "jeep-renegade": "renegade",
    "jeep-renegade-4xe": "renegade",
    "jeep-wrangler": "renegade",

    # SUVs médios e premium
    "jeep-compass": "compass",
    "jeep-commander": "compass",
    "jeep-compass-4xe": "compass",
    "jeep-cherokee": "compass",
    "jeep-grandcherokee": "compass",
    "jeep-commander-blackhawk": "compass",
    "toyota-sw4": "compass",
    "toyota-rav4": "compass",
    "suv-generic": "compass",

    # SUVs urbanos crossover
    "vw-tcross": "tcross",
    "vw-nivus": "tcross",
    "vw-taos": "tcross",
    "chevrolet-tracker": "tcross",
    "chevrolet-spin": "tcross",
    "hyundai-creta": "tcross",
    "hyundai-tucson": "tcross",
    "hyundai-ix35": "tcross",
    "hyundai-santafe": "compass",
    "nissan-kicks": "tcross",
    "nissan-livina": "tcross",
    "nissan-grandlivina": "tcross",
    "nissan-xtrail": "tcross",
    "honda-hrv": "tcross",
    "honda-crv": "compass",
    "honda-wrv": "tcross",
    "honda-zrv": "tcross",
    "renault-duster": "tcross",
    "renault-captur": "tcross",
    "ford-ecosport": "tcross",
    "ford-territory": "tcross",
    "ford-bronco-sport": "renegade",

    # Furgões e Utilitários comerciais
    "fiat-fiorino": "fiorino",
    "hyundai-hr": "fiorino",
    "renault-master": "fiorino",
    "renault-kangoo": "fiorino",
    "peugeot-partner": "fiorino",
    "van-generic": "fiorino"
}

def create_svg(w, h, b64):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">
  <defs>
    <filter id="car-shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="8" stdDeviation="6" flood-color="#000000" flood-opacity="0.3"/>
    </filter>
  </defs>
  <ellipse cx="{w//2}" cy="{h-8}" rx="{int(w*0.42)}" ry="8" fill="#000000" opacity="0.25"/>
  <image href="data:image/webp;base64,{b64}" width="{w}" height="{h}" />
</svg>"""

count = 0
for model_key, render_key in MODEL_MAP.items():
    if render_key in PROCESSED_RENDERS:
        w, h, b64 = PROCESSED_RENDERS[render_key]
        svg_content = create_svg(w, h, b64)
        out_path = os.path.join(MODELS_DIR, f"{model_key}.svg")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        count += 1

print(f"\nSucesso! Gerados {count} modelos fotorrealistas em {MODELS_DIR}")
