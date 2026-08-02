#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validador_abdomen.py
====================
Validador determinista para informes de TC abdomen-pelvis.

Codifica las 12 reglas DURAS extraídas de REGLAS_ABDOMEN_MAESTRAS.md
(un año de correcciones reales en ChatGPT). No es IA: es una checklist
ejecutable que revisa siempre lo mismo y marca lo que incumple una regla.

Cada chequeo devuelve cero o más "flags". Un flag = una regla incumplida,
con el id de la regla, la gravedad y un mensaje explicativo.

Uso:
    python3 validador_abdomen.py informe.txt
    # o desde código:
    from validador_abdomen import validar
    flags = validar(texto_informe)

Filosofía:
    - Preferir FALSOS POSITIVOS (avisar de más) a falsos negativos.
      Un flag que no tocaba se ignora en 2 segundos; un error que pasa
      contamina el dataset.
    - Cada flag cita la regla (D1..D12) para trazabilidad.
    - El validador NO corrige: solo señala. La decisión es del radiólogo.
"""

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional


# ----------------------------------------------------------------------
# Estructura de un flag
# ----------------------------------------------------------------------
@dataclass
class Flag:
    regla: str        # id de la regla, p.ej. "D8"
    gravedad: str     # "alta" | "media" | "baja"
    mensaje: str      # explicación legible
    fragmento: str = ""  # trozo del informe que disparó el flag

    def __str__(self):
        frag = f"  →  «{self.fragmento.strip()[:90]}»" if self.fragmento else ""
        return f"[{self.regla}|{self.gravedad}] {self.mensaje}{frag}"


# ----------------------------------------------------------------------
# Utilidades de parsing
# ----------------------------------------------------------------------
def _norm(texto: str) -> str:
    """Minúsculas y sin acentos, para emparejar términos clínicos."""
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t


def _bloque(texto: str, nombre: str) -> str:
    """
    Devuelve el contenido de un bloque del informe (p.ej. 'impresion',
    'hallazgos', 'datos clinicos'). Heurística por encabezados.
    """
    n = _norm(texto)
    encabezados = {
        "datos clinicos": r"datos cl[ií]nicos\s*:",
        "hallazgos": r"hallazgos\s*:",
        "impresion": r"impresi[oó]n diagn[oó]stica\s*:",
        "interpretacion": r"interpretaci[oó]n global\s*:",
    }
    pat = encabezados.get(nombre)
    if not pat:
        return ""
    m = re.search(pat, n)
    if not m:
        return ""
    inicio = m.end()
    # fin = siguiente encabezado conocido, o fin de texto
    fin = len(texto)
    for otra_pat in encabezados.values():
        m2 = re.search(otra_pat, n[inicio:])
        if m2:
            fin = min(fin, inicio + m2.start())
    return texto[inicio:fin]


# extrae pares (valor_UH, contexto) -> busca números seguidos de UH/HU
_RE_UH = re.compile(r"(-?\d{1,4}(?:[.,]\d+)?)\s*(?:uh|hu|unidades?\s+hounsfield)", re.I)
# extrae medidas en mm
_RE_MM = re.compile(r"(\d{1,4}(?:[.,]\d+)?)\s*mm", re.I)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _ventana(texto: str, pos: int, radio: int = 80) -> str:
    return texto[max(0, pos - radio): pos + radio]


# ======================================================================
#  REGLAS DURAS — cada función recibe el texto y devuelve List[Flag]
# ======================================================================

# ---------- A.1  FORMATO Y SINTAXIS ----------

_NUM_PALABRAS = [
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
    "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
    "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte",
    "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta",
    "noventa", "cien", "ciento", "mil",
]

def regla_D1(texto: str) -> List[Flag]:
    """Números en formato numérico, no en palabras (en contexto de medida)."""
    flags = []
    n = _norm(texto)
    # buscar palabra-número seguida (cerca) de una unidad o de 'milimetros'
    for palabra in _NUM_PALABRAS:
        for m in re.finditer(rf"\b{palabra}\b", n):
            cola = n[m.end(): m.end() + 30]
            if re.search(r"(mil[ií]metros?|cent[ií]metros?|\bmm\b|\bcm\b|por\s+\w+\s+(mil|cent))", cola):
                flags.append(Flag(
                    "D1", "media",
                    f"Posible medida escrita en palabras ('{palabra}...'). Usar formato numérico (p.ej. 44 mm).",
                    _ventana(texto, m.start(), 50)))
                break  # un flag por palabra basta
    return flags


def regla_D2(texto: str) -> List[Flag]:
    """Porcentajes con símbolo %; medidas con unidad explícita."""
    flags = []
    n = _norm(texto)
    # 'por ciento' o 'porciento' en vez de %
    for m in re.finditer(r"\bpor\s*ciento\b|\bporciento\b", n):
        flags.append(Flag("D2", "baja",
                          "Porcentaje en palabras; usar el símbolo %.",
                          _ventana(texto, m.start(), 40)))
    # número 'suelto' que parece medida sin unidad es difícil de detectar sin
    # falsos positivos; se omite deliberadamente para no ruido.
    return flags


def regla_D3(texto: str) -> List[Flag]:
    """Datos clínicos en minúsculas (sin MAYÚSCULAS sostenidas)."""
    flags = []
    dc = _bloque(texto, "datos clinicos")
    if not dc:
        return flags
    # siglas médicas legítimas que NO son 'mayúsculas por descuido'
    siglas_ok = {"SIBO", "TC", "RM", "ITU", "ERC", "IRC", "EPOC", "VIH", "HTA",
                 "DM", "IAM", "TEP", "TVP", "FA", "EII", "RGE", "HBP", "PSA",
                 "IMC", "FID", "FII", "HDA", "HDB", "CU", "ACO", "IPMN"}
    for m in re.finditer(r"[A-ZÁÉÍÓÚÑ]{2,}", dc):
        token = m.group(0)
        if token in siglas_ok:
            continue
        if len(token) >= 4:  # racha larga = dictado sin normalizar
            flags.append(Flag("D3", "media",
                              "Mayúsculas sostenidas en Datos clínicos; normalizar a minúsculas.",
                              token))
            break
    return flags


def regla_D4(texto: str) -> List[Flag]:
    """No incluir 'el paciente se realiza...' en Datos clínicos."""
    flags = []
    dc = _norm(_bloque(texto, "datos clinicos"))
    if re.search(r"se realiza\b|paciente se realiza|se le realiza", dc):
        flags.append(Flag("D4", "media",
                          "Coletilla 'el paciente se realiza...' en Datos clínicos (es contexto del estudio, no dato clínico)."))
    return flags


def regla_D6(texto: str) -> List[Flag]:
    """Impresión: cada idea en línea independiente (no todo en un párrafo)."""
    flags = []
    imp = _bloque(texto, "impresion").strip()
    if not imp:
        return flags
    lineas = [l for l in imp.splitlines() if l.strip()]
    # heurística: si la impresión es una sola línea muy larga con varias frases
    if len(lineas) == 1 and imp.count(".") >= 3 and len(imp) > 160:
        flags.append(Flag("D6", "baja",
                          "Impresión en bloque; separar cada conclusión en línea independiente.",
                          imp[:90]))
    return flags


# ---------- A.2  UMBRALES CUANTITATIVOS (núcleo del validador) ----------

def regla_D8(texto: str) -> List[Flag]:
    """
    Esteatosis hepática: si se afirma esteatosis, comprobar coherencia con UH.
    Si hígado > bazo (o hígado >= 40 UH sin que sea < bazo-10), la esteatosis
    es incoherente. Y viceversa: si hígado claramente < bazo-10 o < 40 y se
    NIEGA esteatosis, también se marca.
    """
    flags = []
    n = _norm(texto)
    afirma = bool(re.search(r"esteatosis hep|h[ií]gado graso|hepatoesteatosis", n)) and \
             not re.search(r"no\s+(hay|se observa|existe|presenta)\s+esteatosis|sin\s+esteatosis|no esteatosis", n)
    niega = bool(re.search(r"no\s+(hay|se observa|existe|presenta)\s+esteatosis|sin\s+esteatosis|no esteatosis", n))

    # intentar extraer UH de hígado y bazo
    h = _uh_de_organo(texto, ["higado", "hepatic"])
    b = _uh_de_organo(texto, ["bazo", "espleni"])

    if h is not None and b is not None:
        diferencia = h - b
        es_esteatosis = (h < 40) or (diferencia <= -10)
        if afirma and not es_esteatosis:
            flags.append(Flag("D8", "alta",
                f"Se afirma esteatosis pero hígado {h:.0f} UH vs bazo {b:.0f} UH (dif {diferencia:+.0f}). "
                f"Criterio: hígado <40 o hígado<=bazo-10. Aquí NO se cumple."))
        if niega and es_esteatosis:
            flags.append(Flag("D8", "alta",
                f"Se niega esteatosis pero hígado {h:.0f} UH vs bazo {b:.0f} UH (dif {diferencia:+.0f}) SÍ cumple criterio."))
    elif afirma and h is None:
        flags.append(Flag("D8", "media",
            "Se afirma esteatosis sin consignar UH hepáticas objetivas. Aportar dato (hígado <40 o hígado<=bazo-10)."))
    return flags


def regla_D9(texto: str) -> List[Flag]:
    """Lipoma: debe tener densidad grasa (-120 a -30 UH). Si se etiqueta lipoma
       con UH fuera de ese rango, marcar."""
    flags = []
    n = _norm(texto)
    # \blipoma\b con frontera, y excluir 'lipomatos*' (eso es D10, no D9)
    for m in re.finditer(r"\blipoma\b(?!tos)", n):
        ventana = _ventana(n, m.start(), 120)
        uhs = [_num(x) for x in _RE_UH.findall(ventana)]
        for uh in uhs:
            if uh > -30:  # no es grasa
                flags.append(Flag("D9", "alta",
                    f"Etiquetado 'lipoma' con densidad {uh:.0f} UH (no grasa). "
                    f"Lipoma = -120 a -30 UH; ~3 UH es líquido simple.",
                    _ventana(texto, m.start(), 80)))
                break
    return flags


def regla_D10(texto: str) -> List[Flag]:
    """Páncreas lipomatoso: 40-60 UH es normal. No diagnosticar lipomatosis en rango normal."""
    flags = []
    n = _norm(texto)
    if re.search(r"p[aá]ncreas? lipomatos|lipomatosis pancre|esteatosis pancre", n):
        upanc = _uh_de_organo(texto, ["pancrea"])
        if upanc is not None and 40 <= upanc <= 60:
            flags.append(Flag("D10", "alta",
                f"Lipomatosis pancreática con {upanc:.0f} UH (rango normal 40-60). No cumple criterio."))
    return flags


def regla_D11(texto: str) -> List[Flag]:
    """Realce verdadero: diferencia <10 UH entre fases = sin realce.
       Si se afirma realce y se citan dos fases con dif <10, marcar."""
    flags = []
    n = _norm(texto)
    if not re.search(r"realce|realza|capta|captaci[oó]n", n):
        return flags
    # buscar menciones de fases con UH: sin contraste / arterial / portal / tardia
    fases = {}
    for clave, pats in {
        "sin": [r"sin contraste", r"basal", r"fase simple"],
        "arterial": [r"arterial", r"fase hepatica", r"portal"],
        "tardia": [r"tard[ií]a", r"equilibrio", r"diferido"],
    }.items():
        for p in pats:
            m = re.search(p + r"[^.]{0,40}?(-?\d{1,4})\s*uh", n)
            if m:
                fases[clave] = _num(m.group(1))
                break
    if len(fases) >= 2:
        vals = list(fases.values())
        if max(vals) - min(vals) < 10 and re.search(r"realza|realce (?!ausente)|capta", n):
            flags.append(Flag("D11", "media",
                f"Se sugiere realce pero diferencia entre fases {max(vals)-min(vals):.0f} UH (<10 = sin realce verdadero). "
                f"Fases detectadas: {fases}"))
    return flags


def regla_D12(texto: str) -> List[Flag]:
    """Aorta abdominal: normal <30 mm. Marcar incoherencias ectasia/aneurisma/normal."""
    flags = []
    n = _norm(texto)
    # buscar 'aorta ... NN mm'
    for m in re.finditer(r"aorta[^.]{0,60}?(\d{1,3})\s*mm", n):
        d = int(m.group(1))
        ctx = _ventana(n, m.start(), 120)
        dice_aneurisma = "aneurisma" in ctx
        dice_ectasia = "ectasia" in ctx
        dice_normal = bool(re.search(r"normal|conservad|sin dilatac", ctx))
        if d >= 30 and not dice_aneurisma:
            flags.append(Flag("D12", "alta",
                f"Aorta abdominal de {d} mm (>=30) sin etiquetar aneurisma.",
                _ventana(texto, m.start(), 80)))
        if d < 25 and (dice_ectasia or dice_aneurisma):
            flags.append(Flag("D12", "media",
                f"Aorta de {d} mm (<25, normal) etiquetada como ectasia/aneurisma.",
                _ventana(texto, m.start(), 80)))
    return flags


def regla_D7(texto: str) -> List[Flag]:
    """
    Pie 'Informado por / Validado por': incluir SI Y SOLO SI el informe tiene
    marcadores de formato clínico chileno (FONASA, ID paciente, previsión, RUT).
    Regla UNIVERSAL — misma lógica en abdomen, lumbar, cervical y tórax.
    Corregida: antes se creía que dependía del input; en realidad es detectable
    desde el propio texto de salida.
    """
    flags = []
    n = _norm(texto)
    marcadores = [r"fonasa", r"id paciente", r"previsi[oó]n\s*:", r"rut\s*:"]
    es_chile = any(re.search(p, n) for p in marcadores)
    tiene_pie = "validado por" in n
    if es_chile and not tiene_pie:
        flags.append(Flag("D7", "baja",
            "Formato clínico chileno detectado pero falta el pie 'Informado por / Validado por'."))
    if not es_chile and tiene_pie:
        flags.append(Flag("D7", "baja",
            "El informe incluye 'Informado por / Validado por' sin marcadores de formato "
            "clínico chileno; en ese caso no debería incluirse."))
    return flags


# ----------------------------------------------------------------------
# Helper: extraer UH asociadas a un órgano por proximidad
# ----------------------------------------------------------------------
def _uh_de_organo(texto: str, claves: List[str]) -> Optional[float]:
    """
    Busca la primera mención de cualquiera de las 'claves' (raíces de órgano)
    y devuelve el valor UH más cercano dentro de una ventana. None si no hay.
    """
    n = _norm(texto)
    mejor = None
    for clave in claves:
        for m in re.finditer(re.escape(clave), n):
            ventana = n[m.start(): m.start() + 90]
            uhs = _RE_UH.findall(ventana)
            if uhs:
                return _num(uhs[0])
    return mejor


# ======================================================================
#  ORQUESTADOR
# ======================================================================
TODAS_LAS_REGLAS = [
    regla_D1, regla_D2, regla_D3, regla_D4, regla_D6, regla_D7,  # A.1 formato
    regla_D8, regla_D9, regla_D10, regla_D11, regla_D12,  # A.2 umbrales
]
# Nota: D5 (asumir normales los no mencionados) sigue sin ser verificable
# sobre el output aislado sin el input; se gestiona en el pipeline, no aquí.


def validar(texto: str) -> List[Flag]:
    """Ejecuta todas las reglas duras y devuelve la lista de flags."""
    flags: List[Flag] = []
    for regla in TODAS_LAS_REGLAS:
        try:
            flags.extend(regla(texto))
        except Exception as e:  # un fallo en una regla no debe tumbar el resto
            flags.append(Flag(regla.__name__, "baja",
                             f"[error interno en la regla: {e}]"))
    return flags


def informe_validacion(texto: str) -> str:
    """Salida legible para humano."""
    flags = validar(texto)
    if not flags:
        return "✓ Sin incidencias. El informe pasa las 10 reglas duras comprobables."
    orden = {"alta": 0, "media": 1, "baja": 2}
    flags.sort(key=lambda f: orden.get(f.gravedad, 3))
    out = [f"Se encontraron {len(flags)} incidencia(s):", ""]
    for f in flags:
        out.append(str(f))
    return "\n".join(out)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            texto = fh.read()
    else:
        texto = sys.stdin.read()
    print(informe_validacion(texto))
