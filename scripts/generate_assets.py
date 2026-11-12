# -*- coding: utf-8 -*-
"""
Script de geração de assets visuais:
1. Logos das principais montadoras em SVG (/static/brands/)
2. Silhuetas de perfil dos 100 modelos mais populares no Brasil em SVG (/static/models/)
3. Silhuetas genéricas por tipo de carroceria (hatch, sedan, suv, pickup, van, generic)
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS_DIR = os.path.join(BASE_DIR, "static", "brands")
MODELS_DIR = os.path.join(BASE_DIR, "static", "models")

os.makedirs(BRANDS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# 1. Logos de Montadoras
BRANDS = {
    "fiat": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <rect width="100" height="100" rx="22" fill="#990000"/>
  <text x="50" y="62" font-family="'Arial Black', 'Trebuchet MS', sans-serif" font-size="28" font-weight="900" fill="#ffffff" text-anchor="middle" letter-spacing="2">FIAT</text>
  <line x1="22" y1="72" x2="78" y2="72" stroke="#f9cc01" stroke-width="3.5" stroke-linecap="round"/>
</svg>""",

    "chevrolet": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 70" width="100%" height="100%">
  <defs>
    <linearGradient id="chevy-gold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffd54f"/>
      <stop offset="50%" stop-color="#d4af37"/>
      <stop offset="100%" stop-color="#aa820a"/>
    </linearGradient>
  </defs>
  <polygon points="12,25 108,25 102,45 6,45" fill="url(#chevy-gold)" stroke="#111827" stroke-width="2.5"/>
  <polygon points="45,8 75,8 75,62 45,62" fill="url(#chevy-gold)" stroke="#111827" stroke-width="2.5"/>
  <polygon points="48,12 72,12 72,58 48,58" fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.6"/>
</svg>""",

    "volkswagen": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <circle cx="50" cy="50" r="46" fill="#001e50" stroke="#001e50" stroke-width="2"/>
  <circle cx="50" cy="50" r="41" fill="none" stroke="#ffffff" stroke-width="4.5"/>
  <path d="M26,32 L36,66 L44,46 L50,57 L56,46 L64,66 L74,32" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M38,32 L50,60 L62,32" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "toyota": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90" width="100%" height="100%">
  <ellipse cx="60" cy="45" rx="54" ry="38" fill="none" stroke="#eb0a1e" stroke-width="7"/>
  <ellipse cx="60" cy="38" rx="18" ry="28" fill="none" stroke="#eb0a1e" stroke-width="6"/>
  <ellipse cx="60" cy="30" rx="36" ry="14" fill="none" stroke="#eb0a1e" stroke-width="6"/>
</svg>""",

    "hyundai": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80" width="100%" height="100%">
  <ellipse cx="60" cy="40" rx="54" ry="34" fill="none" stroke="#002c6c" stroke-width="6"/>
  <path d="M38,62 C38,40 44,20 48,18 M72,62 C76,40 82,20 82,18 M42,40 C52,38 68,38 78,40" fill="none" stroke="#002c6c" stroke-width="7" stroke-linecap="round"/>
</svg>""",

    "renault": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 100" width="100%" height="100%">
  <polygon points="40,6 74,50 40,94 6,50" fill="none" stroke="#111827" stroke-width="8" stroke-linejoin="round"/>
  <polygon points="40,24 58,50 40,76 22,50" fill="none" stroke="#f9cc01" stroke-width="5" stroke-linejoin="round"/>
</svg>""",

    "jeep": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 50" width="100%" height="100%">
  <rect width="110" height="50" rx="10" fill="#1e392a"/>
  <text x="55" y="34" font-family="'Helvetica Neue', Arial, sans-serif" font-size="28" font-weight="900" fill="#ffffff" text-anchor="middle" letter-spacing="2">Jeep</text>
</svg>""",

    "nissan": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 90" width="100%" height="100%">
  <circle cx="55" cy="45" rx="40" ry="40" fill="none" stroke="#c3002f" stroke-width="7"/>
  <rect x="8" y="32" width="94" height="26" rx="4" fill="#111827" stroke="#c3002f" stroke-width="2"/>
  <text x="55" y=\"51\" font-family=\"'Arial Black', Impact, sans-serif\" font-size=\"16\" font-weight=\"900\" fill=\"#ffffff\" text-anchor=\"middle\" letter-spacing=\"2\">NISSAN</text>
</svg>""",

    "honda": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 90" width="100%" height="100%">
  <path d="M16,14 L84,14 C87,14 89,16 88,20 L76,78 C75,81 72,84 69,84 L31,84 C28,84 25,81 24,78 L12,20 C11,16 13,14 16,14 Z" fill="none" stroke="#cc0000" stroke-width="6" stroke-linejoin="round"/>
  <path d="M32,24 L36,74 M68,24 L64,74 M33,48 L67,48" fill="none" stroke="#cc0000" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "ford": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 75" width="100%" height="100%">
  <ellipse cx="65" cy="37.5" rx="60" ry="32" fill="#002c6c" stroke="#ffffff" stroke-width="3"/>
  <ellipse cx="65" cy="37.5" rx="54" ry="26" fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.7"/>
  <text x="65" y="47" font-family="'Brush Script MT', 'Segoe Script', cursive, sans-serif" font-size="34" font-style="italic" font-weight="bold" fill="#ffffff" text-anchor="middle">Ford</text>
