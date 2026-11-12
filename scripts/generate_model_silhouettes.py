# -*- coding: utf-8 -*-
"""
Gerador de silhuetas vetoriais de perfil para os 100 modelos mais populares do Brasil
Categorias de carroceria com variações estilísticas detalhadas e aerodinâmicas.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "static", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def generate_svg_profile(body_type, model_name, brand_name, accent_color="#0284c7"):
    """
    Gera um SVG vetorial de perfil lateral limpo, moderno e de alta precisão.
    viewBox: 0 0 320 140
    """
    # Cores e estilos base
    body_fill = "#334155" # Slate-700
    glass_fill = "#94a3b8" # Slate-400
    wheel_rim = "#cbd5e1"
    tire_fill = "#0f172a"
    accent = accent_color

    # Geometrias base por tipo de carroceria
    if body_type == "pickup_double": # Toro, Oroch, Hilux, S10, Ranger, Frontier, Gladiator, Maverick
        cab_path = "M 32,96 L 42,92 C 48,90 54,80 58,74 L 84,72 L 110,42 C 114,38 122,36 135,36 L 210,36 C 218,36 224,42 226,48 L 226,62 L 286,62 C 292,62 296,66 296,72 L 298,90 C 298,94 294,96 290,96 Z"
        glass_path = "M 115,44 L 145,44 L 145,66 L 96,66 Z M 154,44 L 214,44 C 218,44 220,46 220,50 L 220,66 L 154,66 Z"
        w1_cx, w2_cx, w_r = 75, 252, 22
        ground_y = 100
        roof_rail = "<line x1='135' y1='33' x2='205' y2='33' stroke='#64748b' stroke-width='2.5' stroke-linecap='round'/>"
        bed_line = "<line x1='226' y1='62' x2='226' y2='90' stroke='#1e293b' stroke-width='2'/>"
    elif body_type == "pickup_compact": # Strada, Saveiro, Montana
        cab_path = "M 30,96 L 42,92 C 46,90 52,80 56,74 L 84,72 L 108,44 C 112,40 120,38 132,38 L 192,38 C 198,38 202,42 204,48 L 204,64 L 284,64 C 290,64 294,68 294,74 L 294,92 C 294,96 290,96 286,96 Z"
        glass_path = "M 112,46 L 145,46 L 145,68 L 94,68 Z M 152,46 L 194,46 C 197,46 199,48 199,52 L 199,68 L 152,68 Z"
        w1_cx, w2_cx, w_r = 74, 248, 20
        ground_y = 100
        roof_rail = "<line x1='130' y1='35' x2='188' y2='35' stroke='#64748b' stroke-width='2' stroke-linecap='round'/>"
        bed_line = "<line x1='204' y1='64' x2='204' y2='92' stroke='#1e293b' stroke-width='2'/>"
    elif body_type == "suv_robust": # Compass, Commander, SW4, RAV4, Tucson, Santa Fe, Wrangler, Bronco, Taos, Cherokee
        cab_path = "M 28,96 L 38,90 C 44,88 50,78 54,72 L 80,70 L 106,38 C 110,34 118,32 128,32 L 244,32 C 252,32 258,38 260,46 L 268,68 C 272,76 276,82 284,86 L 286,92 C 286,96 282,96 278,96 Z"
        glass_path = "M 112,40 L 150,40 L 150,65 L 94,65 Z M 158,40 L 210,40 L 210,65 L 158,65 Z M 218,40 L 246,40 C 250,40 254,44 256,48 L 260,65 L 218,65 Z"
        w1_cx, w2_cx, w_r = 75, 238, 22
        ground_y = 100
        roof_rail = "<line x1='125' y1='28' x2='240' y2='28' stroke='#64748b' stroke-width='3' stroke-linecap='round'/>"
        bed_line = ""
    elif body_type == "suv_compact": # Tracker, Creta, Nivus, T-Cross, Renegade, Kicks, Duster, Pulse, HR-V, EcoSport, Captur
        cab_path = "M 30,96 L 40,90 C 46,88 52,78 56,72 L 82,70 L 108,40 C 112,36 120,34 130,34 L 232,34 C 238,34 244,38 248,44 L 262,68 C 266,74 270,80 278,84 L 280,92 C 280,96 276,96 272,96 Z"
        glass_path = "M 114,42 L 152,42 L 152,65 L 96,65 Z M 160,42 L 208,42 L 208,65 L 160,65 Z M 216,42 L 234,42 C 238,42 242,46 244,50 L 254,65 L 216,65 Z"
        w1_cx, w2_cx, w_r = 74, 234, 21
        ground_y = 100
        roof_rail = "<line x1='130' y1='30' x2='228' y2='30' stroke='#64748b' stroke-width='2.5' stroke-linecap='round'/>"
        bed_line = ""
    elif body_type == "sedan": # Corolla, Civic, Sentra, Onix Plus, Cronos, Virtus, Voyage, Prisma, Cruze, City, Logan, Versa, Ka Sedan, Azera, Elantra, Focus Sedan, Fusion
        cab_path = "M 26,96 L 36,92 C 42,90 48,82 52,76 L 82,72 L 106,42 C 110,38 118,36 128,36 L 208,36 C 218,36 226,42 232,48 L 254,68 L 284,70 C 290,70 294,74 294,80 L 294,92 C 294,96 290,96 286,96 Z"
        glass_path = "M 112,44 L 155,44 L 155,67 L 96,67 Z M 163,44 L 206,44 C 212,44 218,48 222,54 L 236,67 L 163,67 Z"
        w1_cx, w2_cx, w_r = 75, 240, 20
        ground_y = 100
        roof_rail = ""
        bed_line = ""
    elif body_type == "hatch_subcompact": # Mobi, Up, Kwid
        cab_path = "M 34,96 L 44,92 C 50,90 56,80 60,74 L 84,72 L 106,38 C 110,34 116,32 126,32 L 204,32 C 210,32 216,36 218,42 L 230,76 C 232,82 236,88 244,90 L 244,94 C 244,96 240,96 236,96 Z"
        glass_path = "M 110,40 L 150,40 L 150,66 L 94,66 Z M 158,40 L 198,40 C 202,40 206,44 208,48 L 216,66 L 158,66 Z"
        w1_cx, w2_cx, w_r = 76, 198, 19
        ground_y = 100
        roof_rail = ""
        bed_line = ""
    elif body_type == "van_commercial": # Fiorino, Master, Kangoo, Partner, HR
        cab_path = "M 30,96 L 40,90 C 46,88 52,78 56,72 L 80,70 L 98,34 C 102,30 108,28 116,28 L 274,28 C 280,28 284,32 284,38 L 284,90 C 284,94 280,96 276,96 Z"
        glass_path = "M 104,36 L 148,36 L 148,65 L 88,65 Z"
        w1_cx, w2_cx, w_r = 75, 236, 21
        ground_y = 100
        roof_rail = ""
        bed_line = "<line x1='154' y1='28' x2='154' y2='92' stroke='#1e293b' stroke-width='2'/>"
    else: # hatch standard: Gol, Polo, Argo, Onix, HB20, Fox, Yaris, Sandero, March, Fit, Celta, Uno, Palio, Ka, Corsa, 208, i30
        cab_path = "M 28,96 L 38,92 C 44,90 50,80 54,74 L 80,72 L 104,40 C 108,36 116,34 126,34 L 212,34 C 218,34 224,38 228,44 L 246,72 C 248,76 252,82 260,86 L 262,92 C 262,96 258,96 254,96 Z"
        glass_path = "M 110,42 L 152,42 L 152,66 L 94,66 Z M 160,42 L 208,42 C 212,42 216,46 218,50 L 228,66 L 160,66 Z"
        w1_cx, w2_cx, w_r = 74, 224, 20
        ground_y = 100
        roof_rail = ""
        bed_line = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 135" width="100%" height="100%">
  <defs>
    <linearGradient id="body-grad-{model_name}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#475569"/>
      <stop offset="50%" stop-color="{body_fill}"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="glass-grad-{model_name}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#cbd5e1"/>
      <stop offset="100%" stop-color="{glass_fill}"/>
    </linearGradient>
    <filter id="shadow-{model_name}" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="4" stdDeviation="3" flood-color="#000000" flood-opacity="0.25"/>
    </filter>
  </defs>

  <!-- Sombra no Solo -->
  <ellipse cx="160" cy="116" rx="125" ry="7" fill="#000000" opacity="0.25"/>

  <!-- Grupo Carroceria com Sombra -->
  <g filter="url(#shadow-{model_name})">
    <!-- Carroceria Principal -->
    <path d="{cab_path}" fill="url(#body-grad-{model_name})" stroke="#0f172a" stroke-width="1.5" stroke-linejoin="round"/>
    
    <!-- Linhas de Caráter e Vinco Lateral -->
    <path d="M 54,74 Q 150,72 260,76" fill="none" stroke="{accent}" stroke-width="2" opacity="0.85"/>
    <path d="M 60,86 Q 160,85 250,88" fill="none" stroke="#1e293b" stroke-width="1.2" opacity="0.6"/>

    <!-- Vidros e Colunas -->
    <path d="{glass_path}" fill="url(#glass-grad-{model_name})" stroke="#1e293b" stroke-width="1.5" stroke-linejoin="round"/>

    <!-- Farol Dianteiro -->
    <path d="M 30,90 Q 36,86 46,86 L 44,92 Z" fill="#fef08a" stroke="#ca8a04" stroke-width="1"/>

    <!-- Lanterna Traseira -->
    <path d="M 280,82 Q 288,84 286,92 L 278,92 Z" fill="#ef4444" stroke="#991b1b" stroke-width="1"/>

    {roof_rail}
    {bed_line}
  </g>

  <!-- Roda Dianteira -->
  <g>
    <!-- Caixa de Roda Recorte -->
    <circle cx="{w1_cx}" cy="{ground_y}" r="{w_r + 2}" fill="none" stroke="#1e293b" stroke-width="3"/>
    <!-- Pneu -->
    <circle cx="{w1_cx}" cy="{ground_y}" r="{w_r}" fill="{tire_fill}"/>
    <!-- Roda de Liga Leve -->
    <circle cx="{w1_cx}" cy="{ground_y}" r="{w_r - 6}" fill="{wheel_rim}" stroke="#64748b" stroke-width="1"/>
    <!-- Raios da Roda -->
    <circle cx="{w1_cx}" cy="{ground_y}" r="4" fill="{accent}"/>
    <line x1="{w1_cx - 10}" y1="{ground_y}" x2="{w1_cx + 10}" y2="{ground_y}" stroke="#475569" stroke-width="2"/>
    <line x1="{w1_cx}" y1="{ground_y - 10}" x2="{w1_cx}" y2="{ground_y + 10}" stroke="#475569" stroke-width="2"/>
  </g>

  <!-- Roda Traseira -->
  <g>
    <!-- Caixa de Roda Recorte -->
    <circle cx="{w2_cx}" cy="{ground_y}" r="{w_r + 2}" fill="none" stroke="#1e293b" stroke-width="3"/>
    <!-- Pneu -->
    <circle cx="{w2_cx}" cy="{ground_y}" r="{w_r}" fill="{tire_fill}"/>
    <!-- Roda de Liga Leve -->
    <circle cx="{w2_cx}" cy="{ground_y}" r="{w_r - 6}" fill="{wheel_rim}" stroke="#64748b" stroke-width="1"/>
    <!-- Raios da Roda -->
    <circle cx="{w2_cx}" cy="{ground_y}" r="4" fill="{accent}"/>
    <line x1="{w2_cx - 10}" y1="{ground_y}" x2="{w2_cx + 10}" y2="{ground_y}" stroke="#475569" stroke-width="2"/>
    <line x1="{w2_cx}" y1="{ground_y - 10}" x2="{w2_cx}" y2="{ground_y + 10}" stroke="#475569" stroke-width="2"/>
  </g>

  <!-- Rótulo do Modelo (Metadado Sutil) -->
  <text x="160" y="130" font-family="'Segoe UI', -apple-system, sans-serif" font-size="9" font-weight="700" fill="#64748b" text-anchor="middle" letter-spacing="1">{brand_name.upper()} {model_name.replace('-', ' ').upper()}</text>
</svg>"""
    return svg

