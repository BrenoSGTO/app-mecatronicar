# -*- coding: utf-8 -*-
"""
Monta static/vehicle_catalog.js (window.VEHICLE_CATALOG) a partir do JSON bruto da
Tabela FIPE baixado por scripts/fetch_fipe_catalog.py.

O que sai para cada marca:
  k  chave (nome do arquivo do logo em static/brands/)
  n  nome exibido
  l  arquivo do logo
  a  apelidos para reconhecer a marca num texto livre ("vw", "gm"...)
  m  modelos: [nome, silhueta, {motor: [anos, combustíveis]}]
       nome    "Strada" (sem versão/acabamento: "Strada Working 1.4 CS" vira "Strada")
       motor   litragem "1.4" ("Elétrico" ou "" quando a FIPE não informa)
       anos    faixas de ano-modelo "1998-2013,2016"
       comb    códigos FIPE: 1 gasolina, 2 álcool, 3 diesel, 4 elétrico, 5 flex, 6 híbrido, 7 GNV

Uso:
    python scripts/build_vehicle_catalog.py fipe_raw.json
"""
import datetime
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vehicle_brands import FIPE_BRANDS, logo_file  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "vehicle_catalog.js")

# Ordem das marcas na lista (as mais comuns na oficina primeiro; o resto em ordem alfabética).
POPULAR = [
    "volkswagen", "fiat", "chevrolet", "ford", "toyota", "hyundai", "renault", "honda", "jeep",
    "nissan", "peugeot", "citroen", "mitsubishi", "kia", "chery", "byd", "gwm", "mercedes-benz",
    "bmw", "audi", "ram", "land-rover", "volvo", "suzuki", "jac",
]

