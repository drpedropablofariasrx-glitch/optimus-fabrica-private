#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_codo.py
=================
Validador determinista para informes de RM de codo/antebrazo.

Extraído de las correcciones y preferencias repetidas del corpus Codo.txt.
Mantiene la misma filosofía que los demás validadores regionales:

- no corrige el informe;
- devuelve flags trazables;
- prioriza detectar omisiones o incoherencias clínicamente relevantes;
- permite falsos positivos de baja gravedad antes que dejar pasar un error.

Uso:
    python validador_codo.py informe.txt

Desde código:
    from validador_codo import validar, informe_validacion
    flags = validar(texto)
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Callable, List


@dataclass
class Flag:
    regla: str
    gravedad: str  # alta | media | baja
    mensaje: str
    fragmento: str = ""

    def __str__(self) -> str:
        frag = f"  →  «{self.fragmento.strip()[:100]}»" if self.fragmento else ""
        return f"[{self.regla}|{self.gravedad}] {self.mensaje}{frag}"


def _norm(texto: str) -> str:
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _ventana(texto: str, pos: int, radio: int = 90) -> str:
    return texto[max(0, pos - radio): pos + radio]


def _bloque(texto: str, nombre: str) -> str:
    """Extrae bloques habituales del informe mediante encabezados."""
    n = _norm(texto)
    encabezados = {
        "datos clinicos": r"datos clinicos\s*:",
        "exploracion": r"exploracion\s*:",
        "hallazgos": r"hallazgos\s*:",
        "impresion": r"impresion diagnostica\s*: ?",
        "interpretacion": r"interpretacion global\s*: ?",
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


def _es_rm_codo(texto: str) -> bool:
    """Identifica una RM convencional de codo, no un campo parcial."""
    n = _norm(texto)
    exploracion = _norm(_bloque(texto, "exploracion"))
    campo_parcial = any(termino in exploracion for termino in (
        "antebrazo", "biceps distal", "insercion distal", "region olecraniana",
    ))
    return ("codo" in exploracion or "rm codo" in n[:300]) and not campo_parcial


# ----------------------------------------------------------------------
# REGLAS DURAS
# ----------------------------------------------------------------------

def regla_D1(texto: str) -> List[Flag]:
    """No filtrar edad, sexo o hospital al cuerpo del informe."""
    flags: List[Flag] = []
    n = _norm(texto)

    patrones = [
        r"edad\s*,?\s*genero\s*y\s*hospital\s*:",
        r"\b\d{1,3}\s*anos?\b.{0,15}\b(hombre|mujer|varon)\b",
        r"\bhospital\s+(vithas|turia|la fe|xativa)\b",
    ]
    for pat in patrones:
        m = re.search(pat, n)
        if m:
            flags.append(Flag(
                "D1",
                "media",
                "Posible dato demográfico o administrativo filtrado al informe; debe reservarse para el dataset interno.",
                _ventana(texto, m.start(), 70),
            ))
            break
    return flags


def regla_D2(texto: str) -> List[Flag]:
    """TAGS y DATASET_ENTRY no deben aparecer en el bloque copiable a PACS."""
    flags: List[Flag] = []
    n = _norm(texto)
    if re.search(r"\btags?\s*[:/]", n) or "dataset_entry" in n or "dataset entry" in n:
        flags.append(Flag(
            "D2",
            "media",
            "El texto contiene TAGS/DATASET_ENTRY visibles; deben permanecer fuera del informe PACS.",
        ))
    return flags


def regla_D3(texto: str) -> List[Flag]:
    """Evitar la redundancia 'epicondilitis ... con tendinosis ...'."""
    flags: List[Flag] = []
    n = _norm(texto)
    patron = r"epicondilitis\s+(?:lateral\s+)?(?:[^.\n]{0,55})\btendinosis\b(?:[^.\n]{0,55})\b(?:extensor|epicondilo lateral)"
    for m in re.finditer(patron, n):
        flags.append(Flag(
            "D3",
            "baja",
            "Redundancia semántica: 'epicondilitis' ya implica tendinopatía del origen extensor. Preferir 'tendinosis ... del tendón conjunto extensor' o 'epicondilitis lateral' sin duplicar ambos conceptos.",
            _ventana(texto, m.start(), 85),
        ))
    return flags


def regla_D4(texto: str) -> List[Flag]:
    """Protege las medidas de retracción en rotura completa de bíceps distal."""
    flags: List[Flag] = []
    n = _norm(texto)
    rotura_completa = re.search(
        r"rotura completa[^.]{0,60}(biceps distal|tendon distal del biceps)|(?:biceps distal|tendon distal del biceps)[^.]{0,60}rotura completa",
        n,
    )
    if rotura_completa:
        if "retraccion" not in n:
            flags.append(Flag(
                "D4",
                "baja",
                "Rotura completa del bíceps distal sin descripción de la retracción proximal.",
            ))
            return flags

        medidas = []
        for medida in re.finditer(r"retraccion[^.\n]{0,50}?(\d+(?:[.,]\d+)?)\s*(mm|cm)?\b", n):
            valor = float(medida.group(1).replace(",", "."))
            unidad = medida.group(2)
            if not unidad:
                flags.append(Flag(
                    "D4", "baja",
                    "Retracción del bíceps distal cuantificada sin unidad; conservar el dictado y revisar mm/cm.",
                    _ventana(texto, medida.start(), 70),
                ))
                continue
            medidas.append((valor * (10 if unidad == "cm" else 1), medida.start()))

        if len(medidas) >= 2:
            referencia = medidas[0][0]
            if any(abs(valor - referencia) > 0.01 for valor, _ in medidas[1:]):
                flags.append(Flag(
                    "D4", "baja",
                    "Medidas de retracción internamente discrepantes; no convertir unidades ni corregir el informe de forma silenciosa.",
                    _ventana(texto, medidas[0][1], 90),
                ))
    return flags


def regla_D5(texto: str) -> List[Flag]:
    """En controles postquirúrgicos/evolutivos, no afirmar evolución si no hay comparación."""
    flags: List[Flag] = []
    n = _norm(texto)
    control = bool(re.search(r"control evolutivo|evolucion|postquirurg|cirugia previa|estable|estabilidad", n))
    sin_previos = bool(re.search(r"no se dispone de estudios previos|sin estudios previos|no hay estudios previos", n))
    afirma_cambio = bool(re.search(r"ha aumentado|ha disminuido|progresion|mejoria|estable(?:\s+respecto)?|estabilidad", n))
    if control and sin_previos and afirma_cambio:
        flags.append(Flag(
            "D5",
            "alta",
            "Se afirma cambio evolutivo pese a declarar ausencia de estudios previos comparables.",
        ))
    return flags


# ----------------------------------------------------------------------
# REGLAS BLANDAS COMPROBABLES
# ----------------------------------------------------------------------

def regla_B1(texto: str) -> List[Flag]:
    """En RM de codo, valorar los nervios cubital, radial y mediano."""
    flags: List[Flag] = []
    if not _es_rm_codo(texto):
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    faltan = []
    for termino, etiqueta in [
        ("cubital", "nervio cubital"),
        ("radial", "nervio radial"),
        ("mediano", "nervio mediano"),
    ]:
        if termino not in hallazgos:
            faltan.append(etiqueta)
    if faltan:
        flags.append(Flag(
            "B1",
            "baja",
            "Valoración neurológica incompleta en RM de codo. Falta mencionar: " + ", ".join(faltan) + ".",
        ))
    return flags


def regla_B2(texto: str) -> List[Flag]:
    """Revisión tendinosa sistemática mínima del codo."""
    flags: List[Flag] = []
    if not _es_rm_codo(texto):
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    grupos = {
        "tendón conjunto extensor": ["conjunto extensor", "extensor comun", "tendon extensor"],
        "tendón conjunto flexor": ["conjunto flexor", "flexor comun", "tendon flexor"],
        "bíceps distal": ["biceps distal", "tendon del biceps", "tendon distal del biceps"],
        "tríceps": ["triceps", "tendon del triceps", "tendon distal del triceps"],
    }
    faltan = [nombre for nombre, claves in grupos.items() if not any(c in hallazgos for c in claves)]
    if faltan:
        flags.append(Flag(
            "B2",
            "baja",
            "Checklist tendinoso incompleto. Falta valorar: " + ", ".join(faltan) + ".",
        ))
    return flags


def regla_B3(texto: str) -> List[Flag]:
    """Si hay artefacto por movimiento, declarar que limita el estudio."""
    flags: List[Flag] = []
    n = _norm(texto)
    if "movimiento" in n or "escasa colaboracion" in n:
        if not re.search(r"limitad|degradad|artefact", n):
            flags.append(Flag(
                "B3",
                "baja",
                "Se menciona movimiento/escasa colaboración sin explicitar la limitación diagnóstica del estudio.",
            ))
    return flags


def regla_B4(texto: str) -> List[Flag]:
    """En estudios bilaterales, separar ambos codos y jerarquizar asimetrías."""
    flags: List[Flag] = []
    n = _norm(texto)
    exploracion = _norm(_bloque(texto, "exploracion"))
    bilateral = "bilateral" in exploracion or "ambos codos" in exploracion or "codos derecho e izquierdo" in exploracion
    if bilateral:
        hallazgos = _norm(_bloque(texto, "hallazgos"))
        if not ("codo derecho" in hallazgos and "codo izquierdo" in hallazgos):
            flags.append(Flag(
                "B4",
                "media",
                "Estudio bilateral sin separación explícita de los hallazgos de codo derecho e izquierdo.",
            ))
    return flags


TODAS_LAS_REGLAS: List[Callable[[str], List[Flag]]] = [
    regla_D1,
    regla_D2,
    regla_D3,
    regla_D4,
    regla_D5,
    regla_B1,
    regla_B2,
    regla_B3,
    regla_B4,
]


def validar(texto: str) -> List[Flag]:
    flags: List[Flag] = []
    for regla in TODAS_LAS_REGLAS:
        try:
            flags.extend(regla(texto))
        except Exception as exc:  # una regla no debe tumbar el resto
            flags.append(Flag(regla.__name__, "baja", f"[error interno en la regla: {exc}]"))
    return flags


def informe_validacion(texto: str) -> str:
    flags = validar(texto)
    if not flags:
        return "✓ Sin incidencias. El informe pasa las reglas comprobables de codo."
    orden = {"alta": 0, "media": 1, "baja": 2}
    flags.sort(key=lambda f: orden.get(f.gravedad, 3))
    out = [f"Se encontraron {len(flags)} incidencia(s):", ""]
    out.extend(str(flag) for flag in flags)
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            texto = fh.read()
    else:
        texto = sys.stdin.read()
    print(informe_validacion(texto))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
