# -*- coding: utf-8 -*-
"""
Gerador determinístico dos assets de veículos do MecatroniCar (repaginação v3).

Gera:
  static/models/<arquetipo>.svg   silhuetas laterais minimalistas (currentColor)
  static/models/*-generic.svg     aliases genéricos usados por identifyCar()
  static/brands/<marca>.svg       monogramas neutros das montadoras (currentColor)
  docs/assets-galeria.html        galeria estática/offline para revisão

Uso:
  python scripts/generate_vehicle_assets.py

Decisões de desenho
-------------------
* Silhuetas: em vez de ~100 desenhos individuais, um conjunto de arquétipos de
  carroceria desenhados a partir de medidas reais (comprimento, altura,
  entre-eixos, roda) em METROS e convertidos numa escala única
  (SCALE unidades/metro). Todas as silhuetas usam a mesma viewBox e a mesma
  linha de chão, então um hatch fica menor que uma picape, como na vida real.
  O mapeamento modelo -> arquétipo fica em static/car_catalog.js (campo
  ``shape`` de cada item de POPULAR_MODELS).
* Logos: logotipos registrados não são reproduzidos. Cada marca recebe um
  monograma (iniciais em tipografia do sistema) dentro de um círculo, todos
  no mesmo padrão. Veja docs/assets-galeria.html.
* Cor: tudo é desenhado com ``currentColor``. O elemento <svg> traz
  ``color="#71717a"`` (zinc-500) como padrão para quando o arquivo é usado via
  <img> (onde não há herança de cor): esse cinza tem contraste >= 3:1 tanto no
  tema claro quanto no escuro/TV. Para herdar a cor do tema, use o SVG inline
  com ``svg { color: inherit }`` ou como máscara CSS:
      .silhueta { background: currentColor;
                  mask: url(/static/models/hatch-medio.svg) center / contain no-repeat; }
"""

import math
import os
import re
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "static", "models")
BRANDS_DIR = os.path.join(ROOT, "static", "brands")
CATALOG_JS = os.path.join(ROOT, "static", "car_catalog.js")
GALLERY = os.path.join(ROOT, "docs", "assets-galeria.html")

DEFAULT_COLOR = "#71717a"  # zinc-500: legível em fundo claro e escuro

# ---------------------------------------------------------------------------
# Silhuetas
# ---------------------------------------------------------------------------
SCALE = 40.0          # unidades SVG por metro (1 un = 2,5 cm)
VB_W, VB_H = 240, 104  # viewBox comum a todas as silhuetas
GROUND = 102.0        # linha de chão (base dos pneus)
ARCH_GAP = 0.055      # folga entre pneu e caixa de roda (m)
RIM = 0.60            # raio do aro / raio do pneu
HUB = 0.22            # raio do cubo / raio do pneu

