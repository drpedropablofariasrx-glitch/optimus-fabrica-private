#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_rodilla.py
=====================
Validador determinista para informes de RM de rodilla.

Codifica las 4 reglas DURAS extraídas de REGLAS_RODILLA_MAESTRAS.md — el
corpus que documenta el origen del proyecto completo. Mismo patrón que
validador_abdomen.py / lumbar / cervical / torax.
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
    """No incluir datos demográficos (edad/sexo/hospital) en el cuerpo del informe.
       Detecta específicamente la fuga del patrón de input 'Edad, genero y hospital: ...'."""
    flags = []
    n = _norm(texto)
    m = re.search(r"edad,?\s*genero\s*y\s*hospital\s*:", n)
    if m:
        flags.append(Flag("D1", "alta",
            "El informe filtra la línea de datos demográficos del input ('Edad, género y hospital: ...'); no debe aparecer.",
            _ventana(texto, m.start(), 70)))
    # patrón adicional: "XX años, hombre/mujer" suelto fuera de datos clínicos
    # (tras _norm, "años" pierde la tilde de la ñ y queda "anos")
    for m2 in re.finditer(r"\b(\d{1,3})\s*an\w?os?,?\s*(hombre|mujer)\b", n):
        flags.append(Flag("D1", "media",
            "Posible dato demográfico (edad + sexo) filtrado en el cuerpo del informe.",
            _ventana(texto, m2.start(), 60)))
    return flags


def regla_D2(texto: str) -> List[Flag]:
    """No usar viñetas en el informe radiológico."""
    flags = []
    for m in re.finditer(r"(?:^|\n)\s*[-•*]\s+\S", texto):
        flags.append(Flag("D2", "baja",
            "Línea con viñeta en el informe; debe ir en prosa integrada, sin viñetas.",
            _ventana(texto, m.start(), 60)))
    return flags


def regla_D3(texto: str) -> List[Flag]:
    """Grados de condropatía deben ir en números romanos, no arábigos."""
    flags = []
    n = _norm(texto)
    for m in re.finditer(r"condropat[ií]a[^.]{0,25}?grado\s*(\d)\b", n):
        flags.append(Flag("D3", "baja",
            f"Condropatía grado {m.group(1)} en número arábigo; usar número romano (I, II, III, IV).",
            _ventana(texto, m.start(), 60)))
    return flags


def regla_D4(texto: str) -> List[Flag]:
    """La impresión diagnóstica no debe incluir hallazgos normales."""
    flags = []
    imp = _bloque(texto, "impresion")
    if not imp:
        return flags
    n_imp = _norm(imp)
    patrones_normal = [
        r"meniscos?\s+(normal|normales|integr)",
        r"ligamentos?\s+.{0,20}(normal|normales|integr)",
        r"sin\s+alteraciones\s+significativas",
        r"tendones?\s+.{0,20}(normal|normales)",
    ]
    for pat in patrones_normal:
        m = re.search(pat, n_imp)
        if m:
            flags.append(Flag("D4", "baja",
                "La impresión diagnóstica parece incluir un hallazgo normal; debe limitarse a la patología relevante.",
                imp[max(0, m.start()-20): m.start()+60]))
    return flags


TODAS_LAS_REGLAS = [regla_D1, regla_D2, regla_D3, regla_D4]


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
        return "✓ Sin incidencias. El informe pasa las 4 reglas duras comprobables."
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