# Nomes de modelo com mais de uma palavra (minúsculas, como aparecem no início do texto da FIPE).
# valor = nome exibido
MULTI = {
    "grand siena": "Grand Siena", "grand livina": "Grand Livina", "grand cherokee": "Grand Cherokee",
    "grand vitara": "Grand Vitara", "grand caravan": "Grand Caravan", "grand c4": "Grand C4 Picasso",
    "grand scenic": "Grand Scénic", "grand santa": "Grand Santa Fe", "grand i10": "Grand i10",
    "corolla cross": "Corolla Cross", "yaris cross": "Yaris Cross", "santa fe": "Santa Fe",
    "palio week.": "Palio Weekend", "palio weekend": "Palio Weekend", "palio adv": "Palio Weekend",
    "uno mille": "Uno Mille", "new beetle": "New Beetle", "space cross": "SpaceCross",
    "range rover": "Range Rover", "discovery sport": "Discovery Sport", "outlander sport": "Outlander Sport",
    "pajero sport": "Pajero Sport", "pajero full": "Pajero Full", "pajero tr4": "Pajero TR4",
    "pajero dakar": "Pajero Dakar", "pajero io": "Pajero iO", "eclipse cross": "Eclipse Cross",
    "l200 triton": "L200 Triton", "captiva sport": "Captiva", "onix plus": "Onix Plus",
    "onix sedan": "Onix Plus", "city hatchback": "City Hatchback", "city hatch": "City Hatchback",
    "yaris sedan": "Yaris Sedan", "polo sedan": "Polo Sedan", "fiesta sedan": "Fiesta Sedan",
    "focus sedan": "Focus Sedan", "ka sedan": "Ka Sedan", "ka+ sedan": "Ka Sedan", "civic si": "Civic",
    "c4 cactus": "C4 Cactus", "c4 lounge": "C4 Lounge", "c4 picasso": "C4 Picasso", "c4 pallas": "C4 Pallas",
    "c3 aircross": "C3 Aircross", "c3 picasso": "C3 Picasso", "aircross": "Aircross",
    "bronco sport": "Bronco Sport", "ranger raptor": "Ranger", "mustang mach-e": "Mustang Mach-E",
    "série 3": "Série 3", "serie 3": "Série 3", "classe a": "Classe A", "classe c": "Classe C",
    "duster oroch": "Oroch", "sandero stepway": "Sandero", "logan expression": "Logan",
    "kangoo express": "Kangoo", "master furgão": "Master", "hilux sw4": "SW4", "hilux cd": "Hilux",
    "s10 pick-up": "S10", "s10 cabine": "S10", "rav 4": "RAV4", "cr-v": "CR-V", "hr-v": "HR-V",
    "wr-v": "WR-V", "zr-v": "ZR-V", "x-trail": "X-Trail", "t-cross": "T-Cross", "up!": "up!",
    "gol (novo)": "Gol", "e-tron": "e-tron", "rs q3": "RS Q3", "rs q8": "RS Q8", "id.4": "ID.4",
    "nova saveiro": "Saveiro", "nova strada": "Strada", "novo uno": "Uno", "fiat 500": "500",
    "dolphin mini": "Dolphin Mini", "seal u": "Seal U", "song plus": "Song Plus", "song pro": "Song Pro",
    "haval h6": "Haval H6", "ora 03": "Ora 03", "tiggo 2": "Tiggo 2", "tiggo 3x": "Tiggo 3X",
    "tiggo 4": "Tiggo 4", "tiggo 5x": "Tiggo 5X", "tiggo 7": "Tiggo 7", "tiggo 8": "Tiggo 8",
    "land cruiser": "Land Cruiser", "santa fé": "Santa Fe", "grand saveiro": "Saveiro",
    "grand carnival": "Carnival", "range r": "Range Rover", "new range": "Range Rover",
    "range r evo": "Range Rover Evoque", "range rover evoque": "Range Rover Evoque",
    "range r velar": "Range Rover Velar", "range rover velar": "Range Rover Velar",
    "range r sport": "Range Rover Sport", "range rover sport": "Range Rover Sport",
    "disc sp": "Discovery Sport", "discov sp": "Discovery Sport", "palio week": "Palio Weekend",
    "id 4": "ID.4", "atto 2": "Atto 2", "atto 8": "Atto 8", "yuan plus": "Yuan Plus", "yuan pro": "Yuan Pro",
    "sealion 7": "Sealion 7", "chevy 500": "Chevy 500", "classe a": "Classe A",
    "bongo k-2500": "Bongo", "bongo k2500": "Bongo", "pick-up": "Pick-up",
}

# Apelidos/correções do primeiro token (minúsculas) -> nome exibido.
RENAME = {
    "crossfox": "CrossFox", "spacefox": "SpaceFox", "ecosport": "EcoSport", "hb20": "HB20", "hb20s": "HB20S",
    "hb20x": "HB20X", "s10": "S10", "sw4": "SW4", "rav4": "RAV4", "l200": "L200", "ix35": "ix35",
    "i30": "i30", "cr-v": "CR-V", "hr-v": "HR-V", "wr-v": "WR-V", "t-cross": "T-Cross", "up!": "up!",
    "up": "up!", "ka+": "Ka+", "c3": "C3", "c4": "C4", "c5": "C5", "ds3": "DS3", "ds4": "DS4", "ds5": "DS5",
    "hr": "HR", "h100": "H100", "doblo": "Doblò", "fiorino": "Fiorino", "mobi": "Mobi",
    "band": "Bandeirante", "def": "Defender", "defe": "Defender", "disc": "Discovery",
    "discov": "Discovery", "discovery3": "Discovery", "discovery4": "Discovery", "freelander2": "Freelander",
    "sprin": "Sprinter", "ss10": "S10", "chevy": "Chevy 500", "range": "Range Rover",
    "ducato-8": "Ducato", "ducato-10": "Ducato", "ducato-15": "Ducato", "i30cw": "i30", "rio": "Rio",
    "joy": "Joy", "tan": "Tan",
    "id.4": "ID.4", "e-tron": "e-tron", "x1": "X1", "x3": "X3", "x5": "X5", "x6": "X6",
}

