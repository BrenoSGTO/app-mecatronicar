# -*- coding: utf-8 -*-
"""
Marcas de carros da Tabela FIPE -> chave usada no app, nome exibido e logo.

`logo` é o slug no car-logos-dataset (github.com/filippofilip95/car-logos-dataset);
None = a marca não tem logo lá e recebe um monograma gerado (iniciais num círculo).
Marcas FIPE duplicadas (ex.: "GREAT WALL" e "GWM") apontam para a mesma chave e
têm os modelos somados.

Uso: python scripts/vehicle_brands.py [--force]   (baixa os logos que faltam em static/brands/;
     com Pillow instalado, corta e reduz cada PNG para 256 px)
"""
import json
import os
import sys
import urllib.request
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS_DIR = os.path.join(ROOT, "static", "brands")
LOGO_URL = "https://cdn.jsdelivr.net/gh/filippofilip95/car-logos-dataset@v2.8.0/logos/optimized/{slug}.png"

# nome na FIPE -> (chave, nome exibido, slug do logo, apelidos para reconhecer no texto)
FIPE_BRANDS = {
    "AM Gen": ("am-gen", "AM General", None, ["am general", "hummer h1"]),
    "ARROW": ("arrow", "Arrow", None, []),
    "ASTON MARTIN": ("aston-martin", "Aston Martin", "aston-martin", []),
    "Acura": ("acura", "Acura", "acura", []),
    "Agrale": ("agrale", "Agrale", None, []),
    "Alfa Romeo": ("alfa-romeo", "Alfa Romeo", "alfa-romeo", ["alfa"]),
    "Asia Motors": ("asia", "Asia Motors", None, ["asia"]),
    "Audi": ("audi", "Audi", "audi", []),
    "BMW": ("bmw", "BMW", "bmw", []),
    "BRM": ("brm", "BRM", None, []),
    "BYD": ("byd", "BYD", "byd", []),
    "Baby": ("baby", "Baby", None, []),
    "Bugre": ("bugre", "Bugre", None, []),
    "CAB Motors": ("cab", "CAB Motors", None, []),
    "CBT Jipe": ("cbt", "CBT", None, []),
    "CHANA": ("changan", "Changan", "changan", ["chana", "caoa changan"]),
    "CHANGAN": ("changan", "Changan", "changan", []),
    "Cadillac": ("cadillac", "Cadillac", "cadillac", []),
    "Caoa Changan": ("changan", "Changan", "changan", []),
    "Caoa Chery": ("chery", "Caoa Chery", "chery", ["caoa", "chery"]),
    "Caoa Chery/Chery": ("chery", "Caoa Chery", "chery", []),
    "Chrysler": ("chrysler", "Chrysler", "chrysler", []),
    "Citroën": ("citroen", "Citroën", "citroen", ["citroen"]),
    "Cross Lander": ("cross-lander", "Cross Lander", None, ["crosslander"]),
    "D2D Motors": ("d2d", "D2D Motors", None, []),
    "DFSK": ("dfsk", "DFSK", None, []),
    "Daewoo": ("daewoo", "Daewoo", "daewoo", []),
    "Daihatsu": ("daihatsu", "Daihatsu", "daihatsu", []),
    "Denza": ("denza", "Denza", "denza", []),
    "Dodge": ("dodge", "Dodge", "dodge", []),
    "EFFA": ("effa", "Effa", None, []),
    "Engesa": ("engesa", "Engesa", None, []),
    "Envemo": ("envemo", "Envemo", None, []),
    "FEVER": ("fever", "Fever", None, []),
    "FOTON": ("foton", "Foton", "foton", []),
    "Ferrari": ("ferrari", "Ferrari", "ferrari", []),
    "Fiat": ("fiat", "Fiat", "fiat", []),
    "Fibravan": ("fibravan", "Fibravan", None, []),
    "Ford": ("ford", "Ford", "ford", []),
    "Fyber": ("fyber", "Fyber", None, []),
    "GAC": ("gac", "GAC", "gac-group", []),
    "GEELY": ("geely", "Geely", "geely", []),
    "GM - Chevrolet": ("chevrolet", "Chevrolet", "chevrolet", ["chevrolet", "chevy", "gm", "chev"]),
    "GREAT WALL": ("gwm", "GWM", "great-wall", ["great wall", "haval"]),
    "GWM": ("gwm", "GWM", "great-wall", []),
    "Gurgel": ("gurgel", "Gurgel", None, []),
    "HAFEI": ("hafei", "Hafei", "hafei", []),
    "HITECH ELECTRIC": ("hitech", "Hitech Electric", None, ["hitech"]),
    "Honda": ("honda", "Honda", "honda", []),
    "Hyundai": ("hyundai", "Hyundai", "hyundai", ["hyunday", "caoa hyundai"]),
    "IVECO": ("iveco", "Iveco", "iveco", []),
    "Isuzu": ("isuzu", "Isuzu", "isuzu", []),
    "JAC": ("jac", "JAC", "jac", []),
    "JINBEI": ("jinbei", "Jinbei", None, []),
    "JPX": ("jpx", "JPX", None, []),
    "Jaecoo": ("jaecoo", "Jaecoo", "jaecoo", []),
    "Jaguar": ("jaguar", "Jaguar", "jaguar", []),
    "Jeep": ("jeep", "Jeep", "jeep", []),
    "Jetour": ("jetour", "Jetour", "jetour", []),
    "Kia Motors": ("kia", "Kia", "kia", ["kia"]),
    "LAMBORGHINI": ("lamborghini", "Lamborghini", "lamborghini", []),
    "LIFAN": ("lifan", "Lifan", "lifan", []),
    "LOBINI": ("lobini", "Lobini", "lobini", []),
    "Lada": ("lada", "Lada", "lada", []),
    "Land Rover": ("land-rover", "Land Rover", "land-rover", ["landrover"]),
    "Leapmotor": ("leapmotor", "Leapmotor", "leapmotor", []),
    "Lexus": ("lexus", "Lexus", "lexus", []),
    "Lotus": ("lotus", "Lotus", "lotus", []),
    "MG": ("mg", "MG", "mg", []),
    "MINI": ("mini", "Mini", "mini", []),
    "Mahindra": ("mahindra", "Mahindra", "mahindra", []),
    "Maserati": ("maserati", "Maserati", "maserati", []),
    "Matra": ("matra", "Matra", None, []),
    "Mazda": ("mazda", "Mazda", "mazda", []),
    "Mclaren": ("mclaren", "McLaren", "mclaren", []),
    "Mercedes-Benz": ("mercedes-benz", "Mercedes-Benz", "mercedes-benz", ["mercedes", "benz", "mb"]),
    "Mercury": ("mercury", "Mercury", "mercury", []),
    "Mitsubishi": ("mitsubishi", "Mitsubishi", "mitsubishi", ["mitsu"]),
    "Miura": ("miura", "Miura", None, []),
    "NETA": ("neta", "Neta", None, []),
    "Nissan": ("nissan", "Nissan", "nissan", []),
    "Omoda": ("omoda", "Omoda", "omoda", []),
    "Peugeot": ("peugeot", "Peugeot", "peugeot", ["peugeout", "pegeot"]),
    "Plymouth": ("plymouth", "Plymouth", "plymouth", []),
    "Pontiac": ("pontiac", "Pontiac", "pontiac", []),
    "Porsche": ("porsche", "Porsche", "porsche", []),
    "RAM": ("ram", "RAM", "ram", []),
    "RELY": ("rely", "Rely", None, []),
    "Renault": ("renault", "Renault", "renault", []),
    "Rolls-Royce": ("rolls-royce", "Rolls-Royce", "rolls-royce", []),
    "Rover": ("rover", "Rover", "rover", []),
    "SERES": ("seres", "Seres", None, []),
    "SHINERAY": ("shineray", "Shineray", None, []),
    "SSANGYONG": ("ssangyong", "SsangYong", "ssangyong", []),
    "Saab": ("saab", "Saab", "saab", []),
    "Saturn": ("saturn", "Saturn", "saturn", []),
    "Seat": ("seat", "Seat", "seat", []),
    "Subaru": ("subaru", "Subaru", "subaru", []),
    "Suzuki": ("suzuki", "Suzuki", "suzuki", []),
    "TAC": ("tac", "TAC", None, []),
    "Toyota": ("toyota", "Toyota", "toyota", ["toyo"]),
    "Troller": ("troller", "Troller", "troller", []),
    "VW - VolksWagen": ("volkswagen", "Volkswagen", "volkswagen", ["vw", "volks", "volkswagen", "wolks"]),
    "Volvo": ("volvo", "Volvo", "volvo", []),
    "Wake": ("wake", "Wake", None, []),
    "Walk": ("walk", "Walk", None, []),
    "ZEEKR": ("zeekr", "Zeekr", "zeekr", []),
    "smart": ("smart", "Smart", "smart", []),
}


