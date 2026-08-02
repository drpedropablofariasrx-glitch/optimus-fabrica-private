#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validador determinista de TC de torax por tipo de estudio y contexto."""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import List


STUDY_TYPES = {"tc_torax", "angio_tc_tep", "cribado_pulmonar", "torax_abdomen_pelvis"}
CLINICAL_CONTEXTS = {"general", "oncologico", "infeccioso", "trauma", "postquirurgico"}
PROTOCOLS = {"sin_contraste", "con_contraste", "angiografico_pulmonar", "baja_dosis", "tap"}


@dataclass
class Flag:
    regla: str
    gravedad: str
    mensaje: str
    fragmento: str = ""
    bloquea_gold: bool = False


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _ventana(texto: str, pos: int, radio: int = 90) -> str:
    return texto[max(0, pos - radio): pos + radio]


def _bloque(texto: str, nombre: str) -> str:
    n = _norm(texto)
    encabezados = {
        "exploracion": r"exploracion\s*:",
        "hallazgos": r"hallazgos\s*:",
        "impresion": r"impresion diagnostica\s*:",
    }
    patron = encabezados.get(nombre)
    if not patron:
        return ""
    inicio = re.search(patron, n)
    if not inicio:
        return ""
    fin = len(texto)
    for otro in encabezados.values():
        candidato = re.search(otro, n[inicio.end():])
        if candidato:
            fin = min(fin, inicio.end() + candidato.start())
    return texto[inicio.end():fin]


def _metadata(metadata=None):
    data = dict(metadata or {})
    return {
        "study_type": data.get("study_type") or "tc_torax",
        "clinical_context": data.get("clinical_context") or "general",
        "protocol": data.get("protocol") or "sin_contraste",
        "contrast": data.get("contrast"),
        "comparison_available": bool(data.get("comparison_available", False)),
        "anatomical_scope": data.get("anatomical_scope") or "torax",
    }


def regla_T1(texto: str, meta: dict) -> List[Flag]:
    if meta["study_type"] not in STUDY_TYPES:
        return [Flag("T1", "alta", "study_type toracico no reconocido.", bloquea_gold=True)]
    if meta["clinical_context"] not in CLINICAL_CONTEXTS:
        return [Flag("T1", "alta", "clinical_context toracico no reconocido.", bloquea_gold=True)]
    if meta["protocol"] not in PROTOCOLS:
        return [Flag("T1", "alta", "protocol toracico no reconocido.", bloquea_gold=True)]
    return []


def regla_T2(texto: str, meta: dict) -> List[Flag]:
    esperados = {
        "angio_tc_tep": "angiografico_pulmonar",
        "cribado_pulmonar": "baja_dosis",
        "torax_abdomen_pelvis": "tap",
    }
    esperado = esperados.get(meta["study_type"])
    if esperado and meta["protocol"] != esperado:
        return [Flag("T2", "alta", f"{meta['study_type']} requiere protocolo {esperado}.", bloquea_gold=True)]
    return []


def regla_T3(texto: str, meta: dict) -> List[Flag]:
    if meta["study_type"] != "angio_tc_tep":
        return []
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    if not re.search(r"arterias? pulmonares?|arterial pulmonar|defecto de replecion|tep\b|embol", hallazgos):
        return [Flag("T3", "alta", "Angio-TC TEP sin valoracion de arterias pulmonares.", bloquea_gold=True)]
    return []


def regla_T4(texto: str, meta: dict) -> List[Flag]:
    if meta["study_type"] != "torax_abdomen_pelvis":
        return []
    hallazgos = _norm(_bloque(texto, "hallazgos")) or _norm(texto)
    territorios = {
        "torax": r"pulmon|pleura|mediast|torax",
        "abdomen": r"higado|bazo|rinon|suprarrenal|abdomen",
        "pelvis": r"vejiga|pelvis|prostata|utero|ovari",
    }
    faltan = [nombre for nombre, patron in territorios.items() if not re.search(patron, hallazgos)]
    if faltan:
        return [Flag("T4", "alta", "TAP sin valoracion de: " + ", ".join(faltan) + ".", bloquea_gold=True)]
    return []


def regla_T5(texto: str, meta: dict) -> List[Flag]:
    n = _norm(texto)
    if re.search(r"pielotc|urolitiasis|bosniak|o-rads|li-rads", n):
        return [Flag("T5", "alta", "El informe toracico contiene una macro o criterio incompatible.", bloquea_gold=True)]
    return []


def regla_T6(texto: str, meta: dict) -> List[Flag]:
    if meta["study_type"] != "angio_tc_tep":
        return []
    n = _norm(texto)
    if re.search(r"opacificacion suboptima|contraste suboptimo|calidad suboptima", n):
        return [Flag("T6", "media", "Calidad angiografica suboptima en Angio-TC TEP.")]
    m = re.search(r"vd\s*/\s*vi[^0-9]{0,15}(\d[.,]\d+)", n)
    if m and re.search(r"sobrecarga.{0,20}derech|hipertension pulmonar", n):
        ratio = float(m.group(1).replace(",", "."))
        if ratio <= 0.9:
            return [Flag("T6", "media", f"VD/VI={ratio} no es coherente con sobrecarga derecha afirmada.")]
    return []


def regla_T7(texto: str, meta: dict) -> List[Flag]:
    n = _norm(texto)
    if "lung-rads" in n and meta["study_type"] != "cribado_pulmonar":
        return [Flag("T7", "baja", "Lung-RADS solo corresponde a un protocolo real de cribado pulmonar.")]
    if "recist" in n and meta["clinical_context"] != "oncologico":
        return [Flag("T7", "baja", "RECIST no debe afirmarse fuera de contexto oncologico.")]
    if meta["study_type"] == "cribado_pulmonar" and "lung-rads" in n and not re.search(r"nodul|nodule", n):
        return [Flag("T7", "baja", "Lung-RADS consignado sin datos nodulares suficientes en el informe.")]
    return []


def regla_T8(texto: str, meta: dict) -> List[Flag]:
    if meta["comparison_available"]:
        return []
    if meta["clinical_context"] not in {"oncologico", "postquirurgico"}:
        return []
    n = _norm(texto)
    m = re.search(r"estable|progresion|respuesta|mejoria|empeoramiento", n)
    if m:
        return [Flag("T8", "baja", "Lenguaje evolutivo sin comparacion disponible declarada.", _ventana(texto, m.start()))]
    return []


TODAS_LAS_REGLAS = [regla_T1, regla_T2, regla_T3, regla_T4, regla_T5, regla_T6, regla_T7, regla_T8]


def validar(texto: str, metadata=None) -> List[Flag]:
    meta = _metadata(metadata)
    flags = []
    for regla in TODAS_LAS_REGLAS:
        try:
            flags.extend(regla(texto, meta))
        except Exception as exc:
            flags.append(Flag(regla.__name__, "baja", f"[error interno en la regla: {exc}]", bloquea_gold=True))
    return flags


if __name__ == "__main__":
    print("\n".join(flag.mensaje for flag in validar(sys.stdin.read())))