# Silhueta (static/models/<forma>.svg) por modelo conhecido.  chave = nome em minúsculas.
SHAPES = {
    # Fiat
    "strada": "picape-pequena", "toro": "picape-media", "argo": "hatch-medio", "mobi": "hatch-compacto",
    "uno": "hatch-compacto", "uno mille": "hatch-compacto", "palio": "hatch-compacto", "siena": "sedan-compacto",
    "grand siena": "sedan-compacto", "cronos": "sedan-compacto", "pulse": "suv-compacto", "fastback": "suv-cupe",
    "fiorino": "furgao-compacto", "doblò": "monovolume", "ducato": "furgao-grande", "punto": "hatch-medio",
    "bravo": "hatch-medio", "linea": "sedan-medio", "idea": "monovolume", "stilo": "hatch-medio",
    "palio weekend": "monovolume", "freemont": "suv-medio", "500": "hatch-compacto", "marea": "sedan-medio",
    "tempra": "sedan-medio", "tipo": "hatch-medio", "brava": "hatch-medio", "147": "hatch-compacto",
    "elba": "monovolume", "prêmio": "sedan-compacto", "premio": "sedan-compacto", "titano": "picape-media",
    "scudo": "furgao-compacto", "600": "suv-compacto", "500e": "hatch-compacto",
    # Volkswagen
    "gol": "hatch-medio", "polo": "hatch-medio", "polo sedan": "sedan-compacto", "t-cross": "suv-compacto",
    "nivus": "suv-cupe", "saveiro": "picape-pequena", "virtus": "sedan-compacto", "voyage": "sedan-compacto",
    "fox": "hatch-medio", "crossfox": "hatch-medio", "spacefox": "monovolume", "taos": "suv-medio",
    "up!": "hatch-compacto", "tiguan": "suv-medio", "amarok": "picape-media", "jetta": "sedan-medio",
    "golf": "hatch-medio", "passat": "sedan-medio", "kombi": "furgao-compacto", "parati": "monovolume",
    "santana": "sedan-medio", "quantum": "monovolume", "fusca": "hatch-compacto", "brasilia": "hatch-compacto",
    "logus": "sedan-compacto", "pointer": "hatch-medio", "bora": "sedan-medio", "touareg": "suv-medio",
    "new beetle": "hatch-compacto", "fusca (novo)": "hatch-compacto", "spacecross": "monovolume",
    "tera": "suv-compacto", "id.4": "suv-medio", "id.buzz": "furgao-compacto", "crafter": "furgao-grande",
    "delivery": "caminhao-leve", "apollo": "sedan-compacto", "variant": "monovolume",
    # Chevrolet
    "onix": "hatch-medio", "onix plus": "sedan-compacto", "tracker": "suv-compacto", "s10": "picape-media",
    "spin": "monovolume", "montana": "picape-pequena", "celta": "hatch-compacto", "prisma": "sedan-compacto",
    "corsa": "hatch-compacto", "cruze": "sedan-medio", "cobalt": "sedan-compacto", "classic": "sedan-compacto",
    "agile": "hatch-medio", "astra": "hatch-medio", "vectra": "sedan-medio", "meriva": "monovolume",
    "zafira": "monovolume", "captiva": "suv-medio", "equinox": "suv-medio", "trailblazer": "suv-medio",
    "blazer": "suv-medio", "kadett": "hatch-medio", "monza": "sedan-medio", "omega": "sedan-medio",
    "chevette": "hatch-compacto", "opala": "sedan-medio", "d20": "picape-media", "silverado": "picape-media",
    "sonic": "hatch-medio", "camaro": "sedan-medio", "spark": "hatch-compacto", "joy": "hatch-medio",
    "bolt": "hatch-medio", "ipanema": "monovolume", "tigra": "hatch-compacto", "calibra": "sedan-medio",
    "s10 blazer": "suv-medio", "a-20": "picape-media", "c-20": "picape-media", "d-20": "picape-media",
    "veraneio": "suv-offroad", "suprema": "monovolume", "spin activ": "monovolume",
    # Toyota
    "hilux": "picape-media", "corolla": "sedan-medio", "corolla cross": "suv-medio", "yaris": "hatch-medio",
    "yaris sedan": "sedan-compacto", "etios": "hatch-medio", "sw4": "suv-medio", "rav4": "suv-medio",
    "bandeirante": "suv-offroad", "prius": "sedan-medio", "camry": "sedan-medio", "fielder": "monovolume",
    "land cruiser": "suv-offroad", "yaris cross": "suv-compacto",
    # Hyundai
    "hb20": "hatch-medio", "hb20s": "sedan-compacto", "hb20x": "hatch-medio", "creta": "suv-compacto",
    "tucson": "suv-medio", "santa fe": "suv-medio", "i30": "hatch-medio", "ix35": "suv-medio",
    "hr": "caminhao-leve", "azera": "sedan-medio", "elantra": "sedan-medio", "veloster": "hatch-medio",
    "vera cruz": "suv-medio", "h1": "furgao-compacto", "h100": "furgao-compacto", "sonata": "sedan-medio",
    "accent": "sedan-compacto", "kona": "suv-compacto", "palisade": "suv-medio",
    # Renault
    "kwid": "hatch-compacto", "sandero": "hatch-medio", "logan": "sedan-compacto", "duster": "suv-compacto",
    "oroch": "picape-pequena", "captur": "suv-compacto", "master": "furgao-grande", "kangoo": "furgao-compacto",
    "megane": "sedan-medio", "mégane": "sedan-medio", "clio": "hatch-compacto", "symbol": "sedan-compacto",
    "scenic": "monovolume", "scénic": "monovolume", "fluence": "sedan-medio", "kardian": "suv-compacto",
    "koleos": "suv-medio", "twingo": "hatch-compacto", "zoe": "hatch-compacto", "kwid e-tech": "hatch-compacto",
    "trafic": "furgao-grande", "19": "sedan-medio", "21": "sedan-medio", "laguna": "sedan-medio",
    # Jeep
    "renegade": "suv-compacto", "compass": "suv-medio", "commander": "suv-medio", "cherokee": "suv-medio",
    "grand cherokee": "suv-medio", "wrangler": "suv-offroad", "gladiator": "picape-media",
    # Nissan
    "kicks": "suv-compacto", "versa": "sedan-compacto", "sentra": "sedan-medio", "frontier": "picape-media",
    "march": "hatch-compacto", "tiida": "hatch-medio", "livina": "monovolume", "grand livina": "monovolume",
    "x-trail": "suv-medio", "pathfinder": "suv-medio", "leaf": "hatch-medio", "murano": "suv-medio",
    # Honda
    "civic": "sedan-medio", "hr-v": "suv-compacto", "city": "sedan-compacto", "fit": "hatch-medio",
    "wr-v": "suv-compacto", "cr-v": "suv-medio", "accord": "sedan-medio", "zr-v": "suv-medio",
    "city hatchback": "hatch-medio",
    # Ford
    "ka": "hatch-compacto", "ka sedan": "sedan-compacto", "ka+": "sedan-compacto", "ecosport": "suv-compacto",
    "ranger": "picape-media", "fiesta": "hatch-medio", "fiesta sedan": "sedan-compacto", "focus": "hatch-medio",
    "focus sedan": "sedan-medio", "fusion": "sedan-medio", "territory": "suv-medio", "maverick": "picape-media",
    "bronco sport": "suv-medio", "bronco": "suv-offroad", "edge": "suv-medio", "escort": "hatch-medio",
    "verona": "sedan-compacto", "corcel": "sedan-compacto", "del rey": "sedan-compacto", "belina": "monovolume",
    "pampa": "picape-pequena", "courier": "picape-pequena", "f-1000": "picape-media", "f-250": "picape-media",
    "f-150": "picape-media", "transit": "furgao-grande", "royale": "monovolume", "versailles": "sedan-medio",
    "mustang": "sedan-medio", "explorer": "suv-medio",
    # Peugeot / Citroën
    "208": "hatch-medio", "207": "hatch-medio", "206": "hatch-compacto", "2008": "suv-compacto",
    "3008": "suv-medio", "5008": "suv-medio", "308": "hatch-medio", "408": "sedan-medio", "307": "hatch-medio",
    "partner": "furgao-compacto", "expert": "furgao-compacto", "boxer": "furgao-grande", "hoggar": "picape-pequena",
    "106": "hatch-compacto", "205": "hatch-compacto", "306": "hatch-medio", "406": "sedan-medio",
    "c3": "hatch-medio", "c4": "hatch-medio", "c4 cactus": "suv-compacto", "c4 lounge": "sedan-medio",
    "c4 picasso": "monovolume", "grand c4 picasso": "monovolume", "c3 picasso": "monovolume", "aircross": "suv-compacto",
    "c3 aircross": "suv-compacto", "berlingo": "furgao-compacto", "jumpy": "furgao-compacto", "jumper": "furgao-grande",
    "xsara": "hatch-medio", "xsara picasso": "monovolume", "c5": "sedan-medio", "c4 pallas": "sedan-medio",
    "basalt": "suv-cupe", "ds3": "hatch-compacto", "ds4": "hatch-medio", "ds5": "hatch-medio",
    # Mitsubishi
    "l200": "picape-media", "l200 triton": "picape-media", "pajero": "suv-offroad", "pajero sport": "suv-medio",
    "pajero full": "suv-offroad", "pajero tr4": "suv-offroad", "pajero dakar": "suv-medio", "asx": "suv-compacto",
    "outlander": "suv-medio", "outlander sport": "suv-compacto", "eclipse cross": "suv-compacto", "lancer": "sedan-medio",
    "pajero io": "suv-offroad", "triton": "picape-media",
    # Kia
    "sportage": "suv-medio", "sorento": "suv-medio", "cerato": "sedan-medio", "picanto": "hatch-compacto",
    "soul": "hatch-medio", "stonic": "suv-compacto", "niro": "suv-compacto", "bongo": "caminhao-leve",
    "carnival": "monovolume", "rio": "hatch-medio", "seltos": "suv-compacto", "optima": "sedan-medio",
    "besta": "furgao-compacto",
    # Chery / BYD / GWM / JAC
    "tiggo 2": "suv-compacto", "tiggo 3x": "suv-compacto", "tiggo 4": "suv-compacto", "tiggo 5x": "suv-compacto",
    "tiggo 7": "suv-medio", "tiggo 8": "suv-medio", "arrizo 5": "sedan-compacto", "arrizo 6": "sedan-medio",
    "qq": "hatch-compacto", "celer": "hatch-medio", "face": "hatch-compacto", "tiggo": "suv-compacto",
    "dolphin": "hatch-medio", "dolphin mini": "hatch-compacto", "seal": "sedan-medio", "song plus": "suv-medio",
    "song pro": "suv-medio", "yuan plus": "suv-compacto", "yuan pro": "suv-compacto", "king": "sedan-medio",
    "tan": "suv-medio", "han": "sedan-medio", "shark": "picape-media", "seal u": "suv-medio",
    "haval h6": "suv-medio", "ora 03": "hatch-medio", "poer": "picape-media", "tank": "suv-offroad",
    "j3": "hatch-medio", "j5": "sedan-medio", "j6": "monovolume", "t40": "suv-compacto", "t50": "suv-compacto",
    "t60": "suv-medio", "t80": "suv-medio", "e-js1": "hatch-compacto", "e-js4": "suv-compacto",
    # Linhas premium agrupadas e modelos novos
    "classe b": "monovolume", "classe e": "sedan-medio", "classe s": "sedan-medio", "classe g": "suv-offroad",
    "classe v": "furgao-compacto", "classe x": "picape-media", "cla": "sedan-medio", "cls": "sedan-medio",
    "glb": "suv-medio", "gls": "suv-medio", "ml": "suv-medio", "gl": "suv-medio", "glk": "suv-medio",
    "série 1": "hatch-medio", "série 2": "sedan-medio", "série 4": "sedan-medio", "série 5": "sedan-medio",
    "série 6": "sedan-medio", "série 7": "sedan-medio", "série 8": "sedan-medio", "x2": "suv-compacto",
    "x4": "suv-cupe", "x7": "suv-medio", "a5": "sedan-medio", "a6": "sedan-medio", "a7": "sedan-medio",
    "a8": "sedan-medio", "q6": "suv-medio", "q8": "suv-cupe", "kait": "suv-compacto", "stepway": "hatch-medio",
    "chevy 500": "picape-pequena", "atto 2": "suv-compacto", "atto 8": "suv-medio", "yuan plus": "suv-compacto",
    "yuan pro": "suv-compacto", "sealion 7": "suv-medio", "haval": "suv-medio", "ora": "hatch-medio",
    "wey": "suv-medio", "tasman": "picape-media", "mohave": "suv-medio", "avenger": "suv-compacto",
    "boreal": "suv-medio", "range rover evoque": "suv-compacto", "range rover velar": "suv-medio",
    "range rover sport": "suv-medio", "hover": "suv-medio", "s-18": "hatch-medio", "cielo": "sedan-compacto",
    "kicks e-power": "suv-compacto", "commander": "suv-medio", "odyssey": "monovolume", "hiace": "furgao-grande",
    # Premium e outros
    "classe a": "hatch-medio", "classe c": "sedan-medio", "sprinter": "furgao-grande", "vito": "furgao-compacto",
    "gla": "suv-compacto", "glc": "suv-medio", "gle": "suv-medio", "série 3": "sedan-medio", "320i": "sedan-medio",
    "x1": "suv-compacto", "x3": "suv-medio", "x5": "suv-medio", "x6": "suv-cupe", "a3": "hatch-medio",
    "a4": "sedan-medio", "q3": "suv-compacto", "q5": "suv-medio", "q7": "suv-medio", "a1": "hatch-compacto",
    "range rover": "suv-medio", "discovery": "suv-medio", "discovery sport": "suv-medio", "defender": "suv-offroad",
    "freelander": "suv-medio", "xc40": "suv-compacto", "xc60": "suv-medio", "xc90": "suv-medio",
    "rampage": "picape-media", "1500": "picape-media", "2500": "picape-media", "3500": "picape-media",
    "jimny": "suv-offroad", "vitara": "suv-compacto", "grand vitara": "suv-medio", "swift": "hatch-compacto",
    "s-cross": "suv-compacto", "sx4": "hatch-medio", "forester": "suv-medio", "impreza": "sedan-medio",
    "xv": "suv-compacto", "outback": "monovolume", "t4": "suv-offroad", "pantanal": "picape-media",
    "daily": "caminhao-leve", "marrua": "suv-offroad", "x60": "suv-compacto", "320": "sedan-medio",
    "niva": "suv-offroad", "laika": "sedan-compacto", "samara": "hatch-compacto", "br-800": "hatch-compacto",
    "gol g4": "hatch-medio", "mx-5": "sedan-medio", "cx-5": "suv-medio", "mx5": "sedan-medio", "d-max": "picape-media",
}