# Coordenadas em metros. x = 0 na traseira, o carro "anda" para a direita
# (frente em x = L); y = 0 no chão. Cada vértice é (x, y, raio_de_canto).
# ``body`` percorre o contorno da frente-baixo, por cima, até a traseira-baixo;
# a parte de baixo (caixas de roda e soleira) é gerada a partir de ``wheels``.
ARCHETYPES = {
    "hatch-compacto": {
        "label": "Hatch compacto",
        "dims": "3,65 x 1,50 m",
        "L": 3.65, "sill": 0.25,
        "wheels": [(0.58, 0.29), (2.98, 0.29)],
        "body": [
            (3.60, 0.24, .06), (3.65, 0.50, .16), (3.58, 0.72, .12),
            (2.70, 0.95, .10), (1.95, 1.47, .26), (0.52, 1.49, .26),
            (0.07, 1.16, .12), (0.00, 0.62, .10), (0.04, 0.25, .06),
        ],
        "windows": [
            [(2.58, 0.99, .04), (1.98, 1.40, .08), (1.52, 1.41, .05), (1.52, 0.99, .03)],
            [(1.44, 0.99, .03), (1.44, 1.41, .05), (0.66, 1.42, .10), (0.34, 1.10, .06), (0.42, 1.01, .03)],
        ],
    },
    "hatch-medio": {
        "label": "Hatch médio",
        "dims": "4,05 x 1,47 m",
        "L": 4.05, "sill": 0.25,
        "wheels": [(0.70, 0.315), (3.25, 0.315)],
        "body": [
            (4.00, 0.24, .06), (4.05, 0.50, .16), (3.97, 0.72, .12),
            (2.92, 0.96, .10), (2.06, 1.44, .28), (0.66, 1.47, .32),
            (0.10, 1.12, .12), (0.00, 0.62, .10), (0.04, 0.25, .06),
        ],
        "windows": [
            [(2.79, 1.00, .04), (2.10, 1.38, .08), (1.64, 1.39, .05), (1.64, 1.00, .03)],
            [(1.56, 1.00, .03), (1.56, 1.39, .05), (0.70, 1.40, .10), (0.36, 1.08, .06), (0.46, 1.01, .03)],
        ],
    },
    "sedan-compacto": {
        "label": "Sedan compacto",
        "dims": "4,45 x 1,47 m",
        "L": 4.45, "sill": 0.25,
        "wheels": [(0.98, 0.315), (3.58, 0.315)],
        "body": [
            (4.40, 0.24, .06), (4.45, 0.50, .16), (4.37, 0.72, .12),
            (3.25, 0.96, .10), (2.38, 1.44, .28), (1.38, 1.46, .30),
            (0.62, 1.04, .14), (0.06, 0.98, .10), (0.00, 0.60, .10),
            (0.05, 0.25, .06),
        ],
        "windows": [
            [(3.12, 1.00, .04), (2.42, 1.38, .08), (1.98, 1.39, .05), (1.98, 1.00, .03)],
            [(1.90, 1.00, .03), (1.90, 1.39, .05), (1.40, 1.39, .10), (0.94, 1.06, .05), (1.02, 1.01, .03)],
        ],
    },
    "sedan-medio": {
        "label": "Sedan médio",
        "dims": "4,65 x 1,45 m",
        "L": 4.65, "sill": 0.25,
        "wheels": [(1.00, 0.33), (3.70, 0.33)],
        "body": [
            (4.60, 0.24, .06), (4.65, 0.48, .16), (4.56, 0.70, .12),
            (3.40, 0.94, .10), (2.52, 1.42, .30), (1.48, 1.44, .34),
            (0.60, 1.03, .14), (0.04, 0.98, .10), (0.00, 0.60, .10),
            (0.05, 0.25, .06),
        ],
        "windows": [
            [(3.26, 0.98, .04), (2.56, 1.36, .08), (2.10, 1.37, .05), (2.10, 0.98, .03)],
            [(2.02, 0.98, .03), (2.02, 1.37, .05), (1.50, 1.37, .12), (0.92, 1.04, .05), (1.00, 0.99, .03)],
        ],
    },
    "suv-compacto": {
        "label": "SUV compacto",
        "dims": "4,25 x 1,62 m",
        "L": 4.25, "sill": 0.33,
        "wheels": [(0.76, 0.345), (3.36, 0.345)],
        "body": [
            (4.19, 0.30, .06), (4.25, 0.58, .16), (4.17, 0.84, .12),
            (3.14, 1.07, .10), (2.30, 1.58, .28), (0.62, 1.62, .30),
            (0.10, 1.32, .12), (0.00, 0.72, .10), (0.04, 0.33, .06),
        ],
        "windows": [
            [(3.00, 1.11, .04), (2.34, 1.52, .08), (1.84, 1.53, .05), (1.84, 1.11, .03)],
            [(1.76, 1.11, .03), (1.76, 1.53, .05), (0.66, 1.55, .10), (0.40, 1.24, .06), (0.50, 1.13, .03)],
        ],
    },
    "suv-medio": {
        "label": "SUV médio",
        "dims": "4,55 x 1,68 m",
        "L": 4.55, "sill": 0.34,
        "wheels": [(0.84, 0.36), (3.54, 0.36)],
        "body": [
            (4.49, 0.31, .06), (4.55, 0.60, .16), (4.46, 0.88, .12),
            (3.32, 1.10, .10), (2.42, 1.64, .30), (0.64, 1.68, .32),
            (0.10, 1.38, .12), (0.00, 0.74, .10), (0.04, 0.34, .06),
        ],
        "windows": [
            [(3.18, 1.14, .04), (2.46, 1.58, .08), (1.96, 1.59, .05), (1.96, 1.14, .03)],
            [(1.88, 1.14, .03), (1.88, 1.59, .05), (0.86, 1.61, .08), (0.88, 1.15, .03)],
            [(0.78, 1.15, .03), (0.78, 1.60, .05), (0.66, 1.61, .08), (0.38, 1.30, .06), (0.44, 1.17, .03)],
        ],
    },
    "suv-cupe": {
        "label": "SUV cupê",
        "dims": "4,35 x 1,53 m",
        "L": 4.35, "sill": 0.34,
        "wheels": [(0.80, 0.345), (3.40, 0.345)],
        "body": [
            (4.29, 0.31, .06), (4.35, 0.60, .16), (4.27, 0.86, .12),
            (3.22, 1.07, .10), (2.38, 1.51, .30), (1.36, 1.53, .40),
            (0.26, 1.24, .12), (0.02, 1.18, .08), (0.00, 0.72, .10),
            (0.05, 0.34, .06),
        ],
        "windows": [
            [(3.08, 1.11, .04), (2.42, 1.45, .08), (1.94, 1.46, .05), (1.94, 1.11, .03)],
            [(1.86, 1.11, .03), (1.86, 1.46, .05), (1.38, 1.46, .14), (0.66, 1.19, .05), (0.74, 1.12, .03)],
        ],
    },
    "suv-offroad": {
        "label": "SUV off-road",
        "dims": "4,15 x 1,85 m",
        "L": 4.15, "sill": 0.46,
        "wheels": [(0.78, 0.39), (3.20, 0.39)],
        "body": [
            (4.11, 0.44, .05), (4.15, 0.80, .08), (4.10, 1.12, .08),
            (3.06, 1.18, .06), (2.78, 1.82, .10), (0.18, 1.85, .14),
            (0.06, 1.74, .08), (0.06, 0.84, .06), (0.10, 0.46, .05),
        ],
        "windows": [
            [(2.92, 1.22, .03), (2.70, 1.72, .05), (2.00, 1.74, .05), (2.00, 1.22, .03)],
            [(1.92, 1.22, .03), (1.92, 1.74, .05), (0.82, 1.75, .05), (0.82, 1.22, .03)],
            [(0.74, 1.22, .03), (0.74, 1.75, .05), (0.24, 1.76, .05), (0.24, 1.22, .03)],
        ],
        # estepe pendurado na tampa traseira
        "extras": [[(0.04, 0.92, .04), (-0.10, 0.92, .12), (-0.10, 1.54, .12), (0.04, 1.54, .04)]],
    },
    "monovolume": {
        "label": "Monovolume",
        "dims": "4,40 x 1,68 m",
        "L": 4.40, "sill": 0.28,
        "wheels": [(0.84, 0.32), (3.46, 0.32)],
        "body": [
            (4.35, 0.26, .06), (4.40, 0.54, .16), (4.32, 0.78, .12),
            (3.50, 0.98, .10), (2.50, 1.64, .30), (0.40, 1.68, .26),
            (0.04, 1.34, .10), (0.00, 0.66, .10), (0.04, 0.28, .06),
        ],
        "windows": [
            [(3.34, 1.03, .04), (2.54, 1.58, .08), (2.06, 1.59, .05), (2.06, 1.03, .03)],
            [(1.98, 1.03, .03), (1.98, 1.59, .05), (1.04, 1.60, .05), (1.04, 1.04, .03)],
            [(0.96, 1.04, .03), (0.96, 1.60, .05), (0.44, 1.61, .10), (0.20, 1.30, .05), (0.24, 1.06, .03)],
        ],
    },
    "picape-pequena": {
        "label": "Picape pequena",
        "dims": "4,55 x 1,58 m",
        "L": 4.55, "sill": 0.30,
        "wheels": [(0.84, 0.33), (3.56, 0.33)],
        "body": [
            (4.50, 0.28, .06), (4.55, 0.56, .16), (4.47, 0.80, .12),
            (3.40, 1.02, .10), (2.56, 1.55, .26), (1.62, 1.58, .14),
            (1.56, 1.12, .04), (0.04, 1.10, .04), (0.00, 0.62, .08),
            (0.04, 0.30, .06),
        ],
        "windows": [
            [(3.26, 1.06, .04), (2.60, 1.49, .08), (2.14, 1.50, .05), (2.14, 1.06, .03)],
            [(2.06, 1.06, .03), (2.06, 1.50, .05), (1.70, 1.51, .08), (1.70, 1.08, .03)],
        ],
    },
    "picape-media": {
        "label": "Picape média",
        "dims": "5,30 x 1,82 m",
        "L": 5.30, "sill": 0.40,
        "wheels": [(1.12, 0.39), (4.22, 0.39)],
        "body": [
            (5.24, 0.38, .06), (5.30, 0.70, .14), (5.22, 1.06, .10),
            (4.12, 1.22, .10), (3.30, 1.79, .24), (1.92, 1.82, .14),
            (1.86, 1.28, .04), (0.04, 1.26, .04), (0.00, 0.74, .08),
            (0.04, 0.40, .06),
        ],
        "windows": [
            [(3.98, 1.26, .04), (3.34, 1.72, .08), (2.86, 1.73, .05), (2.86, 1.26, .03)],
            [(2.78, 1.26, .03), (2.78, 1.73, .05), (2.00, 1.74, .08), (2.00, 1.30, .03)],
        ],
    },
    "furgao-compacto": {
        "label": "Furgão compacto",
        "dims": "4,35 x 1,88 m",
        "L": 4.35, "sill": 0.27,
        "wheels": [(0.80, 0.31), (3.52, 0.31)],
        "body": [
            (4.30, 0.25, .06), (4.35, 0.52, .16), (4.27, 0.76, .12),
            (3.62, 0.98, .10), (2.86, 1.56, .22), (2.40, 1.62, .10),
            (2.24, 1.88, .08), (0.06, 1.88, .10), (0.00, 1.70, .06),
            (0.00, 0.62, .08), (0.04, 0.27, .06),
        ],
        "windows": [
            [(3.46, 1.03, .04), (2.88, 1.50, .08), (2.46, 1.51, .05), (2.46, 1.03, .03)],
        ],
    },
    "furgao-grande": {
        "label": "Furgão grande",
        "dims": "5,55 x 2,48 m",
        "L": 5.55, "sill": 0.42,
        "wheels": [(1.14, 0.36), (4.80, 0.36)],
        "body": [
            (5.50, 0.40, .06), (5.55, 0.74, .12), (5.44, 1.18, .14),
            (4.84, 1.38, .12), (4.24, 2.30, .30), (3.80, 2.48, .24),
            (0.10, 2.48, .12), (0.00, 2.30, .08), (0.00, 0.62, .08),
            (0.04, 0.42, .06),
        ],
        "windows": [
            [(4.70, 1.46, .04), (4.24, 2.18, .10), (3.70, 2.20, .05), (3.70, 1.46, .03)],
        ],
    },
    "caminhao-leve": {
        "label": "Caminhão leve (baú)",
        "dims": "5,00 x 2,35 m",
        "L": 5.00, "sill": 0.48,
        "wheels": [(1.10, 0.34), (4.24, 0.34)],
        "body": [
            (4.96, 0.46, .05), (5.00, 0.80, .08), (4.92, 1.94, .16),
            (4.70, 2.04, .14), (3.50, 2.04, .12), (3.46, 0.80, .04),
            (0.00, 0.80, .04), (0.00, 0.60, .04), (0.04, 0.48, .04),
        ],
        "windows": [
            [(4.84, 1.30, .04), (4.80, 1.88, .06), (4.12, 1.90, .05), (4.12, 1.30, .03)],
        ],
        # baú de carga separado da cabine
        "extras": [[(3.38, 0.86, .03), (3.38, 2.35, .06), (0.00, 2.35, .06), (0.00, 0.86, .03)]],
    },
}