# Lista dos 100 modelos populares (10 marcas x 10 modelos)
MODELS_CATALOG = [
    # 1. Fiat
    ("fiat-strada", "Strada", "Fiat", "pickup_compact", "#f9cc01"),
    ("fiat-argo", "Argo", "Fiat", "hatch", "#f9cc01"),
    ("fiat-mobi", "Mobi", "Fiat", "hatch_subcompact", "#f9cc01"),
    ("fiat-toro", "Toro", "Fiat", "pickup_double", "#f9cc01"),
    ("fiat-cronos", "Cronos", "Fiat", "sedan", "#f9cc01"),
    ("fiat-pulse", "Pulse", "Fiat", "suv_compact", "#f9cc01"),
    ("fiat-fastback", "Fastback", "Fiat", "suv_compact", "#f9cc01"),
    ("fiat-fiorino", "Fiorino", "Fiat", "van_commercial", "#f9cc01"),
    ("fiat-uno", "Uno", "Fiat", "hatch", "#f9cc01"),
    ("fiat-palio", "Palio", "Fiat", "hatch", "#f9cc01"),

    # 2. Volkswagen
    ("vw-gol", "Gol", "Volkswagen", "hatch", "#0284c7"),
    ("vw-polo", "Polo", "Volkswagen", "hatch", "#0284c7"),
    ("vw-tcross", "T-Cross", "Volkswagen", "suv_compact", "#0284c7"),
    ("vw-nivus", "Nivus", "Volkswagen", "suv_compact", "#0284c7"),
    ("vw-saveiro", "Saveiro", "Volkswagen", "pickup_compact", "#0284c7"),
    ("vw-virtus", "Virtus", "Volkswagen", "sedan", "#0284c7"),
    ("vw-voyage", "Voyage", "Volkswagen", "sedan", "#0284c7"),
    ("vw-fox", "Fox", "Volkswagen", "hatch", "#0284c7"),
    ("vw-taos", "Taos", "Volkswagen", "suv_robust", "#0284c7"),
    ("vw-up", "Up", "Volkswagen", "hatch_subcompact", "#0284c7"),

    # 3. Chevrolet
    ("chevrolet-onix", "Onix", "Chevrolet", "hatch", "#eab308"),
    ("chevrolet-onix-plus", "Onix Plus", "Chevrolet", "sedan", "#eab308"),
    ("chevrolet-tracker", "Tracker", "Chevrolet", "suv_compact", "#eab308"),
    ("chevrolet-s10", "S10", "Chevrolet", "pickup_double", "#eab308"),
    ("chevrolet-spin", "Spin", "Chevrolet", "suv_compact", "#eab308"),
    ("chevrolet-montana", "Montana", "Chevrolet", "pickup_compact", "#eab308"),
    ("chevrolet-celta", "Celta", "Chevrolet", "hatch", "#eab308"),
    ("chevrolet-prisma", "Prisma", "Chevrolet", "sedan", "#eab308"),
    ("chevrolet-corsa", "Corsa", "Chevrolet", "hatch", "#eab308"),
    ("chevrolet-cruze", "Cruze", "Chevrolet", "sedan", "#eab308"),

    # 4. Toyota
    ("toyota-hilux", "Hilux", "Toyota", "pickup_double", "#ef4444"),
    ("toyota-corolla", "Corolla", "Toyota", "sedan", "#ef4444"),
    ("toyota-corolla-cross", "Corolla Cross", "Toyota", "suv_robust", "#ef4444"),
    ("toyota-yaris-hatch", "Yaris Hatch", "Toyota", "hatch", "#ef4444"),
    ("toyota-yaris-sedan", "Yaris Sedan", "Toyota", "sedan", "#ef4444"),
    ("toyota-etios", "Etios", "Toyota", "hatch", "#ef4444"),
    ("toyota-sw4", "SW4", "Toyota", "suv_robust", "#ef4444"),
    ("toyota-rav4", "RAV4", "Toyota", "suv_robust", "#ef4444"),
    ("toyota-bandeirante", "Bandeirante", "Toyota", "suv_robust", "#ef4444"),
    ("toyota-prius", "Prius", "Toyota", "sedan", "#ef4444"),

    # 5. Hyundai
    ("hyundai-hb20", "HB20", "Hyundai", "hatch", "#3b82f6"),
    ("hyundai-hb20s", "HB20S", "Hyundai", "sedan", "#3b82f6"),
    ("hyundai-creta", "Creta", "Hyundai", "suv_compact", "#3b82f6"),
    ("hyundai-tucson", "Tucson", "Hyundai", "suv_robust", "#3b82f6"),
    ("hyundai-santafe", "Santa Fe", "Hyundai", "suv_robust", "#3b82f6"),
    ("hyundai-i30", "i30", "Hyundai", "hatch", "#3b82f6"),
    ("hyundai-ix35", "ix35", "Hyundai", "suv_robust", "#3b82f6"),
    ("hyundai-hr", "HR", "Hyundai", "van_commercial", "#3b82f6"),
    ("hyundai-azera", "Azera", "Hyundai", "sedan", "#3b82f6"),
    ("hyundai-elantra", "Elantra", "Hyundai", "sedan", "#3b82f6"),

    # 6. Renault
    ("renault-kwid", "Kwid", "Renault", "hatch_subcompact", "#f59e0b"),
    ("renault-sandero", "Sandero", "Renault", "hatch", "#f59e0b"),
    ("renault-logan", "Logan", "Renault", "sedan", "#f59e0b"),
    ("renault-duster", "Duster", "Renault", "suv_compact", "#f59e0b"),
    ("renault-oroch", "Oroch", "Renault", "pickup_double", "#f59e0b"),
    ("renault-captur", "Captur", "Renault", "suv_compact", "#f59e0b"),
    ("renault-master", "Master", "Renault", "van_commercial", "#f59e0b"),
    ("renault-kangoo", "Kangoo", "Renault", "van_commercial", "#f59e0b"),
    ("renault-megane", "Megane", "Renault", "sedan", "#f59e0b"),
    ("renault-clio", "Clio", "Renault", "hatch", "#f59e0b"),

    # 7. Jeep
    ("jeep-renegade", "Renegade", "Jeep", "suv_compact", "#10b981"),
    ("jeep-compass", "Compass", "Jeep", "suv_robust", "#10b981"),
    ("jeep-commander", "Commander", "Jeep", "suv_robust", "#10b981"),
    ("jeep-cherokee", "Cherokee", "Jeep", "suv_robust", "#10b981"),
    ("jeep-grandcherokee", "Grand Cherokee", "Jeep", "suv_robust", "#10b981"),
    ("jeep-wrangler", "Wrangler", "Jeep", "suv_robust", "#10b981"),
    ("jeep-gladiator", "Gladiator", "Jeep", "pickup_double", "#10b981"),
    ("jeep-compass-4xe", "Compass 4xe", "Jeep", "suv_robust", "#10b981"),
    ("jeep-renegade-4xe", "Renegade 4xe", "Jeep", "suv_compact", "#10b981"),
    ("jeep-commander-blackhawk", "Commander Blackhawk", "Jeep", "suv_robust", "#10b981"),

    # 8. Nissan
    ("nissan-kicks", "Kicks", "Nissan", "suv_compact", "#e11d48"),
    ("nissan-versa", "Versa", "Nissan", "sedan", "#e11d48"),
    ("nissan-sentra", "Sentra", "Nissan", "sedan", "#e11d48"),
    ("nissan-frontier", "Frontier", "Nissan", "pickup_double", "#e11d48"),
    ("nissan-march", "March", "Nissan", "hatch", "#e11d48"),
    ("nissan-tiida", "Tiida", "Nissan", "hatch", "#e11d48"),
    ("nissan-livina", "Livina", "Nissan", "suv_compact", "#e11d48"),
    ("nissan-grandlivina", "Grand Livina", "Nissan", "suv_compact", "#e11d48"),
    ("nissan-xtrail", "X-Trail", "Nissan", "suv_robust", "#e11d48"),
    ("nissan-vdrive", "V-Drive", "Nissan", "sedan", "#e11d48"),

    # 9. Honda
    ("honda-civic", "Civic", "Honda", "sedan", "#dc2626"),
    ("honda-hrv", "HR-V", "Honda", "suv_compact", "#dc2626"),
    ("honda-city", "City", "Honda", "sedan", "#dc2626"),
    ("honda-fit", "Fit", "Honda", "hatch", "#dc2626"),
    ("honda-wrv", "WR-V", "Honda", "suv_compact", "#dc2626"),
    ("honda-crv", "CR-V", "Honda", "suv_robust", "#dc2626"),
    ("honda-accord", "Accord", "Honda", "sedan", "#dc2626"),
    ("honda-zrv", "ZR-V", "Honda", "suv_robust", "#dc2626"),
    ("honda-city-hatchback", "City Hatchback", "Honda", "hatch", "#dc2626"),
    ("honda-prelude", "Prelude", "Honda", "sedan", "#dc2626"),

    # 10. Ford
    ("ford-ka", "Ka", "Ford", "hatch", "#2563eb"),
    ("ford-ka-sedan", "Ka Sedan", "Ford", "sedan", "#2563eb"),
    ("ford-ecosport", "EcoSport", "Ford", "suv_compact", "#2563eb"),
    ("ford-ranger", "Ranger", "Ford", "pickup_double", "#2563eb"),
    ("ford-fiesta", "Fiesta", "Ford", "hatch", "#2563eb"),
    ("ford-focus", "Focus", "Ford", "hatch", "#2563eb"),
    ("ford-fusion", "Fusion", "Ford", "sedan", "#2563eb"),
    ("ford-territory", "Territory", "Ford", "suv_robust", "#2563eb"),
    ("ford-maverick", "Maverick", "Ford", "pickup_double", "#2563eb"),
    ("ford-bronco-sport", "Bronco Sport", "Ford", "suv_robust", "#2563eb"),

    # Silhuetas Genéricas por Categoria
    ("car-generic", "Veículo", "Oficina", "hatch", "#f9cc01"),
    ("hatch-generic", "Hatch", "Oficina", "hatch", "#f9cc01"),
    ("sedan-generic", "Sedan", "Oficina", "sedan", "#f9cc01"),
    ("suv-generic", "SUV", "Oficina", "suv_robust", "#f9cc01"),
    ("pickup-generic", "Picape", "Oficina", "pickup_double", "#f9cc01"),
    ("van-generic", "Utilitário", "Oficina", "van_commercial", "#f9cc01")
]

generated_count = 0
for file_key, model_name, brand_name, body_type, accent in MODELS_CATALOG:
    svg_content = generate_svg_profile(body_type, model_name, brand_name, accent)
    file_path = os.path.join(MODELS_DIR, f"{file_key}.svg")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg_content.strip())
    generated_count += 1

print(f"Total gerado com sucesso: {generated_count} silhuetas de modelos em {MODELS_DIR}")
