#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_tobillo_pie.py
========================
Validador determinista para informes de RM/TC de tobillo, retropié,
mediopié, pie y antepié.

Extraído de las preferencias y correcciones repetidas del corpus
Tobillo-pie.txt. Mantiene la filosofía de los demás validadores OPTIMUS:
no corrige, solo devuelve flags trazables y priorizados.

Uso:
    python validador_tobillo_pie.py informe.txt

Desde código:
    from validador_tobillo_pie import validar, informe_validacion
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


def _tipo_estudio(texto: str) -> str:
    exploracion = _norm(_bloque(texto, "exploracion"))
    cabecera = exploracion or _norm(texto[:350])
    if "dedo" in cabecera or "articulacion concreta" in cabecera:
        return "focal"
    if "antepie" in cabecera:
        return "antepie"
    if "pie y tobillo" in cabecera or "tobillo y pie" in cabecera or "pie-tobillo" in cabecera:
        return "pie_tobillo"
    if "mediopie" in cabecera:
        return "mediopie"
    if "retropie" in cabecera:
        return "retropie"
    if "tobillo" in cabecera:
        return "tobillo"
    if "pie" in cabecera:
        return "pie"
    return "otro"


def _modalidad(texto: str) -> str:
    exploracion = _norm(_bloque(texto, "exploracion"))
    cabecera = exploracion or _norm(texto[:350])
    if "ecografia" in cabecera or re.search(r"\beco\b", cabecera):
        return "ecografia"
    if re.search(r"\btc\b|tomografia", cabecera):
        return "tc"
    if re.search(r"\brm\b|resonancia", cabecera):
        return "rm"
    return "otra"


def _es_rm_de_campo_completo(texto: str) -> bool:
    exploracion = _norm(_bloque(texto, "exploracion"))
    return _modalidad(texto) == "rm" and not re.search(r"\bestudio\s+focal\b|\bfocal\s+de\b", exploracion)


# ----------------------------------------------------------------------
# REGLAS DURAS
# ----------------------------------------------------------------------

def regla_D1(texto: str) -> List[Flag]:
    """No filtrar edad, sexo u hospital al cuerpo del informe."""
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
    """No usar 'distensión bursátil'; usar 'distensión de la bursa intermetatarsiana'."""
    flags: List[Flag] = []
    n = _norm(texto)
    for m in re.finditer(r"distension\s+bursatil|cambios\s+bursatiles|\bbursatil\b", n):
        flags.append(Flag(
            "D2",
            "media",
            "Terminología no preferida: sustituir 'bursátil' por 'distensión de la bursa intermetatarsiana' o 'bursitis intermetatarsiana', según corresponda.",
            _ventana(texto, m.start(), 70),
        ))
    return flags


def regla_D3(texto: str) -> List[Flag]:
    """Respetar la causalidad: os trigonum con signos de pinzamiento posterior."""
    flags: List[Flag] = []
    n = _norm(texto)
    patrones_invertidos = [
        r"pinzamiento posterior[^.\n]{0,45}(?:con|asociado a)\s+(?:un\s+)?os\s+trigonum",
        r"pinzamiento posterior[^.\n]{0,45}(?:con|asociado a)\s+(?:un\s+)?proceso\s+de\s+stieda",
    ]
    for pat in patrones_invertidos:
        m = re.search(pat, n)
        if m:
            flags.append(Flag(
                "D3",
                "baja",
                "Causalidad invertida. Preferir 'os trigonum/proceso de Stieda con signos de pinzamiento posterior'.",
                _ventana(texto, m.start(), 80),
            ))
    return flags


def regla_D4(texto: str) -> List[Flag]:
    """TAGS y DATASET_ENTRY no deben aparecer en el bloque copiable a PACS."""
    flags: List[Flag] = []
    n = _norm(texto)
    if re.search(r"\btags?\s*[:/]", n) or "dataset_entry" in n or "dataset entry" in n:
        flags.append(Flag(
            "D4",
            "media",
            "El texto contiene TAGS/DATASET_ENTRY visibles; deben permanecer fuera del informe PACS.",
        ))
    return flags


