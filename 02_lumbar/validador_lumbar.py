#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_lumbar.py
====================
Validador determinista para informes de RM columna lumbar.

Codifica las 3 reglas DURAS extraídas de REGLAS_LUMBAR_MAESTRAS.md
(un año de correcciones reales en ChatGPT, ~159 casos). Misma filosofía
que validador_abdomen.py: código que comprueba, no un modelo que opina.

Uso:
    python3 validador_lumbar.py informe.txt
    from validador_lumbar import validar, informe_validacion
"""

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Flag:
    regla: str
    gravedad: str
    mensaje: str
    fragmento: str = ""

    def __str__(self):
        frag = f"  →  «{self.fragmento.strip()[:90]}»" if self.fragmento else ""
        return f"[{self.regla}|{self.gravedad}] {self.mensaje}{frag}"


def _norm(texto: str) -> str:
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _ventana(texto: str, pos: int, radio: int = 90) -> str:
    return texto[max(0, pos - radio): pos + radio]


def _bloque(texto: str, nombre: str) -> str:
    n = _norm(texto)
    encabezados = {
        "datos clinicos": r"datos cl[ií]nicos\s*:",
        "hallazgos": r"hallazgos\s*:",
        "impresion": r"impresi[oó]n diagn[oó]stica\s*:",
    }
    pat = encabezados.get(nombre)
    if not pat:
        return ""
    m = re.search(pat, n)
    if not m:
        return ""
    inicio = m.end()
    fin = len(texto)
    for otra in encabezados.values():
        m2 = re.search(otra, n[inicio:])
        if m2:
            fin = min(fin, inicio + m2.start())
    return texto[inicio:fin]


# ======================================================================
#  REGLAS DURAS
# ======================================================================

def regla_D1(texto: str) -> List[Flag]:
    """
    Medidas de protrusión/hernia con 2 dimensiones (p.ej. 15 x 5 mm) deben
    indicar los ejes: '(diámetros transverso y anteroposterior)' — salvo
    que se mencione explícitamente un tercer eje (craneocaudal).
    """
    flags = []
    n = _norm(texto)
    # buscar "NN x NN mm" cerca de protrusion/hernia, sin mención de ejes cerca
    for m in re.finditer(r"(protrusi[oó]n|hernia)[^.]{0,60}?(\d{1,3})\s*x\s*(\d{1,3})\s*mm", n):
        ventana = n[m.start(): m.end() + 90]
        if not re.search(r"transvers|anteroposterior|craneocaudal|eje", ventana):
            flags.append(Flag("D1", "baja",
                f"Medida '{m.group(2)} x {m.group(3)} mm' sin especificar los ejes "
                f"(por defecto: transverso × anteroposterior).",
                _ventana(texto, m.start(), 70)))
    return flags


def regla_D2(texto: str) -> List[Flag]:
    """
    Pie 'Informado por / Validado por': incluir SI Y SOLO SI el informe tiene
    marcadores de formato clínico chileno (FONASA, ID paciente, previsión, RUT).
    Esta es una regla UNIVERSAL (misma lógica en todas las regiones), no
    específica de lumbar — corregido tras aclaración del radiólogo.
    """
    flags = []
    n = _norm(texto)
    marcadores = [r"fonasa", r"id paciente", r"previsi[oó]n\s*:", r"rut\s*:"]
    es_chile = any(re.search(p, n) for p in marcadores)
    tiene_pie = "validado por" in n
    if es_chile and not tiene_pie:
        flags.append(Flag("D2", "baja",
            "Formato clínico chileno detectado pero falta el pie 'Informado por / Validado por'."))
    if not es_chile and tiene_pie:
        flags.append(Flag("D2", "baja",
            "El informe incluye 'Informado por / Validado por' sin marcadores de formato "
            "clínico chileno; en ese caso no debería incluirse."))
    return flags


def regla_D4(texto: str) -> List[Flag]:
    """
    El informe no debe mostrar de forma visible marcadores de TAGS o
    DATASET_ENTRY dentro del cuerpo del informe (deben ir aparte, no en el
    bloque que se copia al PACS).
    """
    flags = []
    n = _norm(texto)
    if re.search(r"\btags?\s*:", n) or "dataset_entry" in n or "dataset entry" in n:
        flags.append(Flag("D4", "media",
            "El informe contiene marcadores de TAGS/DATASET_ENTRY visibles; "
            "el formato acordado los excluye del bloque que se copia al PACS."))
    return flags


TODAS_LAS_REGLAS = [regla_D1, regla_D2, regla_D4]


def validar(texto: str) -> List[Flag]:
    flags: List[Flag] = []
    for regla in TODAS_LAS_REGLAS:
        try:
            flags.extend(regla(texto))
        except Exception as e:
            flags.append(Flag(regla.__name__, "baja", f"[error interno en la regla: {e}]"))
    return flags


def informe_validacion(texto: str) -> str:
    flags = validar(texto)
    if not flags:
        return "✓ Sin incidencias. El informe pasa las 3 reglas duras comprobables."
    orden = {"alta": 0, "media": 1, "baja": 2}
    flags.sort(key=lambda f: orden.get(f.gravedad, 3))
    out = [f"Se encontraron {len(flags)} incidencia(s):", ""]
    out += [str(f) for f in flags]
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            texto = fh.read()
    else:
        texto = sys.stdin.read()
    print(informe_validacion(texto))
