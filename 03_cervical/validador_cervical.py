#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_cervical.py
======================
Validador determinista para informes de RM columna cervical.

Codifica las 3 reglas DURAS extraídas de REGLAS_CERVICAL_MAESTRAS.md.
Mismo patrón que validador_abdomen.py / validador_lumbar.py.

OJO — hay una diferencia anatómica real frente a lumbar:
  - Cervical NO usa "receso lateral"; lumbar SÍ lo usa.
El pie "Informado por / Validado por" no es una diferencia regional: se
incluye solo cuando existe formato clínico chileno.
Si en la fábrica se comparte código entre regiones, no convertir esta
diferencia anatómica cervical/lumbar en regla global.
"""

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import List


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


# ======================================================================
#  REGLAS DURAS
# ======================================================================

def regla_D1(texto: str) -> List[Flag]:
    """
    Pie 'Informado por / Validado por': incluir SI Y SOLO SI el informe tiene
    marcadores de formato clínico chileno (FONASA, ID paciente, previsión, RUT).
    Esta es una regla UNIVERSAL (misma lógica en todas las regiones), no
    específica de cervical — corregido tras aclaración del radiólogo.
    """
    flags = []
    n = _norm(texto)
    marcadores = [r"fonasa", r"id paciente", r"previsi[oó]n\s*:", r"rut\s*:"]
    es_chile = any(re.search(p, n) for p in marcadores)
    tiene_pie = "validado por" in n
    if es_chile and not tiene_pie:
        flags.append(Flag("D1", "baja",
            "Formato clínico chileno detectado pero falta el pie 'Informado por / Validado por'."))
    if not es_chile and tiene_pie:
        flags.append(Flag("D1", "baja",
            "El informe incluye 'Informado por / Validado por' sin marcadores de formato "
            "clínico chileno; en ese caso no debería incluirse."))
    return flags


def regla_D2(texto: str) -> List[Flag]:
    """No usar 'receso lateral' en columna cervical (sí se usa en lumbar; no confundir)."""
    flags = []
    n = _norm(texto)
    for m in re.finditer(r"receso\s+lateral", n):
        flags.append(Flag("D2", "media",
            "Uso de 'receso lateral' en columna cervical: ese compartimento anatómico no existe "
            "como tal en cervical (sí en lumbar). Usar estenosis foraminal / de canal central / "
            "deformidad medular según corresponda.",
            _ventana(texto, m.start(), 70)))
    return flags


def regla_D3(texto: str) -> List[Flag]:
    """Nomenclatura de hernias cervicales: evitar 'posterolateral'; usar localización cerrada
       (central/paracentral/paracentral-foraminal/foraminal/extraforaminal)."""
    flags = []
    n = _norm(texto)
    for m in re.finditer(r"postero\s*-?\s*lateral", n):
        flags.append(Flag("D3", "media",
            "Uso de 'posterolateral' para localizar una hernia cervical: término impreciso. "
            "Usar: central / paracentral / paracentral-foraminal / foraminal / extraforaminal.",
            _ventana(texto, m.start(), 70)))
    return flags


TODAS_LAS_REGLAS = [regla_D1, regla_D2, regla_D3]


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