# Aliases genéricos referenciados por identifyCar() e pelo index.html.
GENERIC_ALIASES = {
    "car-generic": "hatch-medio",
    "hatch-generic": "hatch-medio",
    "sedan-generic": "sedan-compacto",
    "suv-generic": "suv-compacto",
    "pickup-generic": "picape-media",
    "van-generic": "furgao-compacto",
}


def n(v):
    """Formata número com 1 casa decimal, sem zeros supérfluos."""
    s = f"{v:.1f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


class Frame:
    """Converte metros (origem traseira/chão) em coordenadas da viewBox."""

    def __init__(self, length):
        self.ox = (VB_W - length * SCALE) / 2.0

    def pt(self, x, y):
        return (self.ox + x * SCALE, GROUND - y * SCALE)


def _round_corner(p, v, nx, r):
    """Pontos de entrada/saída de um canto arredondado em v (unidades SVG)."""
    def towards(a, b, d):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        return (a[0] + dx / ln * d, a[1] + dy / ln * d)
    d = min(r, math.dist(p, v) / 2.0, math.dist(v, nx) / 2.0)
    return towards(v, p, d), towards(v, nx, d)


def rounded_polyline(pts, closed):
    """pts: [(X, Y, r)] em unidades SVG. Retorna comandos de path."""
    count = len(pts)
    idx = range(count) if closed else range(1, count - 1)
    if closed:
        first, _ = _round_corner(pts[-1][:2], pts[0][:2], pts[1][:2], pts[0][2])
    else:
        first = pts[0][:2]
    out = [f"M{n(first[0])} {n(first[1])}"]
    last = (n(first[0]), n(first[1]))

    def line_to(p):
        nonlocal last
        key = (n(p[0]), n(p[1]))
        if key != last:
            out.append(f"L{key[0]} {key[1]}")
        last = key

    for i in idx:
        p, v, nx = pts[i - 1][:2], pts[i][:2], pts[(i + 1) % count][:2]
        a, b = _round_corner(p, v, nx, pts[i][2])
        line_to(a)
        out.append(f"Q{n(v[0])} {n(v[1])} {n(b[0])} {n(b[1])}")
        last = (n(b[0]), n(b[1]))
    if closed:
        out.append("Z")
    else:
        line_to(pts[-1][:2])
    return "".join(out)


