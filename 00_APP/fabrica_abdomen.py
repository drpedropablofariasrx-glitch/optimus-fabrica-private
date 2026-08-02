#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wrapper de compatibilidad para el antiguo punto de entrada de abdomen.

El punto de entrada recomendado de OPTIMUS es:
    python 00_APP/optimus_app.py
"""

from optimus_app import app
from optimus_app import CASOS_DIR


if __name__ == "__main__":
    print("AVISO: 00_APP/fabrica_abdomen.py queda como wrapper de compatibilidad.")
    print("       Punto de entrada recomendado: python 00_APP/optimus_app.py")
    print("=" * 60)
    print("  Fabrica de casos abierta en:  http://localhost:5000")
    print("  Tus casos se guardan en:      ", CASOS_DIR)
    print("  Para parar: Ctrl+C")
    print("=" * 60)
    app.run(port=5000, debug=False)
