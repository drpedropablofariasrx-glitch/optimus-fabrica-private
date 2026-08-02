#!/usr/bin/env python3
"""Capturador local y supervisado de informes finales desde Vue PACS.

El modo de captura requiere pywinauto, usa exclusivamente el menu
"Ver informes" y nunca ejecuta acciones de edicion, firma o eliminacion.
El parser y las pruebas no necesitan Vue PACS ni dependencias externas.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "datasets"
    / "private"
    / "vuepacs_import"
    / "pendientes_revision.jsonl"
)
DEFAULT_WINDOW_PATTERN = r"(?i).*vue.*pacs.*"
REPORT_MENU_NAME = "Ver informes"
# Inicial de REPORT_MENU_NAME. Verificado sobre el menu contextual real de
# Vue PACS: "Ver informes" es el UNICO item que empieza por esta letra, por
# lo que escribirla con el menu abierto no puede activar otro comando. Si
# alguna vez se añade otro item con la misma inicial, esta ruta deja de ser
# segura y debe retirarse.
REPORT_MENU_INITIAL = REPORT_MENU_NAME[0].lower()
# Intentos de copia por teclado (clic para enfocar + Ctrl+A + Ctrl+C) antes
# de recurrir al menu contextual del panel, mas lento pero ya comprobado.
COPY_KEYBOARD_ATTEMPTS = 3
SELECT_ALL_MENU_NAME = "Seleccionar todo"
COPY_MENU_NAME = "Copiar"
STOP_KEY = 0x7B  # F12
VISUAL_MATCH_THRESHOLD = 0.90
REPORT_MENU_TEMPLATE_PATHS = (
    ROOT / "scripts" / "assets" / "vuepacs_ver_informes.png",
    ROOT / "scripts" / "assets" / "vuepacs_ver_informes_text.png",
)
REPORT_WINDOW_TITLEBAR_TEMPLATE_PATH = (
    ROOT / "scripts" / "assets" / "vuepacs_explorador_informes_titlebar.png"
)
GA_ROOT = 2  # Win32 GetAncestor: raiz de la ventana (nivel superior)
REPORT_MENU_TEMPLATE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAOYAAAAiCAYAAABLE6UZAAAAAXNSR0IArs4c6QAAAARn"
    "QU1BAACxjwv8YQUAAAAJcEhZcwAAFiUAABYlAUlSJPAAAAamSURBVHhe7ZxbbBRVGMc3"
    "SH3yQonUfTC+8AZP+lww9UEeTINBI7xYEjBSGkUUaUFD0lYSIgWbNNGWa0sJxRZr0cWI"
    "xJUGLMULbWm9kEDi8kZfqJc0hO1u/+acnTl79lx2ZodlWXe/SX7Z9pwzc74z8/3mnJmm"
    "GxoZGQFBEMVFaPr2bRQC1tns7Czi8ThBEB6QmARRhJCYBFGEkJgEUYRwMS+OjqLz4CG0"
    "d3Twz9ORCM5Fo7gei2mCBYXEJAj/cDEbd+7E+g3t6D3Rx9myrZFT/fwLnLoNr/M2e9ra"
    "hLiqeF6QmAThHyFma+sU+DbzJxA7n/p0tquTU5zB01/io30f8/aqeF6QmAThH13M4Q+A"
    "5lCanmeFoK6kJCZB3F90MS/vf4BiXkNTTRuWPN+Gqr3XDPUmpnG43tmn/hJuaPX3mZFI3"
    "vu+0d/Nj8mPW9ONwzG9DVHa6GK6S9k7M6mfb40XUEwp0WsiiKp1JmKXUFvzABM4z2LK"
    "UpKY5Ysu5sTR1CzJ6HoqNWuyT/b72Yb7L6Y0azaNqHU6biLnS4wHS3r2r+2fNtQT5YIu"
    "pm1jM+it8QKIGUd0r9/lbKklcm43JaJ08S+msxVCTN/L01yXvUUPiUmk0MSc+HUex08n"
    "cPJsHKeG4xgavYuhy3fx/dQcJm8mCiOmz5nQe2ZNJ7qMMekznhWlF0pe0tueMZVy/dlR"
    "Pm66PxV9bPkbk/oY4J5Pl4xz7xxLxKWON2iMWdpn76O00cQcuwocG0jixFcJ9J+LY/Bi"
    "SkzGD7/PFUhMPWnUeq/ZRRVBRTuuSOJuPluLdvcsZgRNNunEsf2Jme8xpc9xZr0Mk1MV"
    "1trfPcRow3PVVKJIYk5yMa+MAUePJ9H7eQJ9ZxIYiMYxOFJ4Mf2Kp11ohnSxtRlHqrPNC"
    "J4yGo6nxaEkXEZfzlJdK882Zp9jyqjzGJMqkdynKqPpuJo0tjiUuvSYpVlcbZ+1rvQRYu"
    "5qvpIS82fg0OF59PQlcXwogb5v5viS9otRV8zJAomZbamabanr44KKxJKS1VTmBw8xte"
    "R1MN9YbGLmMiapP48xiRhMMVpvHpnxpOPMJUY3Htt4CSFm0/sjQswDnfM40p1ET39qSfv"
    "Zt3EMXriLi7/N4ZcrVwsmZvolkJJYtnKOn4ttSCybYF7Y9rOVO+Qmpq1cJvcxmWNwyPoC"
    "znRjDBajPDOb+ypPhJjbGr8TYnZ9Oo8DB+ZxpDeJs+eTvDyZBGbvJHDh0kThxDRcSIZIK"
    "NOdWbrT+0EklkcSW7HtZyt3MEthSe6skqRxk9zvmMwx+OnTIGbQ82558cPjMl3fMkGI+d"
    "a2M0LMlSu2YMGChxEKhVBZGcbY2AT+nU1g+vYcvj73I16sfQmfdHXl9F8mwcQ0JY8leV"
    "2CJohHElux7Wcrd9DHxbCMLaskaf6fYko48aoY25Y4QsxNb5/C8PAwamtrsWzZMsRiMS5q"
    "S0sLqqqexFAkil2t+7FwYQVvw8rD4TBeXbvW1/9tBhXTTVaRIB7JprXX6i14HteCbT9bu"
    "YNZCouY1nIZw+oiUAwOuYoZ9LxbkZ5ZTfGVOELMjQ29XDY2S7pSuhsTlZVXVFRweeWtrq"
    "4OmzZvRl9/P/a1t/Of2WyaPzEzZwJtVjDg3caQ6B5JbMW2n63cwSyFIS5OLi9WDC9/cor"
    "BIWcxA573bIgxmd4llDZCzNfeOMiFNIlZXV2NysVVaG5uyShn28zMDN9HhX0rQr7ETCdY"
    "6u9t5mSRkJZVeiKnkyMjIT2S2IptP1u5g1mKLIkrLfO0MdnqAsXgEEDMnM+76WZi6MMYX"
    "4kjxFy7sUNIuK/zGK7PgDN+8y8u2pp19Vizrk6Uq/VsxmRfR8Jgv7PPvIkpXSTzRTcgJas"
    "JLRk8ktiKbT9buYNZiixiSvvY0PoKFINDEDGlPm2ox1P/Xqqiti8XhJgvr9+LZHIeBw/14"
    "NEnwuj86W90/wGsbmjFY5VLsL5+By9nZTIb9hzjz5mugGymbNyxA+NTU3kUMzMpTUlrJl"
    "NoFy2ZGB5JbMW2n63cwSxFdjHVNjLG9oFicAgqplLved4ZFpmNcZUJQsznVq3Gm+9uR8P"
    "W97CocjEWLgrjkaeXY+nSpXhneyP/rp8VK1fimc0dWBcF55XIP3jo8TCfLWUJTdyrmARRT"
    "nAxGWzpeXJggH+yWY+hflOeu0wNrdqK0JoPEQovR+vu3ZqEJkhMgvCPENMvbInK3royIf"
    "3MlC4kJkH4J2cxg0JiEoR/SEyCKEJITIIoQkhMgihCSEyCKEL+A/acbdSKLP2lAAAAAElF"
    "TkSuQmCC"
)

DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
DATETIME = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\b"
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?\d[ .-]?){9,14}(?!\d)")
LONG_IDENTIFIER = re.compile(r"\b\d{7,16}\b")
IDENTIFIER_LINE = re.compile(
    r"(?i)^\s*(?:paciente|nombre|apellidos|sip|nhc|historia\s+cl[ií]nica|"
    r"n[uú]mero\s+de\s+historia|identificador)\s*:"
)
SIGNATURE_LINE = re.compile(r"(?i)^\s*(?:dr\.?|dra\.?)\s*:")
RESIDUAL_PII = re.compile(
    r"(?i)\b(?:sip|nhc|historia\s+cl[ií]nica|nombre\s+y\s+apellidos)\b"
)

LABEL_LINE = re.compile(r"^\s{0,4}([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ /]{1,39}):")
AGE_FIELD = re.compile(r"(?i)\bedad\s*:\s*(\d{1,3})")
AGE_GENERALIZATION_THRESHOLD = 90
# Edad mencionada en texto libre, p.ej. "92 a con..." o "93 años de edad".
# El lookahead evita tocar rangos numericos como "6 a 8 mm".
INLINE_AGE = re.compile(r"(?i)\b(\d{2,3})(\s*(?:años?(?:\s+de\s+edad)?|a))\b(?!\s*\d)")

SECTION_DATA = re.compile(r"(?im)^\s*datos\s+cl[ií]nicos\s*:?\s*")
SECTION_EXPLORATION = re.compile(r"(?im)^\s*exploraci[oó]n\s*:?\s*")
SECTION_FINDINGS = re.compile(r"(?im)^\s*hallazgos?\s*:?\s*")
SECTION_IMPRESSION = re.compile(
    r"(?im)^\s*(?:impresi[oó]n\s+diagn[oó]stica|conclusi[oó]n)\s*:?\s*"
)

REGION_TERMS = {
    "abdomen_pelvis": ("abdomen", "abdominopelv", "higado", "riñon", "suprarrenal"),
    "torax": ("torax", "pulmon", "mediastino", "angiotc pulmon"),
    "cervical": ("cervical",),
    "lumbar": ("lumbar", "lumbosacra"),
    "rodilla": ("rodilla",),
    "mano_muneca": ("muneca", "mano", "carpo"),
    "codo": ("codo",),
    "tobillo_pie": ("tobillo", "pie", "aquiles"),
    "cadera_pelvis": ("cadera", "pelvis osea", "coxofemoral"),
    "hombro": ("hombro",),
    # La ATM es articulacion propia y con protocolo propio, asi que no se
    # agrupa bajo cabeza_cuello (reservado a estudios craneoencefalicos).
    "atm": ("temporomandibular", "temporo mandibular", "atm"),
    "cabeza_cuello": (
        "craneo", "cerebro", "cerebral", "encefalo", "encefalico", "intracraneal",
    ),
}


class CaptureError(RuntimeError):
    pass


class StopRequested(RuntimeError):
    pass


def normalized(text: str) -> str:
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _generalize_inline_ages(text: str) -> str:
    """Reemplaza edades >= umbral mencionadas en texto libre por el umbral.

    Solo cambia los digitos (p.ej. "92 a" -> "90 a", "93 años" -> "90
    años"); nunca toca valores por debajo del umbral ni rangos numericos
    como "6 a 8 mm" (el patron exige que la edad no vaya seguida de otro
    numero).
    """

    def replace(match: re.Match[str]) -> str:
        years = int(match.group(1))
        if years < AGE_GENERALIZATION_THRESHOLD or years > 130:
            return match.group(0)
        return f"{AGE_GENERALIZATION_THRESHOLD}{match.group(2)}"

    return INLINE_AGE.sub(replace, text)


def anonymize(text: str) -> str:
    clean_lines = []
    for line in text.replace("\r\n", "\n").splitlines():
        if IDENTIFIER_LINE.search(line) or SIGNATURE_LINE.search(line):
            continue
        value = DATETIME.sub("[FECHA]", line)
        value = DATE.sub("[FECHA]", value)
        value = EMAIL.sub("[EMAIL]", value)
        value = PHONE.sub("[TELEFONO]", value)
        value = LONG_IDENTIFIER.sub("[IDENTIFICADOR]", value)
        value = _generalize_inline_ages(value)
        clean_lines.append(value.rstrip())
    result = "\n".join(clean_lines).strip()
    if RESIDUAL_PII.search(result):
        raise CaptureError("La captura conserva un campo identificativo reconocible.")
    return result


def _section_between(text: str, start: re.Match[str], end: re.Match[str] | None) -> str:
    value = text[start.end() : end.start() if end else len(text)]
    return anonymize(value).strip()


def age_phrase(text: str) -> str:
    """Convierte el campo estructurado 'Edad:' en una frase clínica corta.

    Solo se usa el número de años (nunca meses ni la fecha de nacimiento).
    A partir del umbral de generalización, la edad exacta se reemplaza por
    "N años o más" para reducir el riesgo de reidentificación en pacientes
    muy longevos.
    """
    match = AGE_FIELD.search(text)
    if not match:
        return ""
    years = int(match.group(1))
    if years <= 0 or years > 130:
        return ""
    if years >= AGE_GENERALIZATION_THRESHOLD:
        return f"Paciente de {AGE_GENERALIZATION_THRESHOLD} años o más."
    return f"Paciente de {years} años."


def parse_report(text: str) -> dict:
    clean = text.replace("\r\n", "\n")
    data_matches = list(SECTION_DATA.finditer(clean))
    findings_matches = list(SECTION_FINDINGS.finditer(clean))
    impression_matches = list(SECTION_IMPRESSION.finditer(clean))
    if not data_matches or not findings_matches:
        raise CaptureError("No se reconocieron Datos clinicos ni Hallazgos.")

    data_match = data_matches[-1]
    findings_match = next(
        (match for match in findings_matches if match.start() > data_match.start()),
        None,
    )
    if not findings_match:
        raise CaptureError("Las secciones del informe no aparecen en el orden esperado.")

    # La Impresion diagnostica (o Conclusion) es opcional: algunos informes
    # finales no la incluyen y aun asi son utiles para Hallazgos -> Impresion.
    impression_match = next(
        (match for match in impression_matches if match.start() > findings_match.start()),
        None,
    )

    all_exploration_matches = list(SECTION_EXPLORATION.finditer(clean))
    exploration_in_body = [
        match
        for match in all_exploration_matches
        if data_match.start() < match.start() < findings_match.start()
    ]

    if exploration_in_body:
        exploration_match = exploration_in_body[-1]
        clinical = _section_between(clean, data_match, exploration_match)
        exploration = _section_between(clean, exploration_match, findings_match)
    else:
        # Algunas plantillas no repiten "Exploracion" dentro del cuerpo: se
        # usa el campo de tipo de exploracion que aparece antes de "Datos
        # clinicos" (el encabezado superior del estudio solicitado).
        exploration_before_data = [
            match for match in all_exploration_matches if match.start() < data_match.start()
        ]
        if not exploration_before_data:
            raise CaptureError("Las secciones del informe no aparecen en el orden esperado.")
        top_exploration_match = exploration_before_data[-1]
        clinical = _section_between(clean, data_match, findings_match)
        exploration = _section_between(clean, top_exploration_match, data_match)

    # La edad (generalizada si es muy avanzada) es el unico dato del
    # encabezado de identificacion que se conserva, porque aporta contexto
    # clinico; el resto del encabezado (nombre, NHC, episodio, hospital,
    # medico solicitante...) nunca se procesa.
    phrase = age_phrase(clean)
    if phrase:
        clinical = f"{phrase} {clinical}".strip() if clinical else phrase

    if impression_match is not None:
        findings = _section_between(clean, findings_match, impression_match)
        impression = _section_between(clean, impression_match, None)
        impression = re.split(r"(?im)^\s*(?:dr\.?|dra\.?)\s*:", impression, maxsplit=1)[0].strip()
    else:
        findings = _section_between(clean, findings_match, None)
        impression = ""

    if not all((clinical, exploration, findings)):
        raise CaptureError("Una de las secciones clinicas obligatorias esta vacia.")
    if len(normalized(findings)) < 25:
        raise CaptureError("Hallazgos demasiado breves para una captura segura.")

    return {
        "clinical_data": clinical,
        "exploration": exploration,
        "findings": findings,
        "impression": impression,
    }


def detect_modality(exploration: str) -> str:
    value = normalized(exploration)
    if re.search(r"\b(?:tc|tac|angiotc|tomograf)", value):
        return "TC"
    if re.search(r"\b(?:rm|resonancia)", value):
        return "RM"
    if re.search(r"\b(?:eco|ecograf)", value):
        return "ECO"
    if re.search(r"\b(?:rx|radiograf)", value):
        return "RX"
    return "OTRA"


def detect_region(exploration: str) -> str:
    value = normalized(exploration)
    for region, terms in REGION_TERMS.items():
        if any(normalized(term) in value for term in terms):
            return region
    return "sin_clasificar"


def build_review_candidate(report: dict) -> dict:
    raw_input = "\n\n".join(
        (
            f"Datos clinicos: {report['clinical_data']}",
            f"Exploracion: {report['exploration']}",
            f"Hallazgos:\n{report['findings']}",
        )
    )
    final_report = raw_input + f"\n\nImpresion diagnostica:\n{report['impression']}"
    digest = hashlib.sha256(normalized(final_report).encode("utf-8")).hexdigest()[:20]
    return {
        "review_case_id": f"vuepacs_{digest}",
        "region": detect_region(report["exploration"]),
        "modality": detect_modality(report["exploration"]),
        "source": {"type": "vuepacs_local_clipboard"},
        "candidate_type": "historical_final_report_masked_impression",
        "raw_input": raw_input,
        "final_report": final_report,
        "approval_status": "candidate",
        "review_notes": "Verificar anonimización y coherencia Hallazgos-Impresión.",
        "sft_eligible": False,
        "extraction_confidence": "structured_final_report",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_candidate(path: Path, candidate: dict) -> bool:
    rows = read_jsonl(path)
    if any(row.get("review_case_id") == candidate["review_case_id"] for row in rows):
        return False
    rows.append(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)
    return True


def _clipboard_text() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    if not user32.OpenClipboard(None):
        raise CaptureError("No se pudo abrir el portapapeles.")
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _clear_clipboard() -> None:
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    if user32.OpenClipboard(None):
        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()


def _stop_pressed() -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(STOP_KEY) & 0x8000)


def _ensure_dpi_awareness() -> None:
    """Declara el proceso como consciente del DPI real de cada monitor.

    Sin esto, en un monitor con escalado de Windows distinto de 100%,
    ImageGrab captura en píxeles físicos (la resolución real), pero las
    coordenadas que usa el sistema para clics simulados (SendInput) se
    interpretan en píxeles lógicos/virtualizados si el proceso no declaró
    ser DPI-aware. Eso desalinea el punto encontrado por coincidencia de
    plantilla del punto donde realmente cae el clic. Un blanco grande
    (la ventana entera del informe) tolera ese desajuste; un ítem de menú
    de pocos píxeles de alto no. Se intenta primero la variante moderna
    (por monitor) y se cae a la variante antigua si no está disponible.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _require_automation():
    try:
        from pywinauto import Desktop, keyboard, mouse
        from pywinauto.findwindows import find_elements
    except ImportError as error:
        raise SystemExit(
            "Falta pywinauto. Instala solo el requisito del capturador con: "
            "python -m pip install -r requirements-vuepacs.txt"
        ) from error
    return Desktop, keyboard, mouse, find_elements


def _find_main_window(desktop, title_pattern: str):
    pattern = re.compile(title_pattern)
    matches = [
        window
        for window in desktop.windows()
        if window.is_visible() and pattern.search(window.window_text() or "")
    ]
    if len(matches) != 1:
        raise CaptureError(
            f"Se esperaba una ventana Vue PACS y se encontraron {len(matches)}."
        )
    return matches[0]


def _foreground_process_id() -> int:
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    foreground = user32.GetForegroundWindow()
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
    return process_id.value


def _foreground_window_handle():
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    return user32.GetForegroundWindow()


def _force_foreground(handle) -> bool:
    """Fuerza que una ventana pase realmente a primer plano y reciba foco.

    Windows tiene una proteccion anti-robo-de-foco: un proceso en segundo
    plano (como el que ejecuta este script, lanzado desde una terminal que
    mantiene el foco) no puede quitarle el foco de teclado a la ventana
    activa salvo que la entrada provenga de una accion "real" reciente del
    usuario. Por eso la ventana de Vue PACS puede quedar visible en
    pantalla pero sin foco de teclado real cuando la abre la
    automatizacion, y Ctrl+A/Ctrl+C (o su menu contextual) terminan
    actuando sobre la terminal en vez de sobre el informe. El truco
    habitual para levantar esa restriccion es simular una pulsacion de la
    tecla ALT (que resetea el bloqueo interno) justo antes de pedir el
    foco.
    """
    if not handle:
        return False
    user32 = ctypes.windll.user32
    alt_key = 0x12
    keyup = 0x0002
    user32.keybd_event(alt_key, 0, 0, 0)
    user32.keybd_event(alt_key, 0, keyup, 0)
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    return bool(user32.SetForegroundWindow(handle))


def _foreground_window_class_name() -> str:
    """Clase Win32 de la ventana en primer plano (nunca su titulo)."""
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    handle = user32.GetForegroundWindow()
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(handle, buffer, 256)
    return buffer.value or "?"


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _focused_control_handle():
    """Handle del control que realmente tiene el foco de teclado.

    GetForegroundWindow siempre devuelve la ventana de nivel superior (en
    Vue PACS, normalmente el marco principal MDI), aunque el usuario este
    escribiendo o mirando un panel hijo dentro de una ventana de informe.
    GetGUIThreadInfo, en cambio, reporta el control real con foco (hwndFocus),
    que en ventanas MDI suele ser un descendiente de la ventana de informe
    visible y no de la ventana principal. Se usa solo para comparar handles;
    nunca se lee texto ni titulo de este control.
    """
    user32 = ctypes.windll.user32
    info = _GUITHREADINFO()
    info.cbSize = ctypes.sizeof(_GUITHREADINFO)
    if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
        return None
    return info.hwndFocus or info.hwndActive or None


def _focused_control_class_name() -> str:
    """Clase Win32 del control con foco real (nunca su titulo/texto)."""
    handle = _focused_control_handle()
    if not handle:
        return "?"
    user32 = ctypes.windll.user32
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(handle, buffer, 256)
    return buffer.value or "?"


def _is_real_window(handle) -> bool:
    """True si el handle corresponde a una ventana Win32 que existe ahora.

    Un handle puede ser numericamente distinto de cero pero ya no referirse
    a ninguna ventana real (por ejemplo un remanente del menu contextual
    que UIA sigue listando un instante despues de que la ventana nativa
    dejo de existir). Comprobar solo que el handle no sea 0/None no alcanza
    para descartar estos casos; hace falta IsWindow.
    """
    if not handle:
        return False
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    return bool(user32.IsWindow(handle))


def _window_contains_handle(window_handle, target_handle) -> bool:
    """True si target_handle es window_handle o un descendiente suyo."""
    if not window_handle or not target_handle:
        return False
    if window_handle == target_handle:
        return True
    user32 = ctypes.windll.user32
    user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.IsChild.restype = wintypes.BOOL
    return bool(user32.IsChild(window_handle, target_handle))


def _window_rect(handle):
    """(left, top, right, bottom) de una ventana, o None si no se puede leer."""
    if not handle:
        return None
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    if not user32.GetWindowRect(handle, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


def _window_rect_area(handle) -> int:
    """Area (ancho*alto) de una ventana. 0 si no se puede consultar."""
    rect = _window_rect(handle)
    if rect is None:
        return 0
    left, top, right, bottom = rect
    width = max(0, right - left)
    height = max(0, bottom - top)
    return width * height


def _window_content_click_point(handle):
    """Punto dentro del panel de contenido de la ventana de informe.

    Las ventanas de Vue PACS observadas tienen, de arriba a abajo: cabecera
    con el paciente/version, pestañas ("Datos de orden" / "Final, fecha") y
    despues el panel con el texto del informe, que ocupa la mayor parte de
    la ventana. Se hace clic sesgado hacia la parte baja (60% de la altura)
    para caer dentro de ese panel de contenido y no en la cabecera ni en
    las pestañas, y asi que Ctrl+A seleccione el texto del informe. Se basa
    solo en la geometria de la ventana, nunca en su contenido.
    """
    rect = _window_rect(handle)
    if rect is None:
        return None
    left, top, right, bottom = rect
    x = (left + right) // 2
    y = top + int((bottom - top) * 0.6)
    return (x, y)


def _window_total_child_text_length(handle) -> int:
    """Suma la LONGITUD (nunca el contenido) del texto de los controles hijos.

    Se usa solo para distinguir, entre varias ventanas nuevas del mismo
    tipo, cual tiene contenido real (el informe) de una ventana vacia o
    decorativa (por ejemplo una de carga). En ningun momento se lee ni se
    guarda el texto en si, solo su longitud en caracteres.
    """
    if not handle:
        return 0
    user32 = ctypes.windll.user32
    total = 0

    wndenumproc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(child_handle, _lparam):
        nonlocal total
        length = user32.GetWindowTextLengthW(child_handle)
        if length > 0:
            total += length
        return True

    try:
        user32.EnumChildWindows(handle, wndenumproc(_callback), 0)
    except OSError:
        return total
    return total


def _window_descendant_count(handle) -> int:
    """Cantidad de controles hijos (a cualquier profundidad) de una ventana.

    No inspecciona que son esos controles ni su contenido; solo cuenta
    cuantos hay. Sirve para distinguir una ventana con una interfaz real
    (pestanas, barra de scroll, panel de texto, etc.) de una ventana vacia
    o de carga, incluso cuando el contenido esta en un control que no
    expone su texto por GetWindowTextLength (por ejemplo un visor HTML
    embebido).
    """
    if not handle:
        return 0
    user32 = ctypes.windll.user32
    count = 0

    wndenumproc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(_child_handle, _lparam):
        nonlocal count
        count += 1
        return True

    try:
        user32.EnumChildWindows(handle, wndenumproc(_callback), 0)
    except OSError:
        return count
    return count


def _select_report_window_by_content(new_windows):
    """Ultimo recurso: elige la ventana con mas contenido real.

    Primero compara la longitud de texto de los controles hijos (nunca el
    contenido). Si eso no distingue nada (por ejemplo porque el informe se
    renderiza en un control que no expone texto por Win32, como un visor
    HTML embebido, y todas las ventanas miden longitud 0), se usa como
    alternativa la cantidad de controles hijos: una ventana con una
    interfaz real construida (pestanas, scroll, panel de contenido) tiene
    muchos mas que una ventana vacia o de carga. Devuelve
    (ventana_elegida_o_None, metricas) donde metricas es una lista de
    tuplas (handle, area, longitud_texto, cantidad_de_hijos) para
    diagnostico sin PHI.
    """
    metrics = []
    for window in new_windows:
        area = _window_rect_area(window.handle)
        text_length = _window_total_child_text_length(window.handle)
        descendant_count = _window_descendant_count(window.handle)
        metrics.append((window, area, text_length, descendant_count))

    with_text = sorted(
        (entry for entry in metrics if entry[2] > 0),
        key=lambda entry: entry[2],
        reverse=True,
    )
    if len(with_text) == 1:
        return with_text[0][0], metrics
    if len(with_text) > 1:
        top_length = with_text[0][2]
        runner_up_length = with_text[1][2]
        if top_length >= runner_up_length * 2 and top_length - runner_up_length > 20:
            return with_text[0][0], metrics

    with_children = sorted(
        (entry for entry in metrics if entry[3] > 0),
        key=lambda entry: entry[3],
        reverse=True,
    )
    if len(with_children) == 1:
        return with_children[0][0], metrics
    if len(with_children) > 1:
        top_count = with_children[0][3]
        runner_up_count = with_children[1][3]
        if top_count >= runner_up_count * 2 and top_count - runner_up_count >= 3:
            return with_children[0][0], metrics
    return None, metrics


def _require_vue_focus(main_window) -> None:
    if _foreground_process_id() != main_window.process_id():
        raise CaptureError(
            "Vue PACS no tiene el foco. Vuelve a ejecutar el comando y, durante "
            "la cuenta atrás, haz clic una vez en la fila seleccionada."
        )


def _cursor_position_and_process_id() -> tuple[tuple[int, int], int]:
    user32 = ctypes.windll.user32
    point = wintypes.POINT()
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise CaptureError("No se pudo leer la posición del puntero.")
    window_handle = user32.WindowFromPoint(point)
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window_handle, ctypes.byref(process_id))
    return (point.x, point.y), process_id.value


def _right_click_vue_at_cursor(main_window, mouse) -> None:
    position, process_id = _cursor_position_and_process_id()
    if process_id != main_window.process_id():
        raise CaptureError(
            "El puntero no está sobre Vue PACS. Repite la prueba y déjalo "
            "encima de la fila seleccionada durante la cuenta atrás."
        )
    mouse.click(button="right", coords=position)


def _process_id_at_point(position: tuple[int, int]) -> int:
    user32 = ctypes.windll.user32
    point = wintypes.POINT(*position)
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(
        user32.WindowFromPoint(point), ctypes.byref(process_id)
    )
    return process_id.value


def _visual_report_menu_target(screen=None, virtual_origin=None):
    """Locate the sanitized menu template without retaining a screen capture."""
    try:
        import numpy as np
        from PIL import Image, ImageGrab
        from scipy.signal import fftconvolve
    except ImportError as error:
        raise CaptureError(
            "Faltan Pillow, NumPy o SciPy para la comprobación visual local."
        ) from error

    if screen is None:
        screen = ImageGrab.grab(all_screens=True)
    image = np.asarray(screen.convert("L"), dtype=np.float64)

    if virtual_origin is None:
        user32 = ctypes.windll.user32
        virtual_origin = (
            user32.GetSystemMetrics(76),  # SM_XVIRTUALSCREEN
            user32.GetSystemMetrics(77),  # SM_YVIRTUALSCREEN
        )

    best_target = None
    best_score = -1.0
    for template_path in REPORT_MENU_TEMPLATE_PATHS:
        template = Image.open(template_path).convert("L")
        sample = np.asarray(template, dtype=np.float64)
        height, width = sample.shape
        if image.shape[0] < height or image.shape[1] < width:
            continue

        centered = sample - sample.mean()
        area = float(height * width)
        kernel = np.ones((height, width), dtype=np.float64)
        correlation = fftconvolve(image, centered[::-1, ::-1], mode="valid")
        local_sum = fftconvolve(image, kernel, mode="valid")
        local_sum_sq = fftconvolve(image * image, kernel, mode="valid")
        local_variance = np.maximum(
            local_sum_sq - (local_sum * local_sum / area), 0.0
        )
        denominator = np.sqrt(float(np.sum(centered * centered)) * local_variance)
        scores = np.zeros_like(correlation)
        np.divide(correlation, denominator, out=scores, where=denominator > 1e-12)
        scores = np.clip(scores, -1.0, 1.0)
        row, column = np.unravel_index(np.argmax(scores), scores.shape)
        score = float(scores[row, column])
        if score > best_score:
            best_score = score
            best_target = (
                virtual_origin[0] + int(column) + width // 2,
                virtual_origin[1] + int(row) + height // 2,
            )
    return best_target, max(best_score, 0.0)


def _click_menu_target(mouse, target) -> None:
    """Clic sobre un ítem de menú owner-drawn de forma que sí se registre.

    Un `click()` simple (mover+presionar+soltar en el mismo instante) mueve
    el puntero pero a menudo no activa el ítem en estos menús de WinForms:
    el menú corre su propio bucle modal de mensajes y sólo considera
    "activo" el ítem que previamente quedó resaltado por un movimiento real
    del ratón. Por eso aquí se entra al ítem desde un punto vecino (para
    generar un WM_MOUSEMOVE con desplazamiento real que lo resalte), se da
    tiempo a que el menú repinte, y se separan la pulsación y la
    liberación en vez de emitirlas juntas.
    """
    approach = (target[0] - 12, target[1])
    mouse.move(coords=approach)
    time.sleep(0.15)
    mouse.move(coords=target)
    time.sleep(0.25)
    mouse.press(button="left", coords=target)
    time.sleep(0.08)
    mouse.release(button="left", coords=target)


def _verified_visual_report_target(main_window, screen=None, virtual_origin=None):
    target, score = _visual_report_menu_target(screen, virtual_origin)
    if target is None or score < VISUAL_MATCH_THRESHOLD:
        return None, score
    if _process_id_at_point(target) != main_window.process_id():
        raise CaptureError(
            "La coincidencia visual de 'Ver informes' no pertenece a Vue PACS."
        )
    return target, score


def _ancestor_root_handle(handle):
    """Handle de la ventana de nivel superior que contiene a `handle`."""
    if not handle:
        return None
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
    user32.GetAncestor.restype = wintypes.HWND
    return user32.GetAncestor(handle, GA_ROOT) or None


def _window_handle_at_point(point):
    """Handle de la ventana (de cualquier nivel) bajo un punto de pantalla."""
    user32 = ctypes.windll.user32
    win_point = wintypes.POINT(*point)
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    return user32.WindowFromPoint(win_point) or None


def _locate_report_window_visually(timeout: float, screen=None, virtual_origin=None):
    """Ubica la ventana "Explorador de informes" por su barra de título.

    En vez de confiar en la enumeración de ventanas de UI Automation (que
    puede reportar ventanas fantasma/transitorias sin presencia visual
    real, como se vio en la práctica), se busca directamente en los
    píxeles de la pantalla la barra de título de esta ventana: un elemento
    de interfaz que nunca cambia entre pacientes y nunca contiene datos
    clínicos. Si aparece, se usa esa posición para ubicar la ventana real
    vía WindowFromPoint + GetAncestor. Una ventana fantasma no tiene
    presencia visual pintada en pantalla, por lo que nunca podría producir
    una coincidencia aquí — esto descarta el problema de raíz en vez de
    intentar filtrarlo después. Devuelve (handle, rect, mejor_puntaje). Si
    no aparece dentro del timeout, handle y rect son None y mejor_puntaje
    indica que tan cerca estuvo (util para diagnosticar diferencias de
    escala/DPI entre la plantilla y la pantalla real).
    """
    try:
        import numpy as np
        from PIL import Image, ImageGrab
        from scipy.signal import fftconvolve
    except ImportError as error:
        raise CaptureError(
            "Faltan Pillow, NumPy o SciPy para la comprobación visual local."
        ) from error

    if virtual_origin is None:
        user32 = ctypes.windll.user32
        virtual_origin = (
            user32.GetSystemMetrics(76),  # SM_XVIRTUALSCREEN
            user32.GetSystemMetrics(77),  # SM_YVIRTUALSCREEN
        )

    template = Image.open(REPORT_WINDOW_TITLEBAR_TEMPLATE_PATH).convert("L")
    sample = np.asarray(template, dtype=np.float64)
    height, width = sample.shape
    centered = sample - sample.mean()
    area = float(height * width)
    kernel = np.ones((height, width), dtype=np.float64)

    deadline = time.monotonic() + timeout
    fixed_screen = screen
    best_score_seen = 0.0
    while time.monotonic() < deadline:
        if _stop_pressed():
            raise StopRequested()
        current_screen = (
            fixed_screen if fixed_screen is not None else ImageGrab.grab(all_screens=True)
        )
        image = np.asarray(current_screen.convert("L"), dtype=np.float64)
        if image.shape[0] >= height and image.shape[1] >= width:
            correlation = fftconvolve(image, centered[::-1, ::-1], mode="valid")
            local_sum = fftconvolve(image, kernel, mode="valid")
            local_sum_sq = fftconvolve(image * image, kernel, mode="valid")
            local_variance = np.maximum(
                local_sum_sq - (local_sum * local_sum / area), 0.0
            )
            denominator = np.sqrt(float(np.sum(centered * centered)) * local_variance)
            scores = np.zeros_like(correlation)
            np.divide(correlation, denominator, out=scores, where=denominator > 1e-12)
            scores = np.clip(scores, -1.0, 1.0)
            row, column = np.unravel_index(np.argmax(scores), scores.shape)
            score = float(scores[row, column])
            best_score_seen = max(best_score_seen, score)
            if score >= VISUAL_MATCH_THRESHOLD:
                top_left = (
                    virtual_origin[0] + int(column),
                    virtual_origin[1] + int(row),
                )
                probe_point = (top_left[0] + 20, top_left[1] + height + 20)
                root_handle = _ancestor_root_handle(
                    _window_handle_at_point(probe_point)
                )
                if root_handle:
                    rect = _window_rect(root_handle)
                    if rect is not None:
                        return root_handle, rect, best_score_seen
        if fixed_screen is not None:
            break  # una captura fija (usada en pruebas) no cambia entre vueltas
        time.sleep(0.3)
    return None, None, best_score_seen


def _find_report_menu_item(
    desktop_uia,
    desktop_win32,
    timeout: float,
    process_id: int | None = None,
    find_elements=None,
    diagnostics: dict | None = None,
    target_name: str = REPORT_MENU_NAME,
):
    """Return the exact menu item (por defecto "Ver informes") y su backend.

    `target_name` permite reutilizar esta misma busqueda para otros items
    de menu contextual (por ejemplo "Seleccionar todo" o "Copiar" dentro
    del panel de contenido del informe, que no responde a Ctrl+A/Ctrl+C).
    """
    counters = diagnostics if diagnostics is not None else {}
    counters.setdefault("uia_menu_windows", 0)
    counters.setdefault("uia_descendant_items", 0)
    counters.setdefault("win32_popups", 0)
    counters.setdefault("win32_descendant_popups", 0)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _stop_pressed():
            raise StopRequested()

        uia_menus = desktop_uia.windows(control_type="Menu")
        counters["uia_menu_windows"] = max(
            counters["uia_menu_windows"], len(uia_menus)
        )
        for menu in uia_menus:
            item = menu.child_window(title=target_name, control_type="MenuItem")
            if item.exists(timeout=0.1):
                return "uia", item.wrapper_object()

        if find_elements is not None and process_id is not None:
            try:
                elements = find_elements(
                    process=process_id,
                    title=target_name,
                    control_type="MenuItem",
                    top_level_only=False,
                    visible_only=True,
                    backend="uia",
                )
            except (AttributeError, RuntimeError):
                elements = []
            counters["uia_descendant_items"] = max(
                counters["uia_descendant_items"], len(elements)
            )
            for element in elements:
                item = desktop_uia.backend.generic_wrapper_class(element)
                if (item.window_text() or "").strip() == target_name:
                    return "uia", item

        popups = desktop_win32.windows(class_name="#32768")
        counters["win32_popups"] = max(counters["win32_popups"], len(popups))
        if find_elements is not None and process_id is not None:
            try:
                popup_elements = find_elements(
                    process=process_id,
                    class_name="#32768",
                    top_level_only=False,
                    visible_only=True,
                    backend="win32",
                )
            except (AttributeError, RuntimeError):
                popup_elements = []
            counters["win32_descendant_popups"] = max(
                counters["win32_descendant_popups"], len(popup_elements)
            )
            known_handles = {getattr(popup, "handle", None) for popup in popups}
            popups.extend(
                desktop_win32.backend.generic_wrapper_class(element)
                for element in popup_elements
                if getattr(element, "handle", None) not in known_handles
            )

        for popup in popups:
            try:
                menu = popup.menu()
                if menu is None:
                    continue
                for item in menu.items():
                    if item.text().strip() == target_name:
                        return "win32", item
            except (AttributeError, RuntimeError):
                continue
        time.sleep(0.1)
    return None


def _activate_report_menu_item(backend: str, item, mouse=None) -> str:
    """Activa el item de menu "Ver informes".

    Se intenta primero un clic de mouse real sobre las coordenadas del
    item (lo mismo que haria una persona), en vez de depender solo de
    acciones de accesibilidad (invoke/select). Algunos menus contextuales
    dibujados a mano (owner-drawn) en aplicaciones WinForms antiguas no
    siempre ejecutan el manejador real del comando cuando se activan solo
    por UI Automation, aunque esa accion "tenga exito" sin lanzar error;
    un clic real reproduce fielmente lo que hace un usuario. Si no se
    puede obtener la posicion del item (o no hay mouse disponible), se usa
    invoke()/select() como respaldo. Devuelve una etiqueta indicando que
    metodo se uso, solo para diagnostico (nunca contiene datos del
    paciente).
    """
    if mouse is not None:
        try:
            rect = item.rectangle()
            point = rect.mid_point()
            _click_menu_target(mouse, (point.x, point.y))
            return "clic real"
        except (AttributeError, RuntimeError):
            pass
    if backend == "uia":
        item.invoke()
        return "uia invoke"
    elif backend == "win32":
        item.select()
        return "win32 select"
    else:
        raise CaptureError(f"Backend de menú no reconocido: {backend!r}.")


def _copy_report_content_via_context_menu(
    mouse,
    desktop_uia,
    desktop_win32,
    click_point,
    process_id,
    find_elements,
    timeout: float,
) -> None:
    """Selecciona todo y copia el panel de contenido del informe.

    El panel de contenido del informe es un control personalizado que NO
    responde a Ctrl+A/Ctrl+C: solo se puede copiar via su propio menu
    contextual (clic derecho), con las opciones "Seleccionar todo" y
    "Copiar" como items de menu separados. Se hace clic derecho, se busca
    y activa "Seleccionar todo"; luego se hace clic derecho de nuevo (el
    menu no queda abierto) y se busca y activa "Copiar".
    """
    for target_name in (SELECT_ALL_MENU_NAME, COPY_MENU_NAME):
        mouse.click(button="right", coords=click_point)
        match = _find_report_menu_item(
            desktop_uia,
            desktop_win32,
            min(timeout, 1.0),
            process_id=process_id,
            find_elements=find_elements,
            target_name=target_name,
        )
        if match is None:
            keyboard_escape = getattr(mouse, "send_keys", None)
            if callable(keyboard_escape):
                keyboard_escape("{ESC}")
            raise CaptureError(
                f"No se encontró el ítem de menú '{target_name}' en el "
                "panel del informe."
            )
        _activate_report_menu_item(*match, mouse=mouse)


def _window_classes(windows) -> list[str]:
    """Nombres de clase Win32 de una lista de ventanas (nunca titulos).

    Se usa solo para diagnosticar que ventanas inesperadas se abrieron; el
    titulo de una ventana de VuePACS puede incluir datos del paciente, la
    clase Win32 nunca.
    """
    classes = []
    for window in windows:
        try:
            classes.append(window.class_name() or "?")
        except (AttributeError, RuntimeError):
            classes.append("?")
    return classes


def _report_window_after_activation(desktop_win32, timeout: float):
    """Espera a que la ventana de informe aparezca, por reconocimiento visual.

    Se ubica la ventana buscando su barra de titulo en los pixeles de la
    pantalla, en vez de por enumeracion de ventanas de UI Automation. La
    enumeracion puede reportar ventanas fantasma/transitorias sin
    presencia visual real (se vio repetidas veces en la practica); una
    coincidencia visual, en cambio, solo puede darse sobre una ventana
    realmente pintada en pantalla. Devuelve (ventana|None, puntaje).
    """
    visual_handle, visual_rect, visual_score = _locate_report_window_visually(timeout)
    if visual_handle is not None:
        print(f"Ventana de informe ubicada por reconocimiento visual: {visual_rect}.")
        return desktop_win32.window(handle=visual_handle), visual_score
    return None, visual_score


def _activate_report_menu_and_locate_visually(
    main_window,
    desktop_uia,
    desktop_win32,
    keyboard,
    mouse,
    find_elements,
    timeout: float,
):
    """Un intento completo: abrir el menú, activar 'Ver informes', y esperar
    a que la ventana de informe aparezca visualmente. Devuelve la ventana
    (o None) y el mejor puntaje visual visto, para que el llamador decida
    si reintentar o pasar al método de respaldo.

    El menú se abre con un clic derecho sobre la posición actual del
    puntero. Se probó a abrirlo con la tecla de menú contextual para que
    actuase sobre la fila seleccionada, pero en esta aplicación esa tecla
    no despliega el menú (ni siquiera tras devolver el foco a la lista con
    un clic), así que se mantiene el clic derecho, que sí funciona de
    forma consistente. El avance de fila lo hace {DOWN} entre casos.
    """
    _require_vue_focus(main_window)
    _right_click_vue_at_cursor(main_window, mouse)

    # Ruta de teclado primero: es la unica que no depende de coordenadas
    # de pantalla ni de que el menu resalte el item por movimiento de
    # raton, que es justo lo que ha venido fallando. En un menu nativo de
    # Windows, escribir la inicial de un item cuya letra es unica en ese
    # menu lo EJECUTA directamente, sin necesidad de Enter. Sobre el menu
    # real de Vue PACS se verifico que "Ver informes" es el unico item que
    # empieza por "V".
    #
    # Es seguro aunque el menu no soporte esta navegacion (p.ej. si es un
    # ContextMenuStrip de .NET sin mnemonicos): en ese caso la tecla no
    # hace nada y se continua con los demas metodos. Aqui NO se pulsa
    # Enter en ningun caso: sin poder confirmar que item esta resaltado,
    # un Enter a ciegas podria activar el primer item del menu ("Cargar y
    # adjuntar informe"), que escribe en el sistema.
    keyboard.send_keys(REPORT_MENU_INITIAL)
    window, visual_score = _report_window_after_activation(
        desktop_win32, min(timeout, 2.5)
    )
    if window is not None:
        print(
            f"Menú activado con: tecla '{REPORT_MENU_INITIAL}' "
            "(inicial única del menú)."
        )
        return window, visual_score

    menu_match = _find_report_menu_item(
        desktop_uia,
        desktop_win32,
        min(timeout, 1.0),
        process_id=main_window.process_id(),
        find_elements=find_elements,
    )
    if menu_match is None:
        visual_target, visual_score = _verified_visual_report_target(main_window)
        if visual_target is None:
            keyboard.send_keys("{ESC}")
            raise CaptureError(
                f"No se encontró el menú exacto '{REPORT_MENU_NAME}'; "
                f"coincidencia visual={visual_score:.3f}."
            )
        _click_menu_target(mouse, visual_target)
        print(f"Menú activado con: clic visual en {visual_target}.")
    else:
        activation_method = _activate_report_menu_item(*menu_match, mouse=mouse)
        print(f"Menú activado con: {activation_method}.")

    return _report_window_after_activation(desktop_win32, min(timeout, 5.0))


def _open_report(
    main_window,
    desktop_uia,
    desktop_win32,
    keyboard,
    mouse,
    find_elements,
    timeout: float,
):
    before = {
        window.handle for window in desktop_uia.windows() if window.is_visible()
    }

    # Un clic sobre el menú (real o visual) a veces no llega a registrarse
    # en este WinForms owner-drawn (posible carrera entre el pintado del
    # menú y el evento de clic simulado): si la ventana de informe nunca
    # aparece visualmente en el primer intento, se reintenta el ciclo
    # completo (clic derecho + activar 'Ver informes' + esperar) una vez
    # más antes de recurrir al método de enumeración, propenso a ventanas
    # fantasma.
    def _new_real_windows() -> list:
        return [
            window
            for window in desktop_uia.windows()
            if window.is_visible()
            and window.handle not in before
            and _is_real_window(window.handle)
            and _window_rect(window.handle) is not None
        ]

    def _cursor_left_vue() -> bool:
        # Algunas ventanas de informe pertenecen a un proceso distinto del
        # de Vue PACS y no aparecen en la enumeracion de ventanas de nivel
        # superior de UI Automation (se vio en la practica), por lo que
        # _new_real_windows() puede no detectarlas nunca aunque esten
        # realmente pintadas en pantalla. Este chequeo usa la misma senal
        # que ya usa _right_click_vue_at_cursor para abortar con seguridad:
        # que proceso esta bajo el cursor ahora mismo. Si ya no es Vue
        # PACS, es porque algo se pinto encima (lo mas probable, el
        # informe recien abierto) y un segundo clic ahi seria inseguro.
        try:
            _, process_id = _cursor_position_and_process_id()
        except CaptureError:
            return False
        return bool(process_id) and process_id != main_window.process_id()

    def _new_real_windows_with_grace(grace: float) -> list | bool:
        # El intento visual puede agotar su propio plazo justo antes de que
        # Vue PACS termine de pintar la ventana del informe (carga sobre la
        # red, tamano del informe, etc.): una comprobacion instantanea aqui
        # perderia esa ventana por una fraccion de segundo. Se sondea un
        # rato mas, con el mismo presupuesto que el usuario ya acepto via
        # --timeout, antes de asumir que de verdad no se abrio nada.
        found = _new_real_windows()
        if found or _cursor_left_vue():
            return found or True
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if _stop_pressed():
                raise StopRequested()
            time.sleep(0.2)
            found = _new_real_windows()
            if found or _cursor_left_vue():
                return found or True
        return []

    max_attempts = 2
    last_score = 0.0
    for attempt in range(1, max_attempts + 1):
        window, visual_score = _activate_report_menu_and_locate_visually(
            main_window,
            desktop_uia,
            desktop_win32,
            keyboard,
            mouse,
            find_elements,
            timeout,
        )
        if window is not None:
            return window
        last_score = visual_score
        # La plantilla visual puede no reconocer una ventana que ya se abrio
        # de verdad (p.ej. si su barra de titulo esta en estado inactivo, o
        # con un tema/DPI distinto al de la plantilla guardada, o si tardo
        # en pintarse mas que el plazo de reconocimiento visual). Reintentar
        # el clic a ciegas en ese caso es inseguro: la posicion del cursor
        # usada por el clic derecho puede caer ahora sobre esa ventana nueva
        # en vez de sobre Vue PACS, y el intento se aborta por seguridad sin
        # haber llegado nunca al metodo de respaldo. Por eso, si ya hay (o
        # aparece en breve) una ventana nueva real, no se reintenta el
        # clic: se pasa directo al metodo de respaldo, que la localiza por
        # contenido en vez de por plantilla visual.
        if _new_real_windows_with_grace(min(timeout, 5.0)):
            print(
                "Reconocimiento visual de la ventana de informe: sin "
                f"coincidencia (mejor puntaje visto: {visual_score:.3f}, "
                f"umbral: {VISUAL_MATCH_THRESHOLD:.3f}), pero ya hay una "
                "ventana nueva abierta; se usa el método de respaldo sin "
                "reintentar el clic."
            )
            break
        if attempt < max_attempts:
            print(
                "Reconocimiento visual de la ventana de informe: sin "
                f"coincidencia en el intento {attempt} (mejor puntaje visto: "
                f"{visual_score:.3f}, umbral: {VISUAL_MATCH_THRESHOLD:.3f}); "
                "reintentando el clic sobre 'Ver informes'."
            )
    else:
        print(
            "Reconocimiento visual de la ventana de informe: sin coincidencia "
            f"tras {max_attempts} intentos (mejor puntaje visto: {last_score:.3f}, "
            f"umbral: {VISUAL_MATCH_THRESHOLD:.3f}); se usa el método de respaldo."
        )

    def _close_others(chosen, windows) -> None:
        for window in windows:
            if window.handle != chosen.handle:
                try:
                    window.close()
                except (AttributeError, RuntimeError):
                    pass

    def _still_valid_after_settling(handle, delay: float = 0.3) -> bool:
        # Se vio en la practica que puede aparecer una ventana transitoria
        # (un "flash" de carga) que pasa las validaciones de
        # IsWindow/GetWindowRect en el instante en que se detecta, pero
        # deja de existir un instante despues, siendo reemplazada por la
        # ventana real del informe. Por eso ningun candidato se confirma de
        # inmediato: se espera un poco y se vuelve a validar el mismo
        # handle antes de aceptarlo.
        time.sleep(delay)
        return _is_real_window(handle) and _window_rect(handle) is not None

    def _window_at_cursor_outside_vue():
        # En esta instalacion de Vue PACS la ventana de informe pertenece a
        # un proceso distinto del proceso principal y no aparece nunca en
        # desktop_uia.windows() (se comprobo en la practica: ni el
        # reconocimiento visual por plantilla ni la enumeracion de UI
        # Automation la detectan, aunque este realmente pintada en
        # pantalla). Como unico dato fiable que sí la ubica esta el propio
        # cursor, que quedo sobre ella tras el clic en 'Ver informes': se
        # resuelve su ventana de nivel superior por Win32 puro
        # (WindowFromPoint + GetAncestor), sin leer ningun contenido.
        try:
            cursor_point, cursor_pid = _cursor_position_and_process_id()
        except CaptureError:
            return None
        if not cursor_pid or cursor_pid == main_window.process_id():
            return None
        point_handle = _window_handle_at_point(cursor_point)
        root_handle = _ancestor_root_handle(point_handle) if point_handle else None
        if (
            root_handle
            and root_handle not in before
            and _is_real_window(root_handle)
            and _window_rect(root_handle) is not None
        ):
            return root_handle
        return None

    deadline = time.monotonic() + timeout
    last_new_windows: list = []
    last_foreground_class = ""
    last_focused_class = ""
    last_content_metrics: list = []
    while time.monotonic() < deadline:
        if _stop_pressed():
            raise StopRequested()
        cursor_candidate = _window_at_cursor_outside_vue()
        if cursor_candidate is not None and _still_valid_after_settling(
            cursor_candidate
        ):
            return desktop_win32.window(handle=cursor_candidate)
        new_windows = [
            window
            for window in desktop_uia.windows()
            if window.is_visible()
            and window.handle not in before
            and _is_real_window(window.handle)
            and _window_rect(window.handle) is not None
        ]
        if len(new_windows) == 1:
            candidate = new_windows[0]
            if _still_valid_after_settling(candidate.handle):
                return candidate
        if len(new_windows) > 1:
            # Algunas plantillas de Vue PACS reportan la misma ventana de
            # informe con mas de un handle, y a veces la ventana real (la
            # que efectivamente pasa a primer plano) todavia se esta
            # creando y aun no aparece en este snapshot. Por eso no se
            # aborta en el primer intento sin coincidencia: se sigue
            # reintentando hasta el timeout.
            #
            # GetForegroundWindow() solo devuelve ventanas de nivel superior;
            # en una app MDI como Vue PACS eso normalmente es el marco
            # principal, no la ventana de informe. Por eso tambien se
            # comprueba, via GetGUIThreadInfo, cual es el CONTROL que
            # realmente tiene el foco de teclado, y si ese control esta
            # dentro (es descendiente) de alguna de las ventanas nuevas. Si
            # exactamente una ventana nueva coincide (por handle exacto o
            # por contener al control con foco), se usa esa; las demas se
            # cierran para no dejar ventanas sueltas.
            foreground = _foreground_window_handle()
            focused_control = _focused_control_handle()
            foreground_matches = [
                window
                for window in new_windows
                if window.handle == foreground
                or _window_contains_handle(window.handle, focused_control)
            ]
            if len(foreground_matches) == 1:
                chosen = foreground_matches[0]
                if _still_valid_after_settling(chosen.handle):
                    _close_others(chosen, new_windows)
                    return chosen
            # En esta plantilla de Vue PACS, TODAS las ventanas comparten la
            # misma clase Win32 autogenerada, asi que ni la clase ni el
            # primer plano ni el foco distinguen cual es la ventana con el
            # informe. Como ultimo recurso (nunca leyendo el contenido, solo
            # su longitud y el tamano de la ventana) se elige la que tiene
            # texto sustancialmente mayor que las demas.
            content_choice, content_metrics = _select_report_window_by_content(
                new_windows
            )
            if content_choice is not None and _still_valid_after_settling(
                content_choice.handle
            ):
                _close_others(content_choice, new_windows)
                return content_choice
            last_new_windows = new_windows
            last_foreground_class = _foreground_window_class_name()
            last_focused_class = _focused_control_class_name()
            last_content_metrics = content_metrics
        time.sleep(0.2)
    if last_new_windows:
        classes = _window_classes(last_new_windows)
        metrics_text = "; ".join(
            f"area={area}, texto={text_length}, hijos={descendant_count}"
            for _window, area, text_length, descendant_count in last_content_metrics
        )
        raise CaptureError(
            f"Se abrieron {len(last_new_windows)} ventanas inesperadas "
            f"(clases: {', '.join(classes)}); ninguna coincidió nunca con la "
            f"ventana en primer plano (última clase vista: {last_foreground_class}) "
            f"ni contenía al control con foco de teclado (última clase vista: "
            f"{last_focused_class}); tampoco se distinguió por contenido "
            f"({metrics_text}); captura detenida."
        )
    raise CaptureError(
        "No se detectó una ventana nueva de informe. No se cerrará ninguna ventana."
    )


def capture_reports(
    output: Path,
    title_pattern: str,
    max_cases: int,
    timeout: float,
) -> tuple[int, int]:
    Desktop, keyboard, mouse, find_elements = _require_automation()
    desktop_uia = Desktop(backend="uia")
    desktop_win32 = Desktop(backend="win32")
    main_window = _find_main_window(desktop_uia, title_pattern)
    saved = 0
    duplicates = 0
    print(
        f"Captura supervisada: máximo {max_cases} informes. "
        "Mantén F12 pulsado para detener."
    )
    print("Selecciona la primera fila en Vue PACS. Inicio en 5 segundos...")
    time.sleep(5)


    for case_index in range(max_cases):
        report_window = None
        try:
            if _stop_pressed():
                raise StopRequested()
            _clear_clipboard()
            report_window = _open_report(
                main_window,
                desktop_uia,
                desktop_win32,
                keyboard,
                mouse,
                find_elements,
                timeout,
            )
            report_handle = getattr(report_window, "handle", None)
            click_point = _window_content_click_point(report_handle)
            report_rect = _window_rect(report_handle)
            report_class = None
            try:
                report_class = report_window.class_name()
            except (AttributeError, RuntimeError):
                report_class = "?"
            print(
                f"Ventana de informe detectada: clase={report_class}, "
                f"rect={report_rect}, clic en={click_point}."
            )

            focus_reported = False
            attempts = 0

            def _focus_click_and_copy() -> None:
                nonlocal focus_reported, attempts
                attempts += 1
                _force_foreground(report_handle)
                report_window.set_focus()
                # Ctrl+A + Ctrl+C primero: es mucho mas rapido que abrir dos
                # menus contextuales y, una vez que el panel de contenido
                # tiene el foco de verdad, funciona igual que a mano. El
                # clic izquierdo previo es justo lo que le da ese foco (el
                # panel es un control embebido, no lo recibe solo con
                # set_focus sobre la ventana). Si tras varios intentos el
                # portapapeles sigue vacio, se recurre al menu contextual
                # del propio panel, que ya se comprobo que funciona.
                if click_point is not None:
                    mouse.click(button="left", coords=click_point)
                    time.sleep(0.1)
                if click_point is None or attempts <= COPY_KEYBOARD_ATTEMPTS:
                    keyboard.send_keys("^a")
                    keyboard.send_keys("^c")
                else:
                    if attempts == COPY_KEYBOARD_ATTEMPTS + 1:
                        print(
                            "Ctrl+A/Ctrl+C no llenó el portapapeles; "
                            "se pasa al menú contextual del panel."
                        )
                    _copy_report_content_via_context_menu(
                        mouse,
                        desktop_uia,
                        desktop_win32,
                        click_point,
                        main_window.process_id(),
                        find_elements,
                        timeout,
                    )
                if not focus_reported:
                    focus_reported = True
                    foreground_after_click = _foreground_window_handle()
                    focused_after_click = _focused_control_handle()
                    print(
                        "Después del clic: ventana en primer plano="
                        f"{foreground_after_click} (clase="
                        f"{_foreground_window_class_name()}), control con foco="
                        f"{focused_after_click} (clase="
                        f"{_focused_control_class_name()}), handle de la "
                        f"ventana de informe={report_handle}."
                    )

            # La ventana de informe puede tardar en terminar de dibujarse.
            # Un solo intento de clic + Ctrl+A + Ctrl+C justo despues de
            # detectar la ventana puede caer antes de que el control de
            # contenido este listo, dejando el portapapeles vacio sin
            # segunda oportunidad. Por eso se reintenta el ciclo completo
            # (no solo la lectura del portapapeles) mientras no se detecte
            # contenido valido, hasta agotar el timeout.
            deadline = time.monotonic() + timeout
            copied = ""
            next_retry_at = 0.0
            while time.monotonic() < deadline:
                if _stop_pressed():
                    raise StopRequested()
                if time.monotonic() >= next_retry_at:
                    _focus_click_and_copy()
                    next_retry_at = time.monotonic() + 0.7
                copied = _clipboard_text()
                if SECTION_DATA.search(copied) and SECTION_FINDINGS.search(copied):
                    break
                time.sleep(0.2)
            if not copied:
                raise CaptureError("El informe no llegó al portapapeles.")
            candidate = build_review_candidate(parse_report(copied))
            if append_candidate(output, candidate):
                saved += 1
                print(f"Guardado local: {candidate['review_case_id']}")
            else:
                duplicates += 1
                print("Duplicado omitido.")
        finally:
            _clear_clipboard()
            if report_window is not None:
                # Cierre en el mejor esfuerzo: si la ventana ya no esta en
                # un estado cerrable (por ejemplo porque el usuario la
                # cerro, o porque nunca llego a mostrarse del todo), no
                # dejar que el error de cierre tape el error original
                # (p.ej. "El informe no llegó al portapapeles").
                try:
                    report_window.close()
                except Exception:
                    pass

        if case_index + 1 < max_cases:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if _foreground_process_id() == main_window.process_id():
                    break
                time.sleep(0.1)
            _require_vue_focus(main_window)
            keyboard.send_keys("{DOWN}")
            time.sleep(0.5)
    return saved, duplicates


def probe(title_pattern: str) -> None:
    Desktop, keyboard, mouse, find_elements = _require_automation()
    desktop_uia = Desktop(backend="uia")
    desktop_win32 = Desktop(backend="win32")
    main_window = _find_main_window(desktop_uia, title_pattern)
    print(
        "En 5 segundos: vuelve a Vue PACS, selecciona una fila y deja "
        "el puntero encima de esa misma fila."
    )
    time.sleep(5)
    _require_vue_focus(main_window)
    _right_click_vue_at_cursor(main_window, mouse)
    try:
        diagnostics = {}
        menu_match = _find_report_menu_item(
            desktop_uia,
            desktop_win32,
            1,
            process_id=main_window.process_id(),
            find_elements=find_elements,
            diagnostics=diagnostics,
        )
        if menu_match is None:
            visual_target, visual_score = _verified_visual_report_target(main_window)
            if visual_target is not None:
                print(
                    "OK: menú gráfico localizado mediante plantilla visual local "
                    f"(coincidencia {visual_score:.3f})."
                )
                return
            raise CaptureError(
                "Vue PACS está visible, pero 'Ver informes' no es accesible "
                "mediante UIA ni Win32. Diagnóstico sin datos clínicos: "
                f"menús UIA={diagnostics['uia_menu_windows']}, "
                f"elementos UIA exactos={diagnostics['uia_descendant_items']}, "
                f"popups Win32={diagnostics['win32_popups']}, "
                "popups Win32 descendientes="
                f"{diagnostics['win32_descendant_popups']}, "
                f"coincidencia visual={visual_score:.3f}."
            )
        backend, _ = menu_match
        print(
            "OK: ventana Vue PACS única y menú 'Ver informes' accesible "
            f"mediante {backend.upper()}."
        )
    finally:
        keyboard.send_keys("{ESC}")


def candidate_section_labels(text: str) -> list[str]:
    """Devuelve solo las etiquetas de posibles encabezados (antes de ':').

    Nunca devuelve lo que sigue al ':' en la misma línea, así que no expone
    valores clínicos, fechas ni identificadores: solo la palabra o frase
    corta que parece un encabezado (p. ej. "Técnica", "Hallazgos").
    """
    labels: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = LABEL_LINE.match(line)
        if not match:
            continue
        label = match.group(1).strip()
        key = normalized(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def diagnose_clipboard() -> None:
    """Indica que encabezados de sección se detectan en el portapapeles y si
    aparecen en el orden que exige parse_report.

    Nunca imprime el contenido clínico, solo conteos y booleanos. No borra
    el portapapeles: podés correr --parse-clipboard justo después sin volver
    a copiar. Util cuando --parse-clipboard falla, para saber si es un
    problema de encabezados ausentes o de orden entre secciones.
    """
    text = _clipboard_text()
    clean = text.replace("\r\n", "\n")
    print(f"Caracteres en el portapapeles: {len(clean)}")
    if not clean.strip():
        print("El portapapeles está vacío: repite Ctrl+A y Ctrl+C dentro del informe.")
        return

    data_matches = list(SECTION_DATA.finditer(clean))
    exploration_matches_all = list(SECTION_EXPLORATION.finditer(clean))
    findings_matches = list(SECTION_FINDINGS.finditer(clean))
    impression_matches = list(SECTION_IMPRESSION.finditer(clean))

    print(f"'Datos clínicos' encontrado: {bool(data_matches)} (x{len(data_matches)})")
    print(f"'Exploración' encontrado: {bool(exploration_matches_all)} (x{len(exploration_matches_all)})")
    print(f"'Hallazgos' encontrado: {bool(findings_matches)} (x{len(findings_matches)})")
    print(f"'Impresión diagnóstica' encontrado: {bool(impression_matches)} (x{len(impression_matches)})")

    if data_matches and findings_matches:
        data_match = data_matches[-1]
        findings_match = next(
            (match for match in findings_matches if match.start() > data_match.start()),
            None,
        )
        print(
            "'Hallazgos' aparece después del último 'Datos clínicos': "
            f"{findings_match is not None}"
        )
        if findings_match is not None:
            exploration_between = [
                match
                for match in exploration_matches_all
                if data_match.start() < match.start() < findings_match.start()
            ]
            print(
                "'Exploración' aparece entre 'Datos clínicos' y 'Hallazgos': "
                f"{bool(exploration_between)} (x{len(exploration_between)})"
            )
            impression_after = next(
                (
                    match
                    for match in impression_matches
                    if match.start() > findings_match.start()
                ),
                None,
            )
            print(
                "'Impresión diagnóstica' aparece después de 'Hallazgos': "
                f"{impression_after is not None} (si no hay ninguna, se guarda vacía)"
            )

    labels = candidate_section_labels(clean)
    if labels:
        print("Posibles etiquetas de encabezado detectadas (sin su contenido):")
        for label in labels:
            print(f"  - {label}")


def parse_clipboard_once(output: Path) -> None:
    try:
        copied = _clipboard_text()
        candidate = build_review_candidate(parse_report(copied))
        created = append_candidate(output, candidate)
        print("Caso guardado para revisión." if created else "Caso duplicado; no se guardó otra copia.")
    finally:
        _clear_clipboard()


def main() -> None:
    _ensure_dpi_awareness()
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--probe", action="store_true")
    modes.add_argument("--parse-clipboard", action="store_true")
    modes.add_argument("--diagnose-clipboard", action="store_true")
    modes.add_argument("--capture", action="store_true")
    parser.add_argument("--confirm-read-only", action="store_true")
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--window-title-pattern", default=DEFAULT_WINDOW_PATTERN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.max_cases < 1 or args.max_cases > 5:
        raise SystemExit("El prototipo permite entre 1 y 5 casos por ejecución.")
    if args.capture and not args.confirm_read_only:
        raise SystemExit("La captura requiere --confirm-read-only.")

    try:
        if args.probe:
            probe(args.window_title_pattern)
        elif args.parse_clipboard:
            parse_clipboard_once(args.output)
        elif args.diagnose_clipboard:
            diagnose_clipboard()
        else:
            saved, duplicates = capture_reports(
                args.output,
                args.window_title_pattern,
                args.max_cases,
                args.timeout,
            )
            print(f"Finalizado: {saved} guardados, {duplicates} duplicados.")
    except StopRequested:
        print("Captura detenida con F12; los casos ya guardados permanecen intactos.")
    except CaptureError as error:
        raise SystemExit(f"Captura detenida de forma segura: {error}") from error


if __name__ == "__main__":
    main()