def circle_path(cx, cy, r):
    return (f"M{n(cx - r)} {n(cy)}a{n(r)} {n(r)} 0 1 0 {n(2 * r)} 0"
            f"a{n(r)} {n(r)} 0 1 0 {n(-2 * r)} 0Z")


def silhouette_svg(spec):
    f = Frame(spec["L"])
    sill = spec["sill"]
    wheels = sorted(spec["wheels"])  # da traseira para a frente

    # Caixas de roda: interseção do arco (raio pneu + folga) com a soleira.
    arches = []
    for wx, wr in wheels:
        ar = wr + ARCH_GAP
        dy = sill - wr
        dx = math.sqrt(max(ar * ar - dy * dy, 0.0))
        arches.append((wx - dx, wx + dx, ar, sill < wr))

    # Contorno: começa na borda dianteira da caixa de roda dianteira,
    # percorre o perfil de cima e volta pela parte de baixo.
    front = arches[-1]
    pts = [(*f.pt(front[1], sill), 0)]
    pts += [(*f.pt(x, y), r * SCALE) for x, y, r in spec["body"]]
    pts.append((*f.pt(arches[0][0], sill), 0))
    d = rounded_polyline(pts, closed=False)
    for i, (x0, x1, ar, large) in enumerate(arches):
        ex, ey = f.pt(x1, sill)
        d += f"A{n(ar * SCALE)} {n(ar * SCALE)} 0 {1 if large else 0} 1 {n(ex)} {n(ey)}"
        if i + 1 < len(arches):
            nxp = f.pt(arches[i + 1][0], sill)
            d += f"L{n(nxp[0])} {n(nxp[1])}"
    d += "Z"
    for win in spec["windows"]:
        d += rounded_polyline([(*f.pt(x, y), r * SCALE) for x, y, r in win], closed=True)
    for extra in spec.get("extras", []):
        d += rounded_polyline([(*f.pt(x, y), r * SCALE) for x, y, r in extra], closed=True)

    w = ""
    for wx, wr in wheels:
        cx, cy = f.pt(wx, wr)
        r = wr * SCALE
        w += circle_path(cx, cy, r) + circle_path(cx, cy, r * RIM) + circle_path(cx, cy, r * HUB)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" '
        f'color="{DEFAULT_COLOR}" fill="currentColor" fill-rule="evenodd">'
        f'<path d="{d}"/><path d="{w}"/></svg>\n'
    )