def regla_D5(texto: str) -> List[Flag]:
    """La impresión no debe repetir medidas de fascitis plantar salvo necesidad clínica."""
    flags: List[Flag] = []
    impresion = _norm(_bloque(texto, "impresion"))
    if not impresion:
        return flags
    for m in re.finditer(r"fascitis plantar[^.\n]{0,90}\d+(?:[.,]\d+)?\s*(?:mm|cm)", impresion):
        flags.append(Flag(
            "D5",
            "baja",
            "La impresión repite medidas de la fascia plantar. Preferir una conclusión resumida: 'Hallazgos compatibles con fascitis plantar' y describir aparte una rotura si existe.",
            _ventana(_bloque(texto, "impresion"), m.start(), 75),
        ))
    return flags


# ----------------------------------------------------------------------
# REGLAS BLANDAS COMPROBABLES
# ----------------------------------------------------------------------

def regla_B1(texto: str) -> List[Flag]:
    """Plantilla de antepié: valorar Lisfranc de forma explícita."""
    flags: List[Flag] = []
    tipo = _tipo_estudio(texto)
    if not _es_rm_de_campo_completo(texto) or tipo not in {"antepie", "mediopie", "pie", "pie_tobillo"}:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    if "lisfranc" not in hallazgos:
        flags.append(Flag(
            "B1",
            "baja",
            "Estudio de pie/antepié sin valoración explícita del complejo ligamentario de Lisfranc.",
        ))
    return flags


def regla_B2(texto: str) -> List[Flag]:
    """Checklist básico de RM de tobillo."""
    flags: List[Flag] = []
    if not _es_rm_de_campo_completo(texto) or _tipo_estudio(texto) not in {"tobillo", "pie_tobillo"}:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)

    grupos = {
        "tendón de Aquiles": ["aquiles", "aquileo"],
        "tendones peroneos": ["peroneos", "peroneo largo", "peroneo corto"],
        "tibial posterior": ["tibial posterior"],
        "flexor largo del primer dedo": ["flexor largo del primer dedo", "flexor largo del hallux", "flh"],
        "flexor largo de los dedos": ["flexor largo de los dedos", "fld"],
        "complejo lateral": ["complejo lateral", "peroneoastragalino anterior", "lpaa"],
        "complejo deltoideo": ["deltoideo"],
        "seno del tarso": ["seno del tarso"],
        "fascia plantar": ["fascia plantar"],
    }
    faltan = [nombre for nombre, claves in grupos.items() if not any(c in hallazgos for c in claves)]
    if faltan:
        flags.append(Flag(
            "B2",
            "baja",
            "Checklist de tobillo incompleto. Falta valorar: " + ", ".join(faltan) + ".",
        ))
    return flags


def regla_B3(texto: str) -> List[Flag]:
    """Checklist básico de antepié/pie."""
    flags: List[Flag] = []
    if not _es_rm_de_campo_completo(texto) or _tipo_estudio(texto) not in {"antepie", "pie", "pie_tobillo"}:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)

    grupos = {
        "fracturas o lesiones por estrés": ["fracturas", "lesiones por estres", "fractura por estres"],
        "placas plantares": ["placas plantares", "placa plantar"],
        "neuroma de Morton": ["neuroma de morton", "mort  on", "fibrosis perineural"],
        "bursas intermetatarsianas": ["bursa intermetatars", "bursitis intermetatars"],
        "sesamoideos": ["sesamoid"],
        "tendones flexores/extensores": ["tendinopatia flex", "tendones flexores", "tendones extensores", "flexora o extensora"],
        "almohadilla plantar": ["almohadilla plantar", "grasa plantar"],
    }
    faltan = [nombre for nombre, claves in grupos.items() if not any(c in hallazgos for c in claves)]
    if faltan:
        flags.append(Flag(
            "B3",
            "baja",
            "Checklist de pie/antepié incompleto. Falta valorar: " + ", ".join(faltan) + ".",
        ))
    return flags


