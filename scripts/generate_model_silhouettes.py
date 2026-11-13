# -*- coding: utf-8 -*-
"""
Gerador de Modelos Realistas em Alta Definição (MecatroniCar)
Executa a geração dos 106 arquivos de modelos automotivos em static/models/
com recortes fotorrealistas de estúdio e sombra de solo.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(BASE_DIR, "scripts", "build_photorealistic_models.py")

if __name__ == "__main__":
    if os.path.exists(BUILDER):
        os.system(f"python \"{BUILDER}\"")
    else:
        print("Builder script não encontrado.")
