"""Permite que os testes importem os módulos do app (server, cache, ...) que ficam na raiz."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
