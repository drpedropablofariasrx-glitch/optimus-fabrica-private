#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_mano_muneca.py
=========================
Validador determinista para informes de RM de mano y muñeca (proyecto MSK
codo/muñeca/mano). Mismo patrón que los demás validadores de región.

Reglas estrella: valoración obligatoria de nervios (mediano/cubital en mano;
túnel carpiano/canal de Guyon si incluye muñeca), y taxonomías cerradas de
severidad y cronicidad.
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


def _bloque(texto: str, nombre: str) -> str:
    n = _norm(texto)
    encabezados = {
        "exploracion": r"exploraci[oó]n\s*:",
        "hallazgos": r"hallazgos\s*:",
        "impresion": r"impresi[oó]n diagn[oó]stica\s*:?",
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
    """No incluir edad ni sexo en Hallazgos ni en el cuerpo del informe."""
    flags = []
    hallazgos = _norm(_bloque(texto, "hallazgos"))
    if not hallazgos:
        hallazgos = _norm(texto)
    m = re.search(r"paciente de\s+\d{1,3}\s*an\w?os?|(\b\d{1,3}\s*an\w?os?\b.{0,10}(hombre|mujer|var[oó]n))", hallazgos)
    if m:
        flags.append(Flag("D1", "media",
            "Edad/sexo en el cuerpo del informe; deben ir solo en el DATASET_ENTRY interno.",
            m.group(0)))
    return flags


_SEVERIDAD_OK = ["leve", "moderada", "moderada-avanzada", "avanzada"]
_SEVERIDAD_MALA = ["severa", "grave", "leve-moderada", "importante"]

def regla_D2(texto: str) -> List[Flag]:
    """Severidad solo dentro de la taxonomía cerrada."""
    flags = []
    n = _norm(texto)
    for termino in _SEVERIDAD_MALA:
        for m in re.finditer(rf"\b{re.escape(termino)}\b", n):
            flags.append(Flag("D2", "baja",
                f"Término de severidad '{termino}' fuera de la taxonomía cerrada "
                f"(leve / moderada / moderada-avanzada / avanzada).",
                _ventana(texto, m.start(), 50)))
            break
    return flags


_CRONICIDAD_OK = ["aguda", "subaguda", "cronica", "degenerativa", "postraumatica", "postquirurgica"]

def regla_D3(texto: str) -> List[Flag]:
    """Revisa una cronicidad declarada de forma estructurada, sin exigirla."""
    flags = []
    n = _norm(texto)
    # Solo se interpreta como taxonomía si el informe la declara expresamente.
    # Así, frases clínicas libres como "cambios crónicos" no generan avisos.
    patron = r"\b(?:cronicidad|evolucion|curso)\s*:\s*([a-z-]+)"
    for m in re.finditer(patron, n):
        termino = m.group(1)
        if termino not in _CRONICIDAD_OK:
            flags.append(Flag(
                "D3", "baja",
                f"Término de cronicidad '{termino}' fuera de la taxonomía aprobada "
                "(aguda / subaguda / crónica / degenerativa / postraumática / postquirúrgica).",
                _ventana(texto, m.start(), 50),
            ))
    return flags


# ======================================================================
#  REGLAS BLANDAS COMPROBABLES (valoración de nervios)
# ======================================================================

def regla_B1(texto: str) -> List[Flag]:
    """Informe de mano: debe valorar explícitamente nervio mediano y cubital."""
    flags = []
    n = _norm(texto)
    explor = _norm(_bloque(texto, "exploracion"))
    # Un estudio de dedo/falange no equivale a un estudio completo de mano.
    campo_limitado = any(termino in explor for termino in ("dedo", "falange", "interfalangica"))
    es_mano = ("mano" in explor or "mano" in n[:200]) and not campo_limitado
    if not es_mano:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or n
    if "nervio mediano" not in hallazgos:
        flags.append(Flag("B1", "media",
            "Informe de mano sin valoración explícita del nervio mediano (regla fija de mano)."))
    if "nervio cubital" not in hallazgos and "cubital" not in hallazgos:
        flags.append(Flag("B1", "media",
            "Informe de mano sin valoración explícita del nervio cubital (regla fija de mano)."))
    return flags


def regla_B2(texto: str) -> List[Flag]:
    """Si el estudio incluye muñeca, valorar túnel carpiano y canal de Guyon."""
    flags = []
    n = _norm(texto)
    explor = _norm(_bloque(texto, "exploracion"))
    es_muneca = "muneca" in explor or "muneca" in n[:200]
    if not es_muneca:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or n
    if "tunel carpiano" not in hallazgos and "canal carpiano" not in hallazgos:
        flags.append(Flag("B2", "baja",
            "Estudio de muñeca sin valoración explícita del túnel carpiano."))
    if "guyon" not in hallazgos:
        flags.append(Flag("B2", "baja",
            "Estudio de muñeca sin valoración explícita del canal de Guyon."))
    return flags


TODAS_LAS_REGLAS = [regla_D1, regla_D2, regla_D3, regla_B1, regla_B2]


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
        return "✓ Sin incidencias. El informe pasa las reglas comprobables."
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