</svg>""",

    "peugeot": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 100" width="100%" height="100%">
  <path d="M10,12 L80,12 L75,76 L45,96 L15,76 Z" fill="#111827" stroke="#0284c7" stroke-width="3"/>
  <text x="45" y="32" font-family="'Arial Black', sans-serif" font-size="10" font-weight="900" fill="#ffffff" text-anchor="middle" letter-spacing="1">PEUGEOT</text>
  <path d="M42,42 C50,40 55,48 52,56 C50,62 56,66 58,74 C54,76 46,74 44,70 C42,66 38,68 34,76 M46,50 C40,54 36,60 38,68" fill="none" stroke="#0284c7" stroke-width="4" stroke-linecap="round"/>
</svg>""",

    "citroen": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 90" width="100%" height="100%">
  <rect width="90" height="90" rx="16" fill="#8a1523"/>
  <polyline points="25,36 45,20 65,36" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  <polyline points="25,56 45,40 65,56" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "mitsubishi": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 90" width="100%" height="100%">
  <polygon points="50,8 65,34 50,60 35,34" fill="#e60012"/>
  <polygon points="35,34 50,60 25,60 10,34" fill="#e60012"/>
  <polygon points="65,34 90,34 75,60 50,60" fill="#e60012"/>
</svg>""",

    "chery": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 80" width="100%" height="100%">
  <ellipse cx="55" cy="40" rx="48" ry="30" fill="none" stroke="#b30000" stroke-width="5"/>
  <path d="M38,55 L55,22 L72,55 M44,45 L66,45" fill="none" stroke="#b30000" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "bmw": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <circle cx="50" cy="50" r="46" fill="#111827" stroke="#cbd5e1" stroke-width="4"/>
  <circle cx="50" cy="50" r="30" fill="#ffffff" stroke="#111827" stroke-width="2"/>
  <path d="M50,50 L50,20 A30,30 0 0,0 20,50 Z" fill="#0066b1"/>
  <path d="M50,50 L50,80 A30,30 0 0,0 80,50 Z" fill="#0066b1"/>
  <text x="50" y="17" font-family="Arial, sans-serif" font-size="10" font-weight="bold" fill="#ffffff" text-anchor="middle">BMW</text>
</svg>""",

    "mercedes": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <circle cx="50" cy="50" r="45" fill="none" stroke="#334155" stroke-width="5"/>
  <polygon points="50,50 48,10 50,7 52,10" fill="#334155"/>
  <polygon points="50,50 15,68 12,70 15,72" fill="#334155"/>
  <polygon points="50,50 85,68 88,70 85,72" fill="#334155"/>
  <circle cx="50" cy="50" r="4" fill="#334155"/>
</svg>""",

    "audi": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 60" width="100%" height="100%">
  <circle cx="32" cy="30" r="18" fill="none" stroke="#111827" stroke-width="4"/>
  <circle cx="56" cy="30" r="18" fill="none" stroke="#111827" stroke-width="4"/>
  <circle cx="80" cy="30" r="18" fill="none" stroke="#111827" stroke-width="4"/>
  <circle cx="104" cy="30" r="18" fill="none" stroke="#111827" stroke-width="4"/>
</svg>""",

    "kia": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 60" width="100%" height="100%">
  <rect width="110" height="60" rx="12" fill="#05141f"/>
  <path d="M22,44 L22,16 M22,30 L40,16 M28,26 L40,44 M48,16 L48,44 M58,44 L72,16 L86,44 M62,35 L82,35" fill="none" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "byd": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 65" width="100%" height="100%">
  <ellipse cx="55" cy="32.5" rx="50" ry="28" fill="none" stroke="#e2231a" stroke-width="4"/>
  <text x="55" y="42" font-family="'Helvetica Neue', Arial, sans-serif" font-size="24" font-weight="900" fill="#e2231a" text-anchor="middle" letter-spacing="4">BYD</text>
</svg>""",

    "generic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <polygon points="50,8 92,50 50,92 8,50" fill="#f9cc01" stroke="#111827" stroke-width="6" stroke-linejoin="round"/>
  <circle cx="50" cy="50" r="16" fill="#111827"/>
  <circle cx="50" cy="50" r="10" fill="#f9cc01"/>
</svg>"""
}

for name, svg in BRANDS.items():
    fp = os.path.join(BRANDS_DIR, f"{name}.svg")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(svg.strip())

print(f"Gerados {len(BRANDS)} logos de montadoras em {BRANDS_DIR}")