# ---------------------------------------------------------------------------
# Monogramas das marcas
# ---------------------------------------------------------------------------
# Logotipos registrados não são reproduzidos (desenho impreciso de marca
# registrada fica pior que nenhum). Usamos iniciais em tipografia neutra.
BRAND_MONOGRAMS = {
    "fiat": "FI", "volkswagen": "VW", "chevrolet": "CH", "toyota": "TO",
    "hyundai": "HY", "renault": "RE", "jeep": "JE", "nissan": "NI",
    "honda": "HO", "ford": "FO", "peugeot": "PE", "citroen": "CI",
    "mitsubishi": "MI", "chery": "CC", "bmw": "BMW", "mercedes": "MB",
    "audi": "AU", "kia": "KIA", "byd": "BYD",
}
FONT = "'Segoe UI Variable Display','Segoe UI',system-ui,sans-serif"


def brand_svg(text):
    size = 26 if len(text) <= 2 else 20
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'color="{DEFAULT_COLOR}">'
        '<circle cx="32" cy="32" r="29.5" fill="none" stroke="currentColor" stroke-width="3"/>'
        f'<text x="32" y="32" dy=".35em" text-anchor="middle" fill="currentColor" '
        f'font-family="{FONT}" font-size="{size}" font-weight="600" '
        f'letter-spacing=".5">{escape(text)}</text></svg>\n'
    )