def regla_B4(texto: str) -> List[Flag]:
    """Si se menciona el complejo lateral lesionado, comprobar LPAA/LPC/LPAP."""
    flags: List[Flag] = []
    if not _es_rm_de_campo_completo(texto) or _tipo_estudio(texto) not in {"tobillo", "pie_tobillo"}:
        return flags
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    hay_lesion_lateral = bool(re.search(r"rotura|lesion|fibrocicatricial|adelgazamiento|elongacion", hallazgos)) and (
        "peroneoastragalino" in hallazgos or "complejo lateral" in hallazgos or "lpaa" in hallazgos
    )
    if not hay_lesion_lateral:
        return flags

    componentes = {
        "LPAA": ["peroneoastragalino anterior", "lpaa"],
        "LPC": ["peroneocalcaneo", "lpc"],
        "LPAP": ["peroneoastragalino posterior", "lpap"],
    }
    faltan = [nombre for nombre, claves in componentes.items() if not any(c in hallazgos for c in claves)]
    if faltan:
        flags.append(Flag(
            "B4",
            "media",
            "Lesión del complejo lateral sin revisar todos sus componentes. Falta mencionar: " + ", ".join(faltan) + ".",
        ))
    return flags


def regla_B5(texto: str) -> List[Flag]:
    """La impresión no debe incluir una lista de hallazgos normales."""
    flags: List[Flag] = []
    impresion = _norm(_bloque(texto, "impresion"))
    if not impresion:
        return flags
    patrones = [
        r"resto de tendones.*(?:normal|conservad|integ)",
        r"resto de ligamentos.*(?:normal|conservad|integ)",
        r"sin otros hallazgos",
        r"fascia plantar.*normal",
        r"seno del tarso.*normal",
    ]
    for pat in patrones:
        m = re.search(pat, impresion)
        if m:
            flags.append(Flag(
                "B5",
                "baja",
                "La impresión diagnóstica incluye hallazgos normales; debería limitarse a la patología relevante.",
                _ventana(_bloque(texto, "impresion"), m.start(), 70),
            ))
            break
    return flags


def regla_B6(texto: str) -> List[Flag]:
    """Una RM sin carga no excluye por si sola la inestabilidad dinamica de Lisfranc."""
    flags: List[Flag] = []
    n = _norm(texto)
    if "lisfranc" in n and "sin carga" in n and re.search(r"(?:descarta|excluye|sin)\s+inestabilidad", n):
        flags.append(Flag(
            "B6", "baja",
            "La ausencia de diastasis en un estudio sin carga no excluye inestabilidad dinamica de Lisfranc.",
        ))
    return flags


def regla_B7(texto: str) -> List[Flag]:
    """Evita etiquetar como tenosinovitis el liquido fisiologico aislado del FHL."""
    flags: List[Flag] = []
    n = _norm(texto)
    patron = r"(?:flexor largo del primer dedo|flexor largo del hallux|fhl)[^.\n]{0,100}(?:liquido fisiologico)[^.\n]{0,100}tenosinovitis|tenosinovitis[^.\n]{0,100}(?:flexor largo del primer dedo|flexor largo del hallux|fhl)[^.\n]{0,100}(?:liquido fisiologico)"
    m = re.search(patron, n)
    negativo = r"sin\s+(?:signos\s+de\s+)?tenosinovitis|no\s+(?:hay\s+)?tenosinovitis"
    if m and not re.search(r"engrosamiento|alteracion de senal|sinovial|inflamatori", m.group(0)) and not re.search(negativo, m.group(0)):
        flags.append(Flag(
            "B7", "baja",
            "Tenosinovitis del flexor largo del primer dedo basada solo en liquido fisiologico; revisar si hay cambios tendinosos o inflamatorios asociados.",
            _ventana(texto, m.start(), 90),
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
    regla_B5,
    regla_B6,
    regla_B7,
]


def validar(texto: str) -> List[Flag]:
    flags: List[Flag] = []
    for regla in TODAS_LAS_REGLAS:
        try:
            flags.extend(regla(texto))
        except Exception as exc:
            flags.append(Flag(regla.__name__, "baja", f"[error interno en la regla: {exc}]"))
    return flags


def informe_validacion(texto: str) -> str:
    flags = validar(texto)
    if not flags:
        return "✓ Sin incidencias. El informe pasa las reglas comprobables de tobillo-pie."
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