def monogram_svg(name):
    words = [w for w in name.replace("-", " ").split() if w]
    initials = (words[0][:2] if len(words) == 1 else words[0][0] + words[1][0]).upper()
    size = 26 if len(initials) <= 2 else 20
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" color="#52525b">'
        '<circle cx="32" cy="32" r="29.5" fill="none" stroke="currentColor" stroke-width="3"/>'
        f'<text x="32" y="32" dy=".35em" text-anchor="middle" fill="currentColor" '
        "font-family=\"'Segoe UI Variable Display','Segoe UI',system-ui,sans-serif\" "
        f'font-size="{size}" font-weight="700" letter-spacing=".5">{escape(initials)}</text></svg>'
    )


def shrink_png(path, box=256):
    """Corta a margem transparente e reduz para no máximo 256 px (precisa do Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow ausente: logo mantido no tamanho original)")
        return
    im = Image.open(path).convert("RGBA")
    bbox = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    im.thumbnail((box, box), Image.LANCZOS)
    im.save(path, optimize=True)


def logo_file(key, slug):
    return f"{key}.png" if slug else f"{key}.svg"


def download_logos():
    os.makedirs(BRANDS_DIR, exist_ok=True)
    done = set()
    for key, name, slug, _ in FIPE_BRANDS.values():
        if key in done:
            continue
        done.add(key)
        path = os.path.join(BRANDS_DIR, logo_file(key, slug))
        if os.path.exists(path) and "--force" not in sys.argv:
            continue
        if slug:
            req = urllib.request.Request(LOGO_URL.format(slug=slug), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if not data.startswith(b"\x89PNG"):
                raise RuntimeError(f"logo inválido para {slug}")
            with open(path, "wb") as fh:
                fh.write(data)
            shrink_png(path)
            print(f"{key}: {os.path.getsize(path) // 1024} KB")
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(monogram_svg(name))
            print(f"{key}: monograma")


if __name__ == "__main__":
    download_logos()