def generic_brand_svg():
    # Marca não identificada: mesmo círculo com um pictograma de carro (frente).
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'color="{DEFAULT_COLOR}">'
        '<circle cx="32" cy="32" r="29.5" fill="none" stroke="currentColor" stroke-width="3"/>'
        '<path fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" '
        'stroke-linecap="round" d="M19 37v-5l4-9h18l4 9v5zM19 37v4h5v-4M40 37v4h5v-4M23 31h18"/>'
        '</svg>\n'
    )


# ---------------------------------------------------------------------------
# Catálogo (lido de static/car_catalog.js, fonte única do mapeamento)
# ---------------------------------------------------------------------------
MODEL_RE = re.compile(
    r"\{\s*brand:\s*'([^']+)',\s*key:\s*'([^']+)',\s*name:\s*'([^']+)',"
    r"\s*body:\s*'([^']+)',\s*shape:\s*'([^']+)'"
)
BRAND_RE = re.compile(r"^\s*(\w+):\s*\{\s*name:\s*'([^']+)',\s*logo:", re.M)


def read_catalog():
    with open(CATALOG_JS, encoding="utf-8") as fh:
        js = fh.read()
    models = [dict(zip(("brand", "key", "name", "body", "shape"), m))
              for m in MODEL_RE.findall(js)]
    brands = dict(BRAND_RE.findall(js))
    return models, brands