BODY_LABEL = {
    "hatch": "Hatch", "sedan": "Sedã", "suv": "SUV", "picape": "Picape", "furgao": "Utilitário",
    "monovolume": "Perua / minivan", "caminhao": "Utilitário", "car": "",
}

ENGINE_RE = re.compile(r"(?<![\d.])(\d\.\d)(?![\d])")


def ascii_lower(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def is_electric(label):
    low = ascii_lower(label)
    return "eletric" in low or "letrico" in low or "trico)" in low or "elétr" in label.lower()


MERCEDES_CLASS = re.compile(r"^(a|b|c|e|s|g|r|v|x)-?\d")
MERCEDES_LINE = re.compile(r"^(amg gt|cla|clc|clk|cls|cl|gla|glb|glc|gle|glk|gls|gl|ml|slc|slk|sls|sl)-?\d")
BMW_SERIES = re.compile(r"^m?(\d)\d\d")


def base_name(label, brand_key=""):
    """'Strada Working 1.4 mpi Fire Flex 8V CS' -> ('strada', 'Strada')."""
    clean = re.sub(r"\s+", " ", label.strip())
    low = clean.lower()
    # "Band.Jipe", "Range R.", "Santa Fe/GLS": pontos e barras separam palavras na comparação.
    words = re.sub(r"[/.,]", " ", low).split()
    if brand_key == "mercedes-benz":
        m = MERCEDES_LINE.match(low)
        if m:
            name = m.group(1).upper()
            return name.lower(), name
        m = MERCEDES_CLASS.match(low)
        if m:
            name = "Classe " + m.group(1).upper()
            return name.lower(), name
    if brand_key == "bmw":
        m = BMW_SERIES.match(low)
        if m:
            name = "Série " + m.group(1)
            return name.lower(), name
    if len(words) > 1 and words[0] == "classe" and words[1].isalpha() and len(words[1]) <= 3:
        name = "Classe " + words[1].upper()
        return name.lower(), name
    if len(words) > 1 and words[0] in ("xc", "ex", "ec") and re.fullmatch(r"\d{2}", words[1]):
        name = (words[0] + words[1]).upper()
        return name.lower(), name
    for size in (3, 2):
        key = " ".join(words[:size])
        if len(words) >= size and key in MULTI:
            return MULTI[key].lower(), MULTI[key]
    first = clean.split(" ")[0].strip(",/;:")
    if re.fullmatch(r"\(.*\)", first):
        first = clean.split(" ")[1] if " " in clean else first
    k = first.lower().rstrip(".")
    for cand in (k, words[0] if words else k):
        if cand in MULTI:
            return MULTI[cand].lower(), MULTI[cand]
        if cand in RENAME:
            return RENAME[cand].lower(), RENAME[cand]
    if "." in k:  # "Band.Jipe" sem regra: fica a primeira parte
        k = k.split(".")[0]
        first = first.split(".")[0]
    return k, first.rstrip(".")


def display_variant(variants):
    """Escolhe a grafia: prefere a que não está toda em maiúsculas."""
    counts = Counter(variants)
    mixed = [v for v, _ in counts.most_common() if v != v.upper()]
    if mixed:
        return mixed[0]
    v = counts.most_common(1)[0][0]
    if v.isalpha() and len(v) > 3:
        return v.title()
    return v


def year_ranges(years):
    years = sorted(set(years))
    out = []
    start = prev = years[0]
    for y in years[1:]:
        if y == prev + 1:
            prev = y
            continue
        out.append(f"{start}-{prev}" if prev != start else f"{start}")
        start = prev = y
    out.append(f"{start}-{prev}" if prev != start else f"{start}")
    return ",".join(out)


def infer_shape(name_key, labels, engines, fuels):
    if name_key in SHAPES:
        return SHAPES[name_key]
    first = name_key.split(" ")[0]
    if first in SHAPES:
        return SHAPES[first]
    low = " ".join(ascii_lower(l) for l in labels)
    sizes = [float(e) for e in engines if re.fullmatch(r"\d\.\d", e)]
    big = (max(sizes) if sizes else 0) >= 2.2 or "3" in fuels
    n = max(len(labels), 1)

    def share(pattern):
        return sum(1 for l in labels if re.search(pattern, ascii_lower(l))) / n

    if share(r"\b(cs|cd|ce|cab\.?|cabine|pick-?up|picape)\b") >= 0.4:
        return "picape-media" if big else "picape-pequena"
    if share(r"furg|\bvan\b|minibus|passag|cargo|chassi|\bfurg") >= 0.4:
        return "furgao-grande" if big else "furgao-compacto"
    if share(r"\bsed(an)?\b|\bsed\.") >= 0.4:
        return "sedan-medio" if (min(sizes) if sizes else 0) >= 1.8 else "sedan-compacto"
    if share(r"4x4|4wd|\bsuv\b") >= 0.4:
        return "suv-medio"
    if share(r"\b[35]p\b|hatch") >= 0.4:
        return "hatch-medio" if (max(sizes) if sizes else 0) >= 1.4 else "hatch-compacto"
    del low
    return "car-generic"


def build(raw_path):
    with open(raw_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    this_year = datetime.date.today().year

    brands = {}
    for marca in raw["marcas"]:
        meta = FIPE_BRANDS.get(marca["nome"])
        if not meta:
            print(f"AVISO: marca sem mapeamento: {marca['nome']}")
            continue
        key, name, slug, aliases = meta
        b = brands.setdefault(key, {
            "k": key, "n": name, "l": logo_file(key, slug), "a": set(aliases),
            "models": defaultdict(lambda: {"variants": [], "labels": set(), "eng": defaultdict(lambda: [set(), set()])}),
        })
        b["a"].add(ascii_lower(marca["nome"]))
        for ano_value, labels in marca["anos"].items():
            ano, comb = ano_value.split("-")
            years = [this_year, this_year + 1] if ano == "32000" else [int(ano)]
            for label in labels:
                mkey, variant = base_name(label, key)
                if not mkey or len(mkey) > 30:
                    continue
                model = b["models"][mkey]
                model["variants"].append(variant)
                model["labels"].add(label)
                engines = sorted(set(ENGINE_RE.findall(label)))
                engines = [e for e in engines if 0.6 <= float(e) <= 8.5]
                if not engines:
                    engines = ["Elétrico"] if (comb == "4" or is_electric(label)) else [""]
                for e in engines:
                    model["eng"][e][0].update(years)
                    model["eng"][e][1].add(comb)

    out_brands = []
    total_models = 0
    for key, b in brands.items():
        models = []
        for mkey, m in b["models"].items():
            name = display_variant(m["variants"])
            eng = {}
            fuels_all = set()
            for e, (years, fuels) in m["eng"].items():
                fuels_all |= fuels
                eng[e] = [year_ranges(years), "".join(sorted(fuels))]
            # Motor "" só faz sentido se não houver nenhuma litragem conhecida.
            if "" in eng and len(eng) > 1:
                del eng[""]
            shape = infer_shape(mkey, sorted(m["labels"]), list(eng), fuels_all)
            models.append([name, shape, eng])
        models.sort(key=lambda x: ascii_lower(x[0]))
        total_models += len(models)
        aliases = sorted(a for a in b["a"] if a and a != ascii_lower(b["n"]))
        out_brands.append({"k": key, "n": b["n"], "l": b["l"], "a": aliases, "m": models})

    rank = {k: i for i, k in enumerate(POPULAR)}
    out_brands.sort(key=lambda b: (rank.get(b["k"], len(POPULAR)), ascii_lower(b["n"])))
    payload = {
        "source": f"Tabela FIPE (tabela {raw.get('tabela')}, gerado em {datetime.date.today().isoformat()})",
        "popular": [k for k in POPULAR if k in brands],
        "brands": out_brands,
    }
    js = (
        "/* Catálogo de marcas/modelos vendidos no Brasil (gerado por scripts/build_vehicle_catalog.py\n"
        " * a partir da Tabela FIPE). Não edite à mão: rode o script de novo. */\n"
        "window.VEHICLE_CATALOG = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(js)
    print(f"{len(out_brands)} marcas, {total_models} modelos -> {OUT} ({len(js.encode()) // 1024} KB)")


if __name__ == "__main__":
    build(sys.argv[1])