# ---------------------------------------------------------------------------
# Galeria
# ---------------------------------------------------------------------------
def gallery_html(silhouettes, brand_svgs, models, brand_names):
    def inline(svg):
        return svg.strip()

    by_shape = {}
    for m in models:
        by_shape.setdefault(m["shape"], []).append(
            f'{brand_names.get(m["brand"], m["brand"])} {m["name"]}')

    def silhouette_cards():
        cards = []
        for key, spec in ARCHETYPES.items():
            used = ", ".join(sorted(by_shape.get(key, []))) or "(só genéricos)"
            aliases = ", ".join(a for a, t in GENERIC_ALIASES.items() if t == key)
            cards.append(
                f'<figure class="card"><div class="art">{inline(silhouettes[key])}</div>'
                f'<figcaption><b>{escape(spec["label"])}</b> <code>{key}.svg</code>'
                f'<span class="dim">{escape(spec["dims"])}'
                f'{" · alias: " + escape(aliases) if aliases else ""}</span>'
                f'<span class="uses">{escape(used)}</span></figcaption></figure>')
        return "\n".join(cards)

    def brand_cards():
        cards = []
        for key, svg in brand_svgs.items():
            cards.append(
                f'<figure class="logo"><div class="art">{inline(svg)}</div>'
                f'<figcaption>{escape(brand_names.get(key, key))}<code>{key}.svg</code>'
                f'</figcaption></figure>')
        return "\n".join(cards)

    lineup = "".join(
        f'<div class="lineup-item" title="{escape(ARCHETYPES[k]["label"])}">{inline(silhouettes[k])}</div>'
        for k in ARCHETYPES)

    def section(theme):
        title = "Tema claro" if theme == "light" else "Tema escuro / TV"
        return f"""
<section class="theme {theme}">
  <h2>{title}</h2>
  <h3>Escala comum (mesma viewBox e linha de chão)</h3>
  <div class="lineup">{lineup}</div>
  <h3>Silhuetas por arquétipo</h3>
  <div class="grid">{silhouette_cards()}</div>
  <h3>Montadoras (monogramas)</h3>
  <div class="logos">{brand_cards()}</div>
</section>"""

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galeria de assets de veículos</title>
<!-- Gerado por scripts/generate_vehicle_assets.py. Não editar à mão. -->
<style>
  :root {{ font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif; font-size: 14px; }}
  body {{ margin: 0; background: #f4f4f5; color: #18181b; }}
  header {{ padding: 24px 32px 8px; }}
  header h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  header p {{ margin: 4px 0; color: #52525b; max-width: 960px; line-height: 1.5; }}
  code {{ font-family: Consolas, ui-monospace, monospace; font-size: 12px; }}
  .theme {{ padding: 16px 32px 32px; }}
  .theme h2 {{ font-size: 16px; font-weight: 600; margin: 8px 0 12px; }}
  .theme h3 {{ font-size: 13px; font-weight: 500; margin: 24px 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .light {{ --bg: #ffffff; --surface: #ffffff; --border: #e4e4e7; --fg: #3f3f46; --muted: #71717a; background: #fafafa; color: #18181b; }}
  .dark  {{ --bg: #09090b; --surface: #18181b; --border: #27272a; --fg: #d4d4d8; --muted: #a1a1aa; background: #09090b; color: #fafafa; }}
  svg {{ color: inherit; display: block; width: 100%; height: auto; }}
  .art {{ color: var(--fg); }}
  .lineup {{ display: flex; align-items: flex-end; gap: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 8px 0; }}
  .lineup-item {{ flex: 1 1 0; min-width: 0; color: var(--fg); border-bottom: 1px solid var(--muted); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }}
  .card {{ margin: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }}
  .card .art {{ padding: 4px 8px; }}
  figcaption {{ display: flex; flex-direction: column; gap: 2px; margin-top: 8px; font-size: 13px; }}
  figcaption code {{ color: var(--muted); }}
  .dim {{ color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }}
  .uses {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
  .logos {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 12px; }}
  .logo {{ margin: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px; text-align: center; }}
  .logo .art {{ width: 48px; margin: 0 auto; }}
  .logo figcaption {{ align-items: center; }}
</style>
</head>
<body>
<header>
  <h1>Galeria de assets de veículos</h1>
  <p>Silhuetas laterais em {len(ARCHETYPES)} arquétipos de carroceria, desenhadas a partir de medidas reais na
  mesma escala ({int(SCALE)} unidades por metro, viewBox <code>0 0 {VB_W} {VB_H}</code>, chão em y={int(GROUND)}).
  Os {len(models)} modelos do catálogo apontam para um arquétipo pelo campo <code>shape</code> em
  <code>static/car_catalog.js</code>.</p>
  <p>Logos: monogramas neutros (sem reproduzir marcas registradas). Tudo em <code>currentColor</code>;
  quando usado via <code>&lt;img&gt;</code> a cor padrão é <code>{DEFAULT_COLOR}</code>.</p>
</header>
{section("light")}
{section("dark")}
</body>
</html>
"""


# ---------------------------------------------------------------------------
def write(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(BRANDS_DIR, exist_ok=True)
    models, brand_names = read_catalog()

    # Silhuetas
    silhouettes = {k: silhouette_svg(spec) for k, spec in ARCHETYPES.items()}
    wanted = dict(silhouettes)
    for alias, target in GENERIC_ALIASES.items():
        wanted[alias] = silhouettes[target]
    missing = sorted({m["shape"] for m in models} - set(wanted))
    if missing:
        raise SystemExit(f"car_catalog.js usa arquétipos inexistentes: {missing}")
    for name in os.listdir(MODELS_DIR):
        if name.endswith(".svg") and name[:-4] not in wanted:
            os.remove(os.path.join(MODELS_DIR, name))
    for key, svg in wanted.items():
        write(os.path.join(MODELS_DIR, f"{key}.svg"), svg)

    # Marcas
    brand_svgs = {k: brand_svg(t) for k, t in BRAND_MONOGRAMS.items()}
    brand_svgs["generic"] = generic_brand_svg()
    for name in os.listdir(BRANDS_DIR):
        if name.endswith(".svg") and name[:-4] not in brand_svgs:
            os.remove(os.path.join(BRANDS_DIR, name))
    for key, svg in brand_svgs.items():
        write(os.path.join(BRANDS_DIR, f"{key}.svg"), svg)

    write(GALLERY, gallery_html(silhouettes, brand_svgs, models, brand_names))
    print(f"{len(wanted)} silhuetas, {len(brand_svgs)} logos, galeria em docs/assets-galeria.html")


if __name__ == "__main__":
    main()
