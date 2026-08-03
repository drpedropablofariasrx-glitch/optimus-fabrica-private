#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
optimus_app.py — Fábrica radiológica multirregión OPTIMUS
====================================================================

Qué hace, en una frase: pegas un caso bruto, OpenAI genera el informe en
tus 5 bloques con tus reglas siempre puestas, el validador lo revisa solo,
y guardas el caso limpio en TU disco.

Cómo se usa (lo más simple posible):
    1) Instala las dos librerías (una sola vez):
         pip install flask openai anthropic
    2) Pon tu clave de OpenAI (una sola vez por sesión):
         - Windows PowerShell:  $env:OPENAI_API_KEY="sk-...."
         - o escríbela en la casilla de la propia página al abrirla.
    3) Ejecuta:
         python optimus_app.py
    4) Abre el navegador en:  http://localhost:5000

Tus casos se guardan en la carpeta regional activa.
Nada se sube a internet salvo la llamada a OpenAI para generar el informe.

Este archivo es autónomo: incluye el prompt, el validador y la interfaz.
Cuando quieras, se le puede añadir RAG o cambiar el motor sin rehacerlo.
"""

import os
import re
import json
import logging
import importlib.util
import unicodedata
from datetime import datetime
from pathlib import Path
from region_registry import list_regions, get_region_config, load_region_prompt, load_region_validator
from provider_llama_cpp import LlamaCppProvider, ProviderError

# --- dependencias externas (se instalan con: pip install flask openai anthropic) ---
try:
    from flask import Flask, request, jsonify, Response
except ImportError:
    raise SystemExit("Falta Flask. Ejecuta:  pip install flask openai anthropic anthropic")

# El cliente de OpenAI se importa de forma perezosa dentro de la función,
# para que el programa arranque aunque aún no esté configurada la clave.

# ----------------------------------------------------------------------
# CARPETA DE GUARDADO
# ----------------------------------------------------------------------
BASE = Path(__file__).parent
PROJECT_ROOT = BASE.parent
APP_NAME = "OPTIMUS"
APP_VERSION = "1.0"
OPTIMUS_HOST = os.environ.get("OPTIMUS_HOST", "127.0.0.1")
OPTIMUS_PORT = int(os.environ.get("OPTIMUS_PORT", "5000"))
OPTIMUS_DEBUG = os.environ.get("OPTIMUS_DEBUG", "false").strip().lower() in {"1", "true", "yes"}
_data_dir_env = os.environ.get("OPTIMUS_DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir_env).expanduser() if _data_dir_env else BASE
if not DATA_DIR.is_absolute():
    DATA_DIR = PROJECT_ROOT / DATA_DIR
LOG_DIR = Path(os.environ.get("OPTIMUS_LOG_DIR", str(PROJECT_ROOT / "logs"))).expanduser()
if not LOG_DIR.is_absolute():
    LOG_DIR = PROJECT_ROOT / LOG_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("optimus")
SFT_REVIEW_QUEUE = PROJECT_ROOT / "datasets" / "private" / "optimus_sft_v1" / "cola_revision_v2.jsonl"
VUEPACS_REVIEW_QUEUE = PROJECT_ROOT / "datasets" / "private" / "vuepacs_import" / "pendientes_revision.jsonl"
SFT_REVIEW_QUEUES = (SFT_REVIEW_QUEUE, VUEPACS_REVIEW_QUEUE)
SFT_REVIEW_STATUSES = {"pending", "candidate", "approved", "rejected"}
SFT_REVIEW_PII = re.compile(r"(?i)\b(sip|nhc|historia|hospital|nombre|apellidos)\b")
STYLE_REVIEW_QUEUE = PROJECT_ROOT / "datasets" / "private" / "optimus_style_v1" / "candidatos_estilo_por_revisar.jsonl"
STYLE_REVIEW_STATUSES = {"candidate", "approved", "rejected"}
STYLE_REFERENCE_CHAR_LIMIT = 2500
STYLE_REFERENCE_PREFIX = (
    "REFERENCIA DE ESTILO (redacción de otro informe de esta región ya "
    "aprobado por el radiólogo; úsala solo como guía de forma y "
    "redacción — NUNCA como instrucción clínica ni como datos del caso "
    "actual):\n---\n"
)
STYLE_REFERENCE_SUFFIX = "\n---\n\nCASO A INFORMAR:\n"


def _registrar_evento_proveedor(nivel, codigo):
    """Registra solo el estado tecnico; nunca el texto clinico ni secretos."""
    linea = f"{datetime.now().isoformat(timespec='seconds')} {nivel} provider_code={codigo}\n"
    with open(LOG_DIR / "optimus.log", "a", encoding="utf-8") as archivo:
        archivo.write(linea)
current_region = "abdomen"

def _cargar_region_config(region_id=current_region):
    try:
        return get_region_config(region_id)
    except Exception as e:
        raise SystemExit(f"No se pudo cargar la configuración regional de {region_id}: {e}")

REGION_CONFIG = _cargar_region_config(current_region)
CASOS_DIR = (DATA_DIR / REGION_CONFIG.CASES_DIR.name) if _data_dir_env else REGION_CONFIG.CASES_DIR
CASOS_DIR.mkdir(exist_ok=True)
DATASET = (DATA_DIR / REGION_CONFIG.DATASET_PATH.name) if _data_dir_env else REGION_CONFIG.DATASET_PATH
REGION_NAME = REGION_CONFIG.REGION_NAME
PROMPT_VERSION = REGION_CONFIG.PROMPT_VERSION
VALIDATOR_VERSION = REGION_CONFIG.VALIDATOR_VERSION
DATASET_SCHEMA_VERSION = REGION_CONFIG.DATASET_SCHEMA_VERSION
DEFAULT_PROVIDER = os.environ.get("OPTIMUS_PROVIDER", os.environ.get("LLM_PROVIDER", "openai")).strip().lower()


def _modelo_entorno_o_predeterminado(env_name: str, predeterminado: str) -> str:
    value = (os.environ.get(env_name, "") or "").strip()
    return predeterminado if not value or value.lower().startswith("sk-") else value


DEFAULT_MODELS = {
    "openai": _modelo_entorno_o_predeterminado("OPENAI_MODEL", "gpt-4.1-mini"),
    "anthropic": _modelo_entorno_o_predeterminado("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
    "deepseek": _modelo_entorno_o_predeterminado("DEEPSEEK_MODEL", "deepseek-chat"),
    "llama_cpp": os.environ.get("OPTIMUS_LLAMA_MODEL", ""),
    "mock": "mock-radiology",
}
DEFAULT_MODEL = DEFAULT_MODELS.get(DEFAULT_PROVIDER, DEFAULT_MODELS["openai"])
LAST_GENERATION_METADATA = {}


def _modelo_configurado(proveedor: str) -> str:
    """Lee un modelo configurado sin permitir que una clave se use o exponga como modelo."""
    _, _, env_model = _provider_env_names(proveedor)
    value = (os.environ.get(env_model, "") if env_model else "").strip()
    return "" if value.lower().startswith("sk-") else value


def _llama_provider(modelo=None):
    return LlamaCppProvider(
        base_url=os.environ.get("OPTIMUS_LLAMA_BASE_URL", "http://127.0.0.1:8080"),
        model=modelo or os.environ.get("OPTIMUS_LLAMA_MODEL", ""),
        timeout_seconds=os.environ.get("OPTIMUS_LLAMA_TIMEOUT_SECONDS", "120"),
        api_key=os.environ.get("OPTIMUS_LLAMA_API_KEY", ""),
        health_path=os.environ.get("OPTIMUS_LLAMA_HEALTH_PATH", "/health"),
        max_tokens=os.environ.get("OPTIMUS_LLAMA_MAX_TOKENS", "") or None,
    )

# ======================================================================
#  1) EL PROMPT DE SISTEMA — region activa
# ======================================================================
def _cargar_system_prompt(path=None):
    if path is None:
        try:
            return load_region_prompt(current_region)
        except Exception as e:
            raise SystemExit(f"No se pudo cargar el SYSTEM_PROMPT de abdomen: {e}")
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise SystemExit(f"No se encontró el SYSTEM_PROMPT de abdomen: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise SystemExit(f"El SYSTEM_PROMPT de abdomen está vacío: {prompt_path}")
    return prompt.rstrip("\n")


def _nombre_region(region_id):
    try:
        return get_region_config(region_id).REGION_NAME
    except Exception:
        return region_id

SYSTEM_PROMPT = _cargar_system_prompt()

# ----------------------------------------------------------------------
# CONFIGURACIÓN EDITABLE DESDE EL CHAT DE SISTEMA
# ----------------------------------------------------------------------
CONFIG_PATH = REGION_CONFIG.PROMPT_CONFIG_PATH
HISTORIAL_DIR = REGION_CONFIG.PROMPT_HISTORY_DIR   # copias de respaldo del prompt, para deshacer
HISTORIAL_DIR.mkdir(exist_ok=True)


def cargar_config():
    """Carga overrides/borradores del prompt sin modificar el prompt base versionado."""
    cfg = {
        "prompt_override": None,
        "prompt_draft": None,
        "prompt_override_version": None,
        "prompt_draft_version": None,
        "prompt_events": [],
        "notas": [],
        "version": 1,
        "updated_at": None,
    }
    if CONFIG_PATH.exists():
        try:
            existente = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(existente, dict):
                legacy_prompt = existente.pop("system_prompt", None)
                if legacy_prompt and not existente.get("prompt_override"):
                    if legacy_prompt.strip() != SYSTEM_PROMPT.strip():
                        existente["prompt_override"] = legacy_prompt
                        existente["prompt_override_version"] = f"{PROMPT_VERSION}+legacy"
                cfg.update(existente)
                if legacy_prompt is not None:
                    cfg["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    else:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def guardar_config(cfg):
    cfg["updated_at"] = datetime.now().isoformat(timespec="seconds")
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def diff_prompts(viejo, nuevo):
    """Devuelve un diff legible línea a línea: qué se quita (-) y qué se añade (+)."""
    import difflib
    viejo_l = (viejo or "").splitlines()
    nuevo_l = (nuevo or "").splitlines()
    salida = []
    for linea in difflib.unified_diff(viejo_l, nuevo_l, lineterm="", n=1):
        if linea.startswith("+++") or linea.startswith("---") or linea.startswith("@@"):
            continue
        if linea.startswith("+"):
            salida.append("＋ " + linea[1:])
        elif linea.startswith("-"):
            salida.append("－ " + linea[1:])
    return "\n".join(salida) if salida else "(sin diferencias de texto)"


APP_CONFIG = cargar_config()
PROMPT_BASE = SYSTEM_PROMPT

def prompt_efectivo():
    override = (APP_CONFIG.get("prompt_override") or "").strip()
    return override or PROMPT_BASE

def prompt_version_efectiva():
    if (APP_CONFIG.get("prompt_override") or "").strip():
        return APP_CONFIG.get("prompt_override_version") or f"{PROMPT_VERSION}+override"
    return PROMPT_VERSION

def _registrar_evento_prompt(action, diff, source_version, target_version, motivo=""):
    APP_CONFIG.setdefault("prompt_events", []).append({
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "usuario": "radiologo",
        "accion": action,
        "version_origen": source_version,
        "version_destino": target_version,
        "diff": diff,
        "motivo": motivo or "",
    })

def _siguiente_override_version():
    count = len([e for e in APP_CONFIG.get("prompt_events", []) if e.get("accion") == "aplicar_override"]) + 1
    return f"{PROMPT_VERSION}+override.{count}"

SYSTEM_PROMPT = prompt_efectivo()
# propuesta pendiente: guarda también el prompt ANTERIOR para poder mostrar diff y deshacer
ULTIMA_PROPUESTA = {"prompt": None, "respuesta": None, "prompt_anterior": None}

# Bandeja de reglas candidatas extraídas de tus correcciones (propone, no aplica)
REGLAS_CANDIDATAS = REGION_CONFIG.CANDIDATES_PATH


def proponer_regla_desde_correccion(caso, informe_ia, informe_final, nota, proveedor, key, modelo):
    """
    Dado el informe de la IA y tu versión corregida, pide al modelo que juzgue
    si la diferencia esconde una REGLA generalizable o es solo un cambio puntual.
    Devuelve un dict, o None si no se pudo. NUNCA aplica nada: solo propone.
    """
    diff = diff_prompts(informe_ia, informe_final)
    if not diff or diff == "(sin diferencias de texto)":
        if not nota:
            return None
    system = (
        "Eres un analista de correcciones radiológicas. Recibes el informe que generó una IA "
        "y la versión corregida por el radiólogo. Tu tarea es decidir si la diferencia revela una "
        "REGLA generalizable (aplicable a futuros informes) o si es un cambio PUNTUAL de ese caso.\n"
        "Devuelve SOLO JSON válido con estas claves:\n"
        '  "tipo": "regla" | "puntual",\n'
        '  "categoria": "formato" | "terminologia" | "estilo" | "contencion_diagnostica" | "ortografia" | "otro",\n'
        '  "regla": "enunciado breve y accionable de la regla, en imperativo" (vacío si es puntual),\n'
        '  "motivo": "una frase explicando por qué es regla o por qué es puntual".\n'
        "Sé conservador: si el cambio no tiene patrón claro, márcalo como puntual."
    )
    user = f"INFORME IA:\n{informe_ia}\n\nINFORME CORREGIDO:\n{informe_final}\n\nNOTA DEL RADIÓLOGO:\n{nota or '(sin nota)'}\n\nDIFERENCIAS:\n{diff}\n\nDevuelve JSON."
    try:
        raw = _llm_chat_text(proveedor, key, modelo, system, user)
        obj = _extraer_json(raw)
    except Exception:
        return None
    return obj

# ======================================================================
#  2) EL VALIDADOR — fuente única regional
# ======================================================================
def _norm(t):
    t = t.lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

def _cargar_validador_regional(path=None):
    if path is None:
        try:
            return load_region_validator(current_region)
        except Exception as e:
            raise SystemExit(f"No se pudo cargar el validador regional de abdomen: {e}")
    validator_path = Path(path or REGION_CONFIG.VALIDATOR_MODULE)
    if not validator_path.exists():
        raise SystemExit(f"No se encontró el validador regional de abdomen: {validator_path}")
    spec = importlib.util.spec_from_file_location("optimus_validador_abdomen", validator_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise SystemExit(f"No se pudo cargar el validador regional de abdomen: {e}")
    if not hasattr(module, "validar"):
        raise SystemExit(f"El validador regional de abdomen no expone validar(): {validator_path}")
    return module

VALIDADOR_REGIONAL = _cargar_validador_regional()

def activar_region(region_id):
    """Cambia la region activa y recarga todos sus recursos regionales."""
    global current_region, REGION_CONFIG, CASOS_DIR, DATASET, REGION_NAME
    global PROMPT_VERSION, VALIDATOR_VERSION, DATASET_SCHEMA_VERSION
    global CONFIG_PATH, HISTORIAL_DIR, APP_CONFIG, PROMPT_BASE, SYSTEM_PROMPT
    global VALIDADOR_REGIONAL, REGLAS_CANDIDATAS, ULTIMA_PROPUESTA

    config = _cargar_region_config(region_id)
    current_region = region_id
    REGION_CONFIG = config
    REGION_NAME = config.REGION_NAME
    CASOS_DIR = (DATA_DIR / config.CASES_DIR.name) if _data_dir_env else config.CASES_DIR
    CASOS_DIR.mkdir(exist_ok=True)
    DATASET = (DATA_DIR / config.DATASET_PATH.name) if _data_dir_env else config.DATASET_PATH
    PROMPT_VERSION = config.PROMPT_VERSION
    VALIDATOR_VERSION = config.VALIDATOR_VERSION
    DATASET_SCHEMA_VERSION = config.DATASET_SCHEMA_VERSION
    CONFIG_PATH = config.PROMPT_CONFIG_PATH
    HISTORIAL_DIR = config.PROMPT_HISTORY_DIR
    HISTORIAL_DIR.mkdir(exist_ok=True)
    PROMPT_BASE = _cargar_system_prompt()
    SYSTEM_PROMPT = PROMPT_BASE
    APP_CONFIG = cargar_config()
    SYSTEM_PROMPT = prompt_efectivo()
    VALIDADOR_REGIONAL = _cargar_validador_regional()
    REGLAS_CANDIDATAS = config.CANDIDATES_PATH
    ULTIMA_PROPUESTA = {"prompt": None, "respuesta": None, "prompt_anterior": None}
    return config

def _flag_a_dict(flag):
    if isinstance(flag, dict):
        out = {
            "regla": flag.get("regla", ""),
            "gravedad": flag.get("gravedad", ""),
            "mensaje": flag.get("mensaje", ""),
            "bloquea_gold": bool(flag.get("bloquea_gold", False)),
        }
    else:
        out = {
        "regla": getattr(flag, "regla", ""),
        "gravedad": getattr(flag, "gravedad", ""),
        "mensaje": getattr(flag, "mensaje", ""),
        "bloquea_gold": bool(getattr(flag, "bloquea_gold", False)),
        }
    regla = out["regla"]
    mensaje = (out["mensaje"] or "").lower()
    if "error interno" in mensaje:
        out["bloquea_gold"] = True
    if regla in {"D8", "D9", "D10", "D11", "D12"} and out["gravedad"] == "alta":
        out["bloquea_gold"] = True
    return out

def _flags_metainfo_visible(texto):
    flags = []
    n = _norm(texto or "")
    patrones = [
        (r"\btags?\s*(?:/|:|$)", "TAGS"),
        (r"\betiquetas\s*(?:/|:|$)", "ETIQUETAS"),
        (r"dataset[_\s-]*entry", "DATASET_ENTRY"),
        (r"analisis estructurado del caso", "ANÁLISIS ESTRUCTURADO DEL CASO"),
    ]
    for pat, etiqueta in patrones:
        if re.search(pat, n):
            flags.append({"regla":"META_VISIBLE","gravedad":"alta",
                "mensaje":f"El informe visible contiene metainformación interna ({etiqueta}). Revisar y retirarla antes de guardar/copiar al PACS.",
                "bloquea_gold":True})
    return flags

def _tiene_metainfo_visible(texto):
    return bool(_flags_metainfo_visible(texto))

def validar(texto, metadata=None):
    """Devuelve lista de dicts: {regla, gravedad, mensaje}."""
    if current_region == "torax":
        regionales = VALIDADOR_REGIONAL.validar(texto, metadata or {})
    else:
        regionales = VALIDADOR_REGIONAL.validar(texto)
    flags = [_flag_a_dict(f) for f in regionales]
    flags.extend(_flags_metainfo_visible(texto))
    return flags

# ======================================================================
#  3) LLAMADAS A MODELOS — OpenAI, Claude y DeepSeek
# ======================================================================
def _openai_compat_chat(client, modelo, system, user):
    """
    Llama a un modelo compatible con la API de OpenAI (OpenAI o DeepSeek).
    Intenta con temperature=0.2 (más preciso). Si el modelo no admite cambiar
    la temperatura (algunos GPT-5 y modelos de razonamiento solo aceptan la
    por defecto), reintenta sin ese parámetro en vez de fallar.
    """
    mensajes = [{"role":"system","content":system}, {"role":"user","content":user}]
    try:
        resp = client.chat.completions.create(model=modelo, messages=mensajes, temperature=0.2)
    except Exception as e:
        if "temperature" in str(e).lower():
            # el modelo no acepta temperatura personalizada -> reintentar sin ella
            resp = client.chat.completions.create(model=modelo, messages=mensajes)
        else:
            raise
    content = getattr(resp.choices[0].message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    # Algunos modelos recientes pueden completar la petición legacy pero no
    # entregar texto en message.content. En ese caso usamos Responses API,
    # que expone el resultado de texto como output_text.
    responses = getattr(client, "responses", None)
    if responses and hasattr(responses, "create"):
        try:
            response = responses.create(
                model=modelo,
                instructions=system,
                input=user,
                temperature=0.2,
            )
        except Exception as exc:
            if "temperature" not in str(exc).lower():
                raise RuntimeError("El modelo no devolvió texto en Chat Completions.") from exc
            response = responses.create(model=modelo, instructions=system, input=user)
        output_text = getattr(response, "output_text", "") or ""
        if str(output_text).strip():
            return str(output_text).strip()
    raise RuntimeError(
        "El modelo respondió correctamente, pero no devolvió texto de informe. "
        "Prueba otro modelo o revisa su compatibilidad con la API."
    )


def _texto_anthropic(resp):
    partes = []
    for bloque in getattr(resp, "content", []) or []:
        if getattr(bloque, "type", None) == "text":
            partes.append(getattr(bloque, "text", ""))
        elif isinstance(bloque, dict) and bloque.get("type") == "text":
            partes.append(bloque.get("text", ""))
    return "\n".join(p for p in partes if p).strip()

def generar_informe(caso_bruto, api_key, modelo=None, proveedor=None):
    global LAST_GENERATION_METADATA
    proveedor = (proveedor or DEFAULT_PROVIDER or "openai").strip().lower()
    if proveedor in {"claude", "anthropic"}:
        proveedor = "anthropic"
    modelo = (modelo or DEFAULT_MODELS.get(proveedor) or DEFAULT_MODEL).strip()
    LAST_GENERATION_METADATA = {"provider": proveedor, "model": modelo, "status": "success"}

    if proveedor == "mock":
        return "Datos clínicos: no aportados.\nHallazgos: informe simulado; revisar el dictado clínico.\nImpresión diagnóstica: generación simulada."

    if proveedor == "llama_cpp":
        try:
            result = _llama_provider(modelo).generate(SYSTEM_PROMPT, caso_bruto)
        except ProviderError as exc:
            _registrar_evento_proveedor("WARNING", exc.code)
            LAST_GENERATION_METADATA = {"provider": "llama_cpp", "model": modelo, "status": "error", "error_code": exc.code}
            raise RuntimeError(f"{exc.code}: {exc}") from exc
        LAST_GENERATION_METADATA = result.metadata
        return result.content

    if proveedor == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        return _openai_compat_chat(client, modelo, SYSTEM_PROMPT, caso_bruto)

    if proveedor == "deepseek":
        # DeepSeek usa una API compatible con el SDK de OpenAI.
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        return _openai_compat_chat(client, modelo, SYSTEM_PROMPT, caso_bruto)

    if proveedor == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("Falta Anthropic. Ejecuta: pip install anthropic")
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=modelo,
            max_tokens=5000,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role":"user", "content":caso_bruto}],
        )
        return _texto_anthropic(resp)

    raise ValueError(f"Proveedor no reconocido: {proveedor}. Usa openai, anthropic, deepseek, llama_cpp o mock.")


def normalizar_formato_pacs(informe, eliminar_analisis_calidad=False):
    """Entrega texto plano para PACS sin alterar el contenido clínico."""
    text = str(informe or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("**", "")
    text = re.sub(
        r"(?im)^[ \t]*(?:\d+[.)][ \t]*)?(Datos clínicos|Exploración|Técnica|Hallazgos|Impresión diagnóstica)[ \t]*:?[ \t]*$",
        lambda match: f"{match.group(1)}:",
        text,
    )
    text = re.sub(
        r"(?im)^[ \t]*[-•][ \t]*((?:L|S)\d[ \t]*[-–][ \t]*(?:L|S)\d[ \t]*:)",
        lambda match: match.group(1),
        text,
    )
    text = re.sub(r"(?im)^[ \t]*[-•][ \t]+", "", text)
    if eliminar_analisis_calidad:
        text = re.sub(
            r"(?is)\n*(?:\d+[.)][ \t]*)?(?:análisis|analisis) de (?:calidad|oportunidades de mejora).*?$",
            "",
            text,
        )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalizar_formato_pacs_lumbar(informe):
    """Compatibilidad con las pruebas y llamadas previas de columna lumbar."""
    return normalizar_formato_pacs(informe)

# ======================================================================
#  4) INTERFAZ WEB (local)
# ======================================================================
app = Flask(__name__)

PAGINA = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fábrica Radiológica — Chat</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#f7f7f8;--panel:#fff;--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--side:#171717;--side2:#242424;--accent:#10a37f;--warn:#b54708;--danger:#b42318;--ok:#027a48;--shadow:0 16px 40px rgba(17,24,39,.09)}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif;font-size:14px}.app{display:grid;grid-template-columns:var(--col-side,292px) 6px minmax(0,1fr) 6px var(--col-admin,360px);height:100vh;overflow:hidden}.divisor{background:transparent;cursor:col-resize;position:relative;z-index:5}.divisor:hover,.divisor.activo{background:var(--accent)}.divisor::after{content:"";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:2px;height:26px;border-radius:2px;background:#cbd5e1}.divisor:hover::after{background:#fff}.sidebar{background:var(--side);color:#f4f4f5;display:flex;flex-direction:column;border-right:1px solid #303030;min-height:0}.brand{padding:14px;display:flex;gap:10px;align-items:center}.logo{width:32px;height:32px;border-radius:10px;background:var(--accent);display:grid;place-items:center;font-weight:800}.brand b{font-size:14px}.brand span{display:block;font-size:11.5px;color:#aaa;margin-top:1px}.new{margin:4px 12px 12px;border:1px solid #3d3d3d;background:#202020;color:#fff;border-radius:10px;padding:10px 12px;text-align:left}.new:hover{background:#2b2b2b}.side-title{padding:0 14px 8px;color:#aaa;font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;display:flex;justify-content:space-between}.case-list{overflow:auto;padding:0 8px 12px;flex:1}.case{padding:10px;border-radius:10px;color:#ececec;cursor:pointer;border:1px solid transparent;margin:2px 0}.case:hover{background:var(--side2);border-color:#333}.case .date{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#bdbdbd}.case .prev{font-size:13px;margin-top:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.badge{display:inline-block;margin-top:7px;margin-right:4px;padding:2px 7px;border-radius:999px;background:#263b34;color:#9ee7c7;font-size:10.5px}.badge.warn{background:#3b311d;color:#ffd58a}.badge.corr{background:#1e3448;color:#a8d4ff}.side-foot{padding:12px;border-top:1px solid #303030}.field{display:block;color:#aaa;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin:9px 0 5px}.side-foot input,.side-foot select{width:100%;background:#111;color:#fff;border:1px solid #3d3d3d;border-radius:9px;padding:9px 10px;font-size:12px}.tiny{font-size:11.5px;color:#9ca3af;line-height:1.35;margin-top:8px}.sidebtn{width:100%;border:1px solid #3d3d3d;background:#202020;color:#eaeaea;border-radius:9px;padding:8px 10px;margin-top:8px;text-align:left}.main{display:flex;flex-direction:column;height:100vh;min-width:0}.top{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--line);background:rgba(247,247,248,.9);backdrop-filter:blur(12px)}.top h1{font-size:15px;margin:0}.meta{font-size:12px;color:var(--muted);margin-top:2px}.actions{display:flex;gap:8px}.pill{border:1px solid var(--line);background:#fff;color:#374151;border-radius:999px;padding:7px 11px;font-size:12.5px;cursor:pointer}.pill.primary{background:var(--accent);border-color:var(--accent);color:#fff}.chat{flex:1;overflow:auto;padding:28px 22px 210px}.thread{max-width:980px;margin:0 auto}.welcome{text-align:center;max-width:720px;margin:8vh auto 28px}.welcome .biglogo{width:52px;height:52px;border-radius:17px;background:#111;color:white;display:grid;place-items:center;margin:0 auto 16px;font-weight:800}.welcome h2{font-size:28px;letter-spacing:-.03em;margin:0 0 8px}.welcome p{color:var(--muted);margin:0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:24px;text-align:left}.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:13px;font-size:13px;color:#374151}.card b{display:block;color:#111827;margin-bottom:4px}.msg{display:grid;grid-template-columns:36px minmax(0,1fr);gap:13px;margin:21px 0}.av{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:12px}.av.u{background:#dbeafe;color:#1d4ed8}.av.a{background:#111;color:#fff}.bubble{background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.03)}.bt{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin-bottom:8px}.pre{white-space:pre-wrap;font-family:'IBM Plex Mono',monospace;font-size:12.8px;line-height:1.55}.report{white-space:pre-wrap;min-height:230px;outline:none;font-size:14.5px;line-height:1.65}.report:focus{box-shadow:inset 0 0 0 2px rgba(16,163,127,.18);border-radius:12px}.flag{border-radius:12px;padding:10px 12px;margin-bottom:8px;font-size:13px;border:1px solid transparent}.flag.alta{background:#fef2f2;color:var(--danger);border-color:#fecaca}.flag.media{background:#fffbeb;color:var(--warn);border-color:#fde68a}.flag.ok{background:#ecfdf3;color:var(--ok);border-color:#bbf7d0}.composer{position:fixed;left:calc(var(--col-side,292px) + 6px);right:calc(var(--col-admin,360px) + 6px);bottom:0;background:linear-gradient(to top,var(--bg) 84%,rgba(247,247,248,0));padding:34px 22px 18px}.box{max-width:980px;margin:0 auto;background:#fff;border:1px solid #d1d5db;border-radius:22px;box-shadow:var(--shadow);padding:12px}.box textarea{width:100%;min-height:72px;max-height:70vh;border:0;outline:0;resize:vertical;background:transparent;line-height:1.5}.row{display:flex;align-items:center;justify-content:space-between;gap:10px}.send{width:38px;height:38px;border:0;border-radius:12px;background:var(--accent);color:white;font-size:18px;font-weight:800;cursor:pointer}.status{font-size:12.5px;color:var(--muted)}.admin{border-left:1px solid var(--line);background:#fff;display:flex;flex-direction:column;min-height:0}.admin-head{height:58px;padding:13px 16px;border-bottom:1px solid var(--line)}.admin-head b{font-size:14px}.admin-head span{display:block;color:var(--muted);font-size:12px;margin-top:2px}.admin-log{flex:1;overflow:auto;padding:14px;background:#fbfbfc}.admin-msg{border-radius:14px;padding:11px 12px;margin-bottom:10px;font-size:13px;line-height:1.45}.admin-msg.user{background:#f3f4f6}.admin-msg.bot{background:#eefbf7;border:1px solid #c7f0e3}.admin-msg.warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}.admin-compose{border-top:1px solid var(--line);padding:12px}.admin-compose textarea{width:100%;min-height:74px;resize:vertical;border:1px solid var(--line);border-radius:12px;padding:10px;outline:0}.admin-actions{display:flex;gap:8px;margin-top:8px}.admin-actions button{border:1px solid var(--line);background:#fff;border-radius:10px;padding:8px 10px;font-size:12.5px;cursor:pointer}.admin-actions button.primary{background:var(--accent);border-color:var(--accent);color:#fff}.correction{display:none;margin-top:12px}.correction textarea{width:100%;min-height:70px;border:1px solid var(--line);border-radius:12px;padding:10px;resize:vertical}.code{font-family:'IBM Plex Mono',monospace;font-size:12px;white-space:pre-wrap}.empty{color:#9ca3af;font-style:italic}@media(max-width:1150px){.app{grid-template-columns:260px minmax(0,1fr)}.divisor,.admin{display:none}.composer{left:260px;right:0}}@media(max-width:820px){.app{grid-template-columns:1fr}.sidebar,.divisor{display:none}.composer{left:0;right:0}.cards{grid-template-columns:1fr}.chat{padding-left:14px;padding-right:14px}.top{padding:0 12px}.msg{grid-template-columns:30px minmax(0,1fr);gap:10px}.av{width:30px;height:30px}}
/* Interfaz clínica: distribución estable, acciones agrupadas y estados técnicos discretos. */
:root{--bg:#f5f7fb;--surface:#fff;--side:#111827;--side2:#1f2937;--line:#dfe5ef;--ink:#172033;--muted:#67748a;--accent:#0c9f82;--accent-dark:#087961;--shadow:0 12px 30px rgba(18,35,59,.08)}
.app{grid-template-columns:320px 8px minmax(540px,1fr) 8px 336px;background:var(--bg)}
.sidebar{background:linear-gradient(180deg,#101827 0%,#0d1420 100%);border-right:0;box-shadow:10px 0 30px rgba(15,23,42,.08)}
.brand{padding:18px 16px 16px;border-bottom:1px solid rgba(255,255,255,.09)}.logo{width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#10b996,#0a8b72)}.brand span{color:#aab5c7}
.new,.sidebtn{width:calc(100% - 28px);margin:8px 14px 0!important;border-color:rgba(255,255,255,.13);background:rgba(255,255,255,.055);border-radius:10px;padding:11px 12px;font-weight:650;transition:.15s ease}.new{margin-top:16px!important;background:var(--accent);border-color:var(--accent);color:#fff}.new:hover{background:var(--accent-dark)}.sidebtn:hover{background:rgba(255,255,255,.1)}
.side-title{padding:20px 16px 7px}.case-list{padding:0 12px 14px}.case{padding:11px 10px}.side-foot{padding:14px 14px 16px;background:rgba(0,0,0,.13);border-top-color:rgba(255,255,255,.1)}.side-foot input,.side-foot select{border-color:rgba(255,255,255,.16);background:#0c1320;padding:10px}.side-foot .sidebtn{width:100%;margin:8px 0 0!important}.field{margin-top:13px}.tiny{color:#aab5c7}
.top{height:68px;padding:0 26px;background:rgba(255,255,255,.92);border-color:var(--line)}.top h1{font-size:16px}.meta{font-size:12px}.pill{padding:8px 13px;border-color:var(--line);font-weight:650}.pill.primary{background:var(--accent);border-color:var(--accent)}
.chat{padding:34px 28px 190px}.thread{max-width:1060px}.welcome{margin:7vh auto 28px}.welcome .biglogo{background:linear-gradient(135deg,#0f172a,#25334b);box-shadow:0 10px 22px rgba(15,23,42,.15)}.welcome h2{font-size:30px;color:var(--ink)}.welcome p{font-size:14px}.cards{gap:12px;margin-top:28px}.card{border-color:var(--line);border-radius:14px;padding:16px;box-shadow:0 4px 15px rgba(15,23,42,.03)}
.composer{left:calc(var(--col-side,320px) + 8px);right:calc(var(--col-admin,336px) + 8px);padding:24px 28px 18px}.box{max-width:1060px;border-color:#d7deea;border-radius:18px;padding:14px 16px;box-shadow:var(--shadow)}.box textarea{min-height:78px;font-size:14px}.send{width:42px;height:42px;border-radius:13px;background:var(--accent)}.status{min-width:0;max-width:calc(100% - 58px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}
.admin{border-left:0;background:#fff;box-shadow:-10px 0 30px rgba(15,23,42,.04)}.admin-head{height:68px;padding:16px 18px;border-color:var(--line)}.admin-log{padding:16px;background:#f8fafc}.admin-msg{border-radius:12px;padding:12px 13px}.admin-compose{padding:14px}.admin-compose textarea{min-height:84px}.admin-actions{flex-wrap:wrap;gap:7px}.admin-actions button{flex:1 1 130px;padding:9px 8px}.admin-actions button.primary{background:var(--accent);border-color:var(--accent)}
@media(max-width:1150px){.app{grid-template-columns:280px minmax(0,1fr)}.composer{left:280px;right:0}.sidebar{box-shadow:6px 0 20px rgba(15,23,42,.08)}}
.report-card{margin-top:4px;border:1px solid var(--line);border-radius:18px;overflow:hidden;background:var(--surface);box-shadow:0 6px 20px rgba(15,23,42,.05)}.report-toolbar{height:48px;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 12px;border-bottom:1px solid var(--line);background:rgba(248,250,252,.92)}.report-toolbar .report-name{font-size:12px;font-weight:750;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}.report-tools{display:flex;align-items:center;gap:6px}.report-tool{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:9px;padding:6px 9px;font:600 12px Inter,system-ui,sans-serif;cursor:pointer}.report-tool:hover{border-color:var(--accent);color:var(--accent)}.report-editor{display:block;width:100%;min-height:430px;resize:vertical;border:0;outline:0;padding:24px 26px;background:transparent;color:var(--ink);font:14.5px/1.8 Inter,system-ui,sans-serif;white-space:pre-wrap}.report-editor:focus{box-shadow:inset 0 0 0 2px rgba(16,163,127,.20)}.composer-actions{display:flex;align-items:center;gap:8px}.analyze-btn{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:12px;padding:9px 12px;font:650 12px Inter,system-ui,sans-serif;cursor:pointer}.analyze-btn:hover{border-color:var(--accent);color:var(--accent)}
/* El editor de reglas no debe competir con el flujo de informe. */
.app{grid-template-columns:320px 8px minmax(0,1fr)}#divDer,.admin{display:none}.composer{right:0}.app.admin-open{grid-template-columns:320px 8px minmax(540px,1fr) 8px 336px}.app.admin-open #divDer{display:block}.app.admin-open .admin{display:flex}.app.admin-open .composer{right:calc(var(--col-admin,336px) + 8px)}.advanced-toggle{display:inline-flex;align-items:center;gap:6px}.admin-head{height:auto;min-height:68px}.admin-head .admin-region{font-size:11px;color:var(--accent);margin-top:5px}.admin-log:empty{display:none}.admin-hint{margin:0;color:var(--muted);font-size:12px;line-height:1.45}.admin-compose{border-top:0}.admin-actions button{flex:1 1 138px}.admin-actions .admin-apply{background:var(--accent);border-color:var(--accent);color:#fff}
@media(max-width:1150px){.app.admin-open{grid-template-columns:280px minmax(0,1fr)}.app.admin-open #divDer,.app.admin-open .admin{display:none}.app.admin-open .composer{left:280px;right:0}}
html[data-theme="dark"]{--bg:#111827;--surface:#182131;--side:#0b1220;--side2:#182235;--line:#2c3a50;--ink:#e8edf6;--muted:#aab7ca;--accent:#16b895;--accent-dark:#0b8f74;--shadow:0 12px 30px rgba(0,0,0,.32)}
html[data-theme="dark"] .top{background:rgba(17,24,39,.94)}html[data-theme="dark"] .admin{background:#151e2d}html[data-theme="dark"] .admin-log{background:#111a28}html[data-theme="dark"] .card,html[data-theme="dark"] .bubble,html[data-theme="dark"] .box{background:#182131;border-color:var(--line);color:var(--ink)}html[data-theme="dark"] .card,html[data-theme="dark"] .card b{color:var(--ink)}html[data-theme="dark"] .pill,html[data-theme="dark"] .admin-actions button,html[data-theme="dark"] .report-tool,html[data-theme="dark"] .analyze-btn{background:#1e293b;color:var(--ink);border-color:var(--line)}html[data-theme="dark"] .pill.primary,html[data-theme="dark"] .admin-actions button.primary{background:var(--accent);border-color:var(--accent);color:#fff}html[data-theme="dark"] .box textarea,html[data-theme="dark"] .admin-compose textarea,html[data-theme="dark"] .correction textarea,html[data-theme="dark"] .report-editor{background:transparent;color:var(--ink)}html[data-theme="dark"] .report-toolbar{background:#151e2d}html[data-theme="dark"] .admin-compose{border-color:var(--line);background:#151e2d}html[data-theme="dark"] .admin-msg.user{background:#263246;color:var(--ink)}html[data-theme="dark"] .admin-msg.bot{background:#133b38;border-color:#1b6257;color:#dcfff6}html[data-theme="dark"] .admin-msg.warn{background:#40351a;border-color:#7a6421;color:#ffe8a2}html[data-theme="dark"] .welcome .biglogo{background:#0b1220}html[data-theme="dark"] .divisor::after{background:#5d6b81}
</style></head><body>
<div class="app" id="appShell">
<aside class="sidebar"><div class="brand"><div class="logo">R</div><div><b>Fábrica Radiológica</b><span>informes · QA · chat de sistema</span></div></div><button class="new" onclick="nuevoCaso()">+ Nuevo caso</button><button class="sidebtn" style="margin:0 14px 8px" onclick="abrirImportar()">Importar del hospital</button><button class="sidebtn" style="margin:0 14px 8px" onclick="window.location.href='/sft_revision'">Revisar SFT</button><button class="sidebtn" style="margin:0 14px 8px" onclick="window.location.href='/style_revision'">Revisar estilo</button><div class="side-title"><span>Casos</span><span id="count">—</span></div><div class="case-list" id="lista"><div class="empty">Sin casos guardados.</div></div><div class="side-foot"><label class="field">Región activa</label><select id="region" onchange="regionChanged()"><option value="abdomen">Abdomen</option><option value="lumbar">Columna lumbar</option><option value="cervical">Columna cervical</option><option value="rodilla">Rodilla</option></select><div class="tiny" id="regionDetectionHelp">Se detecta automáticamente al pegar; usa este selector solo para corregir una ambigüedad.</div><label class="field">Proveedor</label><select id="provider" onchange="providerChanged();saveConfig()"><option value="openai">OpenAI</option><option value="anthropic">Claude / Anthropic</option><option value="deepseek">DeepSeek</option></select><label class="field">Modelo</label><input id="model" list="model-presets" value="gpt-4.1-mini"><datalist id="model-presets"><option value="gpt-4.1-mini"><option value="gpt-4.1"><option value="gpt-4o-mini"><option value="gpt-5"><option value="gpt-5-mini"><option value="claude-sonnet-4-5"><option value="claude-opus-4-1"><option value="deepseek-chat"><option value="deepseek-reasoner"></datalist><button class="sidebtn" onclick="detectarModelos()">Detectar modelos disponibles</button><label class="field">Referencia de estilo</label><label style="display:flex;align-items:center;gap:7px;color:#ddd;font-size:12.5px;font-weight:400;text-transform:none;letter-spacing:normal;margin:2px 0 4px"><input type="checkbox" id="useStyleRef" style="width:auto"> Usar un ejemplo aprobado de esta región</label><label class="field">API key</label><input type="password" id="key" placeholder="opcional si usas variable de entorno"><div class="tiny" id="providerHelp">OpenAI: usa OPENAI_API_KEY si no escribes clave aquí.</div></div></aside>
<div class="divisor" id="divIzq" data-target="side"></div>
<section class="main"><header class="top"><div><h1 id="regionTitle">TC abdomen y pelvis</h1><div class="meta" id="caseMeta">Nuevo caso · sin guardar</div></div><div class="actions"><button class="pill advanced-toggle" id="advancedToggle" type="button" onclick="toggleAdminPanel()" aria-expanded="false">⚙ Estilo y reglas</button><button class="pill" id="themeToggle" type="button" onclick="toggleTheme()">Modo oscuro</button><button class="pill" onclick="revalidar()">Revalidar</button><button class="pill" onclick="copiarInforme()">Copiar</button><button class="pill primary" onclick="guardar()">Guardar</button></div></header><main class="chat" id="chat"><div class="thread" id="thread"><div class="welcome" id="welcome"><div class="biglogo">R</div><h2>¿Qué quieres revisar?</h2><p>Pega un dictado para generar un informe o un informe ya redactado para analizarlo. La región se detecta sola.</p><div class="cards"><div class="card"><b>Generar</b>Dictado → informe editable.</div><div class="card"><b>Analizar</b>Informe pegado → región y control de calidad.</div><div class="card"><b>Estilo y reglas</b>Cambia el formato en lenguaje natural desde ⚙, con vista previa antes de aplicarlo.</div></div></div></div></main><div class="composer"><div class="box"><textarea id="caso" placeholder="Pega un dictado o un informe completo; detectaré la región automáticamente…"></textarea><div class="row"><span class="status" id="estado"></span><div class="composer-actions"><button class="analyze-btn" id="analyze" type="button" onclick="analizarInformePegado()">Analizar informe</button><button class="send" id="gen" title="Generar informe" onclick="generar()">↑</button></div></div></div></div></section>
<div class="divisor" id="divDer" data-target="admin"></div>
<aside class="admin"><div class="admin-head"><b>Estilo y reglas</b><span>Habla con OPTIMUS como en ChatGPT. La propuesta se revisa antes de aplicarse.</span><div class="admin-region" id="adminRegion">Región activa</div></div><div class="admin-log" id="adminLog"></div><div class="admin-compose"><p class="admin-hint">Ej.: “En cervical no uses viñetas y describe los niveles en orden craneocaudal”.</p><textarea id="adminText" placeholder="Describe el cambio de estilo o regla que quieres…"></textarea><div class="admin-actions"><button class="primary" onclick="adminChat()">Enviar propuesta</button><button class="admin-apply" onclick="aplicarPrompt()">Aplicar cambio</button><button onclick="guardarBorradorPrompt()">Guardar borrador</button><button onclick="restaurarPromptBase()">Restaurar base</button><button onclick="verPrompt()">Ver prompt</button><button onclick="verCandidatas()">Reglas candidatas</button></div><div class="status" id="adminStatus"></div></div></aside>
</div>
<script>
let informeIA="", currentFlags=[], currentCaseId=null, currentCaseInput="", currentProvider="", currentModel="", currentGenerationMetadata={}, validacionHumana=false, fechaValidacion="", validatedBy="", caseStatus="draft", currentRegion="abdomen", currentThoraxMeta={};
const $=id=>document.getElementById(id);
function applyTheme(theme){document.documentElement.dataset.theme=theme;localStorage.setItem('fab_theme',theme);const button=$('themeToggle');if(button)button.textContent=theme==='dark'?'Modo claro':'Modo oscuro'}
function toggleTheme(){applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')}
applyTheme(localStorage.getItem('fab_theme')||'dark');
function actualizarContextoReglas(){const label=$('adminRegion');if(label)label.textContent='Región activa: '+regionLabel(currentRegion)}
function setAdminPanel(open){const shell=$('appShell'),button=$('advancedToggle');if(!shell||!button)return;shell.classList.toggle('admin-open',!!open);button.setAttribute('aria-expanded',String(!!open));localStorage.setItem('fab_admin_panel',open?'open':'closed');if(open){actualizarContextoReglas();setTimeout(()=>$('adminText')?.focus(),0)}}
function toggleAdminPanel(){setAdminPanel(!$('appShell').classList.contains('admin-open'))}
setAdminPanel(localStorage.getItem('fab_admin_panel')==='open');
function cfg(){return {provider:$('provider').value,model:$('model').value,key:$('key').value,region:currentRegion,use_style_reference:$('useStyleRef').checked}}
function regionLabel(region){return {abdomen:'TC abdomen y pelvis',lumbar:'RM columna lumbar',cervical:'RM columna cervical',rodilla:'RM rodilla',mano_muneca:'Mano y muñeca',codo:'Codo',tobillo_pie:'Tobillo y pie',torax:'Tórax'}[region]||region}
function thoraxPayload(){if(currentRegion!=='torax')return {};const get=id=>$(id)?$(id).value:'';return {study_type:get('thoraxStudyType')||'tc_torax',clinical_context:get('thoraxContext')||'general',protocol:get('thoraxProtocol')||'sin_contraste',contrast:get('thoraxContrast')||'sin_contraste',comparison_available:$('thoraxComparison')?$('thoraxComparison').checked:false}}
function renderThoraxControls(meta={}){const old=$('thoraxControls');if(old)old.remove();if(currentRegion!=='torax')return;currentThoraxMeta={...currentThoraxMeta,...meta};const box=$('caso').closest('.box');const panel=document.createElement('div');panel.id='thoraxControls';panel.className='row';panel.style.cssText='align-items:end;flex-wrap:wrap;margin-bottom:8px';panel.innerHTML=`<label class="field" style="margin:0;min-width:140px">Tipo<select id="thoraxStudyType"><option value="tc_torax">TC tórax</option><option value="angio_tc_tep">Angio-TC TEP</option><option value="cribado_pulmonar">Cribado pulmonar</option><option value="torax_abdomen_pelvis">Tórax-abdomen-pelvis</option></select></label><label class="field" style="margin:0;min-width:120px">Contexto<select id="thoraxContext"><option value="general">General</option><option value="oncologico">Oncológico</option><option value="infeccioso">Infeccioso</option><option value="trauma">Trauma</option><option value="postquirurgico">Postquirúrgico</option></select></label><label class="field" style="margin:0;min-width:120px">Protocolo<select id="thoraxProtocol"><option value="sin_contraste">Sin contraste</option><option value="con_contraste">Con contraste</option><option value="angiografico_pulmonar">Angiográfico pulmonar</option><option value="baja_dosis">Baja dosis</option><option value="tap">TAP</option></select></label><label class="field" style="margin:0;min-width:120px">Contraste<select id="thoraxContrast"><option value="sin_contraste">Sin contraste</option><option value="con_contraste">Con contraste</option></select></label><label class="field" style="margin:0;display:flex;gap:6px;align-items:center;text-transform:none"><input id="thoraxComparison" type="checkbox"> Comparación disponible</label>`;box.insertBefore(panel,$('caso'));for(const [id,key] of [['thoraxStudyType','study_type'],['thoraxContext','clinical_context'],['thoraxProtocol','protocol'],['thoraxContrast','contrast']])if(meta[key])$(id).value=meta[key];if($('thoraxComparison'))$('thoraxComparison').checked=!!meta.comparison_available}
function textoInforme(){const inf=$('informe');return inf?(inf.value||''):''}
function hayContenidoPendiente(){return !!(($('caso')&&$('caso').value.trim())||currentCaseInput||textoInforme().trim())}
async function regionChanged(){const sel=$('region');const nueva=sel.value;if(nueva===currentRegion)return;if(hayContenidoPendiente()&&!confirm('Cambiar de región limpiará el caso actual no guardado. ¿Continuar?')){sel.value=currentRegion;return}const r=await fetch('/region',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({region:nueva})});const d=await r.json();if(!r.ok||!d.ok){alert(d.error||'No se pudo cambiar de región');sel.value=currentRegion;return}currentRegion=d.region;$('regionTitle').textContent=regionLabel(currentRegion);nuevoCaso();renderThoraxControls();actualizarContextoReglas();cargarCasos();adminAdd('bot','Región activa: '+(d.region_name||currentRegion)+' · prompt '+(d.prompt_version||''))}
function saveConfig(){localStorage.setItem('fab_provider',$('provider').value);localStorage.setItem('fab_model',$('model').value)}
async function loadConfig(){const select=$('provider');for(const [value,label] of [['llama_cpp','llama.cpp local'],['mock','Mock local']])if(![...select.options].some(o=>o.value===value))select.add(new Option(label,value));const p=localStorage.getItem('fab_provider'),m=localStorage.getItem('fab_model');if(p)$('provider').value=p;else{try{const d=await (await fetch('/health')).json();if([...select.options].some(o=>o.value===d.active_provider))select.value=d.active_provider}catch(e){}}if(m)$('model').value=m;providerChanged()}
async function refreshProviderStatus(){let el=$('providerStatus');if(!el){el=document.createElement('div');el.id='providerStatus';el.className='tiny';$('providerHelp').after(el)}const selectedProvider=$('provider').value;const r=await fetch('/health?provider='+encodeURIComponent(selectedProvider));const d=await r.json();const llama=selectedProvider==='llama_cpp';const available=!llama||d.provider_reachable;const latency=currentGenerationMetadata.latency_ms!==undefined?` · última latencia ${currentGenerationMetadata.latency_ms} ms`:'';const error=currentGenerationMetadata.error_code?` · ${currentGenerationMetadata.error_code}`:'';el.textContent=`Proveedor: ${selectedProvider} · ${d.provider_model||'modelo sin especificar'} · ${available?'disponible':'no disponible'}${latency}${error}`;if(llama&&!available){$('gen').disabled=true;el.textContent+=' · Inicie llama-server y vuelva a comprobar la conexión.'}else $('gen').disabled=false}
function providerChanged(){const p=$('provider').value;const help={openai:'OpenAI: usa OPENAI_API_KEY si no escribes clave aquí.',anthropic:'Claude: usa ANTHROPIC_API_KEY si no escribes clave aquí.',deepseek:'DeepSeek: usa DEEPSEEK_API_KEY si no escribes clave aquí.',llama_cpp:'llama.cpp local: configure OPTIMUS_LLAMA_BASE_URL y arranque llama-server por separado.',mock:'Mock local: solo para pruebas, no genera informes clínicos.'};$('providerHelp').textContent=help[p]||help.openai;if(!localStorage.getItem('fab_model')){$('model').value={openai:'gpt-4.1-mini',anthropic:'claude-sonnet-4-5',deepseek:'deepseek-chat',llama_cpp:'',mock:'mock-radiology'}[p]||'gpt-4.1-mini'}refreshProviderStatus()}
function msg(role,title,html){$('welcome')?.remove();const div=document.createElement('div');div.className='msg';div.innerHTML=`<div class="av ${role==='user'?'u':'a'}">${role==='user'?'Tú':'IA'}</div><div class="bubble"><div class="bt">${title}</div>${html}</div>`;$('thread').appendChild(div);$('chat').scrollTop=$('chat').scrollHeight;return div}
const ENCABEZADOS=['Datos clínicos','Datos clinicos','Técnica','Tecnica','Exploración','Exploracion','Hallazgos','Impresión diagnóstica','Impresion diagnostica','Interpretación global','Interpretacion global','Análisis de oportunidades de mejora','Analisis de oportunidades de mejora','Oportunidades de mejora','Análisis global','Analisis global'];
function resaltarEncabezados(el){
  // pone en negrita SOLO visualmente el encabezado al inicio de cada línea (hasta los dos puntos)
  const texto=el.textContent;
  const lineas=texto.split('\n');
  const html=lineas.map(l=>{
    const m=l.match(/^(\s*)([^:]{1,45}?):(.*)$/);
    if(m){const etiqueta=m[2].trim();if(ENCABEZADOS.some(e=>etiqueta.toLowerCase()===e.toLowerCase())){return m[1]+'<strong>'+escapeHtml(m[2])+':</strong>'+escapeHtml(m[3])}}
    return escapeHtml(l);
  }).join('\n');
  el.innerHTML=html;
}
function escapeHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function marcarNoValidado(){validacionHumana=false;fechaValidacion="";validatedBy="";if(caseStatus==='validated')caseStatus='corrected';const s=$('goldStatus');if(s)s.textContent='No validado como Gold Standard'}
function validarGold(){validacionHumana=true;fechaValidacion=new Date().toISOString();validatedBy='radiologo';caseStatus='validated';const s=$('goldStatus');if(s)s.textContent='Validado como Gold Standard'}
function enfocarInforme(){const inf=$('informe');if(inf)inf.focus()}
function setReport(txt){marcarNoValidado();msg('assistant','Informe generado',`<section class="report-card"><div class="report-toolbar"><span class="report-name">Informe listo para PACS</span><div class="report-tools"><button type="button" class="report-tool" onclick="enfocarInforme()">✎ Editar</button><button type="button" class="report-tool" onclick="copiarInforme()" title="Copiar texto plano">⧉ Copiar</button></div></div><textarea id="informe" class="report-editor" spellcheck="false" aria-label="Informe editable"></textarea></section><div class="correction" id="correctionCard"><label class="field">Qué corregiste y por qué</label><textarea id="correccion" placeholder="Ej.: cambié ectasia por ureteropielocaliectasia porque es el término preciso."></textarea></div><div class="row" style="margin-top:10px;justify-content:flex-start"><button class="pill primary" onclick="validarGold()">Validar como Gold Standard</button><span class="status" id="goldStatus">No validado como Gold Standard</span></div>`);$('informe').value=txt;$('informe').addEventListener('input',()=>{$('correctionCard').style.display=(textoInforme().trim()!==informeIA.trim())?'block':'none';if(caseStatus!=='validated')caseStatus='corrected';marcarNoValidado()})}
function pintarFlags(flags){currentFlags=flags||[];let html='';if(!currentFlags.length)html='<div class="flag ok">Sin incidencias en reglas duras comprobables.</div>';else html=currentFlags.map(f=>`<div class="flag ${f.gravedad}"><b>[${f.regla}]</b> ${f.mensaje}</div>`).join('');let old=$('qaMsg');if(old)old.remove();const m=msg('assistant','Control de calidad',`<div id="qaMsg">${html}</div>`)}
async function aplicarRegionDetectada(region){if(!region||region===currentRegion)return true;const r=await fetch('/region',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({region})});const d=await r.json();if(!r.ok||!d.ok){alert(d.error||'No se pudo activar la región detectada');return false}currentRegion=d.region;$('region').value=d.region;$('regionTitle').textContent=regionLabel(currentRegion);currentThoraxMeta={};renderThoraxControls();actualizarContextoReglas();return true}
let deteccionRegionTimer=null;
async function detectarRegionPegada(){const caso=$('caso').value.trim();if(caso.length<12)return;const estado=$('estado');estado.textContent='Detectando región…';try{const r=await fetch('/detectar_region',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({caso})});const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo detectar la región');if(d.confidence==='high'&&d.region){const activada=await aplicarRegionDetectada(d.region);estado.textContent=activada?`Región detectada: ${regionLabel(d.region)}`:'No se pudo activar la región detectada';return}estado.textContent=d.region?`Posible región: ${regionLabel(d.region)} · confirma al continuar.`:'No se pudo identificar la región; puedes elegirla manualmente.'}catch(e){estado.textContent='No se pudo detectar la región automáticamente.'}}
function programarDeteccionRegion(){clearTimeout(deteccionRegionTimer);deteccionRegionTimer=setTimeout(detectarRegionPegada,180)}
async function prepararRegionDelCaso(caso){const r=await fetch('/detectar_region',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({caso})});const d=await r.json();if(!r.ok){alert(d.error||'No se pudo detectar la región');return false}if(d.confidence==='high'){const activada=await aplicarRegionDetectada(d.region);if(activada)$('estado').textContent=`Región detectada: ${regionLabel(d.region)}`;return activada}const propuesta=d.region?`Se ha detectado posible región: ${regionLabel(d.region)}. ¿Quieres usarla?`:`No se ha podido identificar con seguridad la región. ¿Quieres continuar con la región seleccionada: ${regionLabel(currentRegion)}?`;if(!confirm(propuesta))return false;return d.region?aplicarRegionDetectada(d.region):true}
async function analizarInformePegado(){const informe=$('caso').value.trim();if(!informe){alert('Pega un informe primero');return}if(!(await prepararRegionDelCaso(informe)))return;currentCaseInput=informe;currentThoraxMeta=thoraxPayload();currentProvider='';currentModel='';currentGenerationMetadata={origen:'informe_pegado',analisis:'validacion_local'};caseStatus='imported';$('analyze').disabled=true;$('estado').textContent='Analizando…';msg('user','Informe pegado',`<div class="pre"></div>`).querySelector('.pre').textContent=informe;$('caso').value='';informeIA=informe;setReport(informe);try{const r=await fetch('/validar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({informe,...currentThoraxMeta})});const d=await r.json();pintarFlags(d.flags||[]);$('caseMeta').textContent=`Informe analizado · ${regionLabel(currentRegion)}`;$('estado').textContent=`Analizado localmente · ${regionLabel(currentRegion)}`}catch(e){$('estado').textContent='No se pudo completar el análisis';msg('assistant','Error',String(e))}finally{$('analyze').disabled=false}}
async function generar(){const caso=$('caso').value.trim();if(!caso){alert('Pega un caso primero');return}if(!(await prepararRegionDelCaso(caso)))return;currentCaseInput=caso;currentThoraxMeta=thoraxPayload();caseStatus='generated';$('gen').disabled=true;$('estado').textContent='Generando…';msg('user','Dictado bruto',`<div class="pre"></div>`).querySelector('.pre').textContent=caso;$('caso').value='';try{const r=await fetch('/generar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...cfg(),...currentThoraxMeta,caso})});const d=await r.json();if(d.error||!String(d.informe||'').trim()){const error=d.error||'El modelo terminó sin devolver texto de informe. No se ha creado ni guardado ningún informe vacío.';currentGenerationMetadata={error_code:String(error).split(':')[0]||'generation_error'};msg('assistant','Error',`<div class="pre"></div>`).querySelector('.pre').textContent=error;$('estado').textContent='Error';return}informeIA=d.informe;currentProvider=d.provider||$('provider').value;currentModel=d.model||$('model').value;currentGenerationMetadata=d.generation_metadata||{};setReport(d.informe);pintarFlags(d.flags);$('estado').textContent=`Listo · ${d.provider} · ${d.model}`;$('caseMeta').textContent='Caso generado · pendiente de guardar'}catch(e){currentGenerationMetadata={error_code:'network_error'};$('estado').textContent='Error de conexión';msg('assistant','Error',String(e))}finally{$('gen').disabled=false;refreshProviderStatus()}}
async function revalidar(){const inf=$('informe');if(!inf){alert('No hay informe');return}const r=await fetch('/validar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({informe:textoInforme(),...thoraxPayload()})});pintarFlags((await r.json()).flags)}
async function guardar(){const inf=$('informe');if(!inf){alert('Genera un informe primero');return}const payload={...cfg(),...thoraxPayload(),provider:currentProvider||$('provider').value,model:currentModel||$('model').value,generation_metadata:currentGenerationMetadata,caso:currentCaseInput,informe_ia:informeIA,informe_final:textoInforme(),correccion:$('correccion')?$('correccion').value:'',validacion_humana:validacionHumana,fecha_validacion:fechaValidacion,validated_by:validatedBy,case_status:caseStatus};const r=await fetch('/guardar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok||d.error){msg('assistant','Error',`<div class="pre"></div>`).querySelector('.pre').textContent=d.error||'No se pudo guardar';return}$('caseMeta').textContent='Guardado · '+d.archivo;msg('assistant','Guardado',d.hubo_correccion?'Caso guardado con corrección.':'Caso guardado sin cambios.');currentCaseInput='';currentProvider='';currentModel='';currentGenerationMetadata={};caseStatus='draft';marcarNoValidado();if(d.candidata&&d.candidata.tipo==='regla'){adminAdd('bot','He detectado una posible regla en tu corrección: “'+(d.candidata.regla||'')+'”. Pulsa «Reglas aprendidas» para revisarla.')}cargarCasos()}
async function copiarInforme(){const inf=$('informe');if(!inf){alert('Genera un informe primero');return}
  // innerText da el texto plano SIN la negrita ni símbolos: limpio para pegar en el PACS
  const limpio=textoInforme().replace(/\u00A0/g,' ');
  try{await navigator.clipboard.writeText(limpio)}catch(e){
    // reserva por si el navegador bloquea el portapapeles
    const ta=document.createElement('textarea');ta.value=limpio;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();
  }
  // confirmación visual estilo ChatGPT: el botón dice "Copiado ✓" un momento
  const btn=[...document.querySelectorAll('.pill')].find(b=>b.textContent.trim().startsWith('Copiar')||b.textContent.trim().startsWith('Copiado'));
  if(btn){const orig=btn.textContent;btn.textContent='Copiado ✓';setTimeout(()=>{btn.textContent=orig},1500)}
  $('estado').textContent='Informe copiado (texto limpio para PACS)'}
function nuevoCaso(){$('thread').innerHTML='<div class="welcome" id="welcome"><div class="biglogo">R</div><h2>Nuevo caso</h2><p>Pega el dictado abajo para generar el informe.</p></div>';$('caso').value='';informeIA='';currentCaseInput='';currentProvider='';currentModel='';currentThoraxMeta={};caseStatus='draft';marcarNoValidado();currentCaseId=null;$('caseMeta').textContent='Nuevo caso · sin guardar';$('estado').textContent='';renderThoraxControls()}
async function abrirImportar(){
  const plantilla=await (await fetch('/plantilla_captura')).text();
  $('thread').innerHTML='';
  const cont=document.createElement('div');cont.className='msg';
  cont.innerHTML=`<div class="av">R</div><div class="bubble"><div class="role">Importar casos del hospital</div>
    <p style="margin:.2em 0 .8em">Pega aquí el texto que rellenaste en el hospital con tus casos (dictado bruto + informe). Cada caso entre los marcadores. Se guardarán todos de golpe en tu dataset.</p>
    <details style="margin-bottom:10px"><summary style="cursor:pointer;color:#10a37f">Ver / copiar la plantilla para el hospital</summary>
    <div class="pre" style="margin-top:8px">${plantilla.replace(/</g,'&lt;')}</div>
    <button class="pill" style="margin-top:6px" onclick="navigator.clipboard.writeText(\`${plantilla.replace(/`/g,'\\\\`')}\`);this.textContent='Plantilla copiada ✓'">Copiar plantilla</button></details>
    <textarea id="importText" style="width:100%;min-height:220px;font-family:ui-monospace,monospace;font-size:13px;padding:12px;border:1px solid #d1d5db;border-radius:12px" placeholder="Pega aquí tus casos capturados en el hospital…"></textarea>
    <div style="margin-top:10px"><button class="pill primary" onclick="ejecutarImportar()">Importar casos</button> <span id="impEstado" class="status"></span></div>
    <div id="impResultado" style="margin-top:12px"></div></div>`;
  $('thread').appendChild(cont);
}
async function ejecutarImportar(){
  const texto=$('importText').value.trim();
  if(!texto){alert('Pega primero los casos');return}
  $('impEstado').textContent='Importando…';
  const r=await fetch('/importar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto})});
  const d=await r.json();
  if(!d.ok){$('impEstado').textContent='';$('impResultado').innerHTML='<div class="flag media">'+(d.error||'Error')+'</div>';return}
  $('impEstado').textContent='';
  let html=`<div class="flag ok">Importados ${d.importados} de ${d.total} casos al dataset.</div>`;
  d.resultados.forEach((res,i)=>{
    if(res.estado==='importado')html+=`<div style="font-size:13px;color:#6b7280;margin:4px 0">Caso ${i+1} · ${res.region} · ${res.avisos} aviso(s) del validador</div>`;
    else html+=`<div class="flag media">Caso ${i+1} · ${res.region}: ${res.aviso}</div>`;
  });
  $('impResultado').innerHTML=html;
  cargarCasos();
}
async function cargarCasos(){const r=await fetch('/casos');const d=await r.json();$('count').textContent=d.casos.length;const lista=$('lista');if(!d.casos.length){lista.innerHTML='<div class="empty">Sin casos guardados.</div>';return}lista.innerHTML=d.casos.map(c=>`<div class="case" onclick="verCaso('${c.id}')"><div class="date">${c.fecha}</div><div class="prev">${c.preview}</div><span class="badge ${c.limpio?'':'warn'}">${c.limpio?'sin incidencias':c.nflags+' avisos'}</span>${c.corregido?'<span class="badge corr">corregido</span>':''}</div>`).join('')}
async function verCaso(id){const r=await fetch('/caso/'+id);const d=await r.json();nuevoCaso();currentThoraxMeta={study_type:d.study_type,clinical_context:d.clinical_context,protocol:d.protocol,contrast:d.contrast,comparison_available:d.comparison_available};renderThoraxControls(currentThoraxMeta);$('caso').value=d.input||'';currentCaseInput=d.input||'';currentProvider=d.proveedor||'';currentModel=d.modelo||'';msg('user','Dictado bruto',`<div class="pre"></div>`).querySelector('.pre').textContent=d.input||'';informeIA=d.informe_ia||d.informe_final||'';setReport(d.informe_final||d.informe||'');validacionHumana=!!d.validacion_humana;fechaValidacion=d.fecha_validacion||'';validatedBy=d.validated_by||'';caseStatus=d.case_status||'draft';if($('goldStatus'))$('goldStatus').textContent=validacionHumana?'Validado como Gold Standard':'No validado como Gold Standard';if((d.tiene_correccion||d.hubo_correccion)&&$('correctionCard')){$('correctionCard').style.display='block';$('correccion').value=d.correccion_radiologo||d.correccion||''}pintarFlags(d.flags||[]);$('caseMeta').textContent='Caso '+id;currentCaseId=id}
function mensajeErrorProveedor(proveedor,error){const txt=String(error||'');if(/incorrect api key|invalid_api_key|authentication/i.test(txt))return `No se pudo validar la clave de ${proveedor}. Revísala en provider_runtime.env y reinicia OPTIMUS.`;return `No se pudieron consultar los modelos de ${proveedor}. Revisa la conexión y la configuración.`}
async function detectarModelos(){$('estado').textContent='Consultando modelos…';const r=await fetch('/modelos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg())});const d=await r.json();if(d.error){$('estado').textContent=mensajeErrorProveedor($('provider').value,d.error);return}const dl=$('model-presets');dl.innerHTML=d.models.map(m=>`<option value="${m}">`).join('');if(d.preferido)$('model').value=d.preferido;$('estado').textContent=d.models.length+' modelos detectados'}
function adminAdd(cls,txt){const d=document.createElement('div');d.className='admin-msg '+cls;d.textContent=txt;$('adminLog').appendChild(d);$('adminLog').scrollTop=$('adminLog').scrollHeight;return d}
async function adminChat(){const text=$('adminText').value.trim();if(!text)return;adminAdd('user',text);$('adminText').value='';$('adminStatus').textContent='Pensando…';const r=await fetch('/admin_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...cfg(),mensaje:text})});const d=await r.json();if(d.error){adminAdd('warn',d.error)}else{adminAdd('bot',d.respuesta||'Listo.');if(d.tipo==='prompt'){if(d.diff){const div=adminAdd('bot','Cambios propuestos (revísalos antes de aplicar):');const pre=document.createElement('div');pre.className='code';pre.style.marginTop='6px';pre.textContent=d.diff;div.appendChild(pre)}adminAdd('warn','Propuesta pendiente. Pulsa “Aplicar cambio” para guardarla, o ignórala.')}}$('adminStatus').textContent=''}
async function aplicarPrompt(){const r=await fetch('/aplicar_prompt',{method:'POST'});const d=await r.json();adminAdd(d.ok?'bot':'warn',d.mensaje||d.error||'Sin cambios')}
async function guardarBorradorPrompt(){const r=await fetch('/guardar_prompt_borrador',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const d=await r.json();adminAdd(d.ok?'bot':'warn',d.mensaje||d.error||'No se pudo guardar borrador')}
async function restaurarPromptBase(){const r=await fetch('/restaurar_prompt_base',{method:'POST'});const d=await r.json();adminAdd(d.ok?'bot':'warn',d.mensaje||d.error||'Nada que restaurar')}
async function deshacerPrompt(){return restaurarPromptBase()}
async function verCandidatas(){const r=await fetch('/candidatas');const d=await r.json();if(!d.total){adminAdd('bot','No hay reglas candidatas pendientes. Se generan solas cuando corriges un informe y lo guardas.');return}adminAdd('bot','Reglas aprendidas de tus correcciones ('+d.total+' pendientes). Las marcadas como «regla» son las que valen la pena; las «puntual» probablemente no.');d.candidatas.forEach(c=>{const div=document.createElement('div');div.className='admin-msg '+(c.tipo==='regla'?'bot':'user');const et=c.tipo==='regla'?'REGLA':'puntual';div.innerHTML=`<div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;margin-bottom:4px">${et} · ${c.categoria||''}</div><div style="margin-bottom:6px">${c.regla?c.regla:'(sin regla; cambio puntual)'}</div><div style="font-size:12px;color:#6b7280">${c.motivo||''}</div>`;if(c.regla){const b1=document.createElement('button');b1.textContent='Convertir en regla';b1.style.cssText='margin-top:8px;margin-right:6px;border:1px solid #10a37f;background:#10a37f;color:#fff;border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer';b1.onclick=()=>aceptarCandidata(c.ts);div.appendChild(b1)}const b2=document.createElement('button');b2.textContent='Descartar';b2.style.cssText='margin-top:8px;border:1px solid #e5e7eb;background:#fff;border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer';b2.onclick=()=>descartarCandidata(c.ts,div);div.appendChild(b2);$('adminLog').appendChild(div)});$('adminLog').scrollTop=$('adminLog').scrollHeight}
async function aceptarCandidata(ts){const r=await fetch('/candidata_aceptar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ts})});const d=await r.json();if(!d.ok){adminAdd('warn',d.error||'No se pudo');return}if(d.diff){const div=adminAdd('bot','Cambios propuestos (revísalos antes de aplicar):');const pre=document.createElement('div');pre.className='code';pre.style.marginTop='6px';pre.textContent=d.diff;div.appendChild(pre)}adminAdd('warn',d.mensaje)}
async function descartarCandidata(ts,div){await fetch('/candidata_descartar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ts})});if(div)div.style.opacity='.4'}
async function verPrompt(){const r=await fetch('/config');const d=await r.json();const p=d.prompt_efectivo||d.system_prompt||'';adminAdd('bot','Prompt efectivo ('+(d.prompt_version||'sin versión')+'):\n\n'+p.slice(0,3500)+(p.length>3500?'\n\n[recortado en pantalla]':''))}
async function cargarRegiones(){const r=await fetch('/regiones');const d=await r.json();currentRegion=d.current_region||'abdomen';const sel=$('region');if(sel){sel.innerHTML=d.regions.filter(x=>x.enabled).map(x=>`<option value="${x.region_id}">${x.region_name}</option>`).join('');sel.value=currentRegion}$('regionTitle').textContent=regionLabel(currentRegion);renderThoraxControls();actualizarContextoReglas()}
// --- Redimensionado de columnas (arrastrar los divisores) ---
(function(){
  const root=document.documentElement;
  // restaurar tamaños guardados
  const s=localStorage.getItem('fab_col_side'), a=localStorage.getItem('fab_col_admin');
  if(s)root.style.setProperty('--col-side',s+'px');
  if(a)root.style.setProperty('--col-admin',a+'px');
  function arrastrar(divisor,cual){
    let x0,ini;
    divisor.addEventListener('mousedown',e=>{
      x0=e.clientX;
      const val=getComputedStyle(root).getPropertyValue(cual==='side'?'--col-side':'--col-admin');
      ini=parseInt(val)|| (cual==='side'?292:360);
      divisor.classList.add('activo');
      document.body.style.cursor='col-resize';
      document.body.style.userSelect='none';
      function mover(ev){
        let delta=ev.clientX-x0;
        // el panel derecho crece hacia la izquierda: invertir signo
        let nuevo = cual==='side' ? ini+delta : ini-delta;
        nuevo=Math.max(200,Math.min(640,nuevo)); // límites sensatos
        root.style.setProperty(cual==='side'?'--col-side':'--col-admin', nuevo+'px');
      }
      function soltar(){
        document.removeEventListener('mousemove',mover);
        document.removeEventListener('mouseup',soltar);
        divisor.classList.remove('activo');
        document.body.style.cursor='';document.body.style.userSelect='';
        const val=parseInt(getComputedStyle(root).getPropertyValue(cual==='side'?'--col-side':'--col-admin'));
        localStorage.setItem(cual==='side'?'fab_col_side':'fab_col_admin', val);
      }
      document.addEventListener('mousemove',mover);
      document.addEventListener('mouseup',soltar);
    });
    // doble clic = restaurar tamaño por defecto
    divisor.addEventListener('dblclick',()=>{
      root.style.setProperty(cual==='side'?'--col-side':'--col-admin', (cual==='side'?292:360)+'px');
      localStorage.removeItem(cual==='side'?'fab_col_side':'fab_col_admin');
    });
  }
  const di=document.getElementById('divIzq'), dd=document.getElementById('divDer');
  if(di)arrastrar(di,'side');
  if(dd)arrastrar(dd,'admin');
})();
const casoInput=$('caso');
if(casoInput){casoInput.addEventListener('paste',()=>setTimeout(programarDeteccionRegion,0));casoInput.addEventListener('input',programarDeteccionRegion)}
loadConfig();cargarRegiones().then(cargarCasos);
</script></body></html>"""

PAGINA_REVISION_SFT = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>OPTIMUS - Revision SFT</title>
<style>
:root{--bg:#f7f7f8;--panel:#fff;--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--button:#fff;--accent:#10a37f;--danger:#b42318}:root[data-theme="dark"]{--bg:#101315;--panel:#181d20;--ink:#edf2f4;--muted:#a8b3ba;--line:#354048;--button:#222a2f;--danger:#ff837c}*{box-sizing:border-box}html,body{height:100%;overflow:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:14px Inter,system-ui,sans-serif}.top{height:62px;background:var(--panel);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 24px}.top h1{margin:0;font-size:17px}.top span{display:block;color:var(--muted);font-size:12px;margin-top:3px}.top-actions{display:flex;gap:8px}.back,.button{border:1px solid var(--line);background:var(--button);border-radius:7px;padding:8px 11px;color:var(--ink);cursor:pointer;text-decoration:none;font-size:13px}.button.primary{background:var(--accent);border-color:var(--accent);color:#fff}.button.danger{color:var(--danger)}.layout{height:calc(100vh - 62px);max-width:none;margin:0;padding:18px 22px;display:grid;grid-template-columns:260px minmax(0,1fr);gap:18px;overflow:hidden}.sidebar,.editor{background:var(--panel);border:1px solid var(--line);border-radius:8px;min-height:0}.sidebar{padding:16px;overflow:auto}.field{display:block;font-weight:600;font-size:12px;margin:0 0 5px;color:var(--muted)}.filter{width:100%;border:1px solid var(--line);border-radius:6px;padding:9px;margin:0 0 12px;background:var(--button);color:var(--ink)}.summary{font-size:12px;color:var(--muted);line-height:1.6}.editor{padding:20px;display:grid;grid-template-rows:auto minmax(0,1fr) auto auto;gap:12px;overflow:hidden}.meta{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding-bottom:12px;margin:0}.meta b{font-size:15px}.source{font:12px ui-monospace,monospace;color:var(--muted);margin-top:4px}.counter{font-size:12px;color:var(--muted)}.report-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;min-height:0}.report-pane{display:flex;flex-direction:column;min-height:0}.report-pane textarea{flex:1;min-height:0;height:100%;resize:none}.notes-wrap .field{margin-bottom:5px}textarea{display:block;width:100%;padding:11px;border:1px solid var(--line);border-radius:6px;resize:vertical;font:13px ui-monospace,monospace;line-height:1.45;color:var(--ink);background:var(--button)}textarea.notes{min-height:64px;height:64px;max-height:92px}.actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0}.status{margin-left:auto;color:var(--muted);font-size:12px}.empty{padding:36px;text-align:center;color:var(--muted)}@media(max-width:900px){html,body{height:auto;overflow:auto}.layout{height:auto;min-height:calc(100vh - 62px);grid-template-columns:1fr;padding:12px}.sidebar{height:auto}.editor{display:block}.report-grid{grid-template-columns:1fr}.report-pane textarea{height:340px;min-height:340px;margin-bottom:14px}.notes-wrap{margin-top:8px}.actions{margin-top:14px}.top{padding:0 14px}.status{width:100%;margin-left:0}}
</style></head><body><header class="top"><div><h1>Revision SFT</h1><span>Dataset ampliado v2</span></div><div class="top-actions"><button class="button" id="themeToggle" type="button">Modo oscuro</button><a class="back" href="/">Volver a OPTIMUS</a></div></header><main class="layout"><aside class="sidebar"><label class="field" for="region">Region</label><select class="filter" id="region"></select><label class="field" for="modality">Modalidad</label><select class="filter" id="modality"></select><label class="field" for="origen">Origen</label><select class="filter" id="origen"><option value="all">Todos</option><option value="vuepacs">VuePACS</option><option value="general">Dataset general</option></select><label class="field" for="state">Estado</label><select class="filter" id="state"><option value="pending">Pendientes</option><option value="candidate">Asociacion por revisar</option><option value="approved">Aprobados</option><option value="rejected">Descartados</option><option value="all">Todos</option></select><div class="summary" id="summary"></div></aside><section class="editor" id="editor"><div class="empty">Cargando casos...</div></section></main><script>
const el=id=>document.getElementById(id);
function applyTheme(theme){
  document.documentElement.dataset.theme=theme;
  localStorage.setItem("optimus_sft_theme",theme);
  el("themeToggle").textContent=theme==="dark" ? "Modo claro" : "Modo oscuro";
}
const savedTheme=localStorage.getItem("optimus_sft_theme");
applyTheme(savedTheme==="dark" ? "dark" : "light");
el("themeToggle").addEventListener("click",()=>{
  applyTheme(document.documentElement.dataset.theme==="dark" ? "light" : "dark");
});
let cases=[],index=0;
function safeText(value){return value==null?'':String(value)}
function escapeHtml(value){return safeText(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function active(){return cases[index]}
function sourceText(item){const src=item.source||{};const lines=Array.isArray(src.lines)?src.lines.join('-'):'';return `${src.file||''} ${lines?`(lineas ${lines})`:''}`}
async function loadCases(reset=true){const params=new URLSearchParams({region:el('region').value||'all',modality:el('modality').value||'all',origen:el('origen').value||'all',status:el('state').value||'pending'});const response=await fetch('/sft_revision/cases?'+params);const data=await response.json();if(!response.ok){el('editor').innerHTML='<div class="empty">'+safeText(data.error||'No se pudo cargar la cola.')+'</div>';return}cases=data.cases||[];if(reset)index=0;el('summary').textContent=`${data.summary.pending} pendientes | ${data.summary.candidate||0} por asociar | ${data.summary.approved} aprobados | ${data.summary.rejected} descartados`;render()}
function render(){const item=active();if(!item){el('editor').innerHTML='<div class="empty">No hay casos para este filtro.</div>';return}const detail=[item.origen_cola,sourceText(item),item.modality,item.extraction_confidence,item.candidate_type].filter(Boolean).join(' | ');el('editor').innerHTML=`<div class="meta"><div><b>${escapeHtml(item.region)}</b><div class="source">${escapeHtml(detail)}</div></div><div class="counter">${index+1} de ${cases.length}</div></div><div class="report-grid"><div class="report-pane"><label class="field" for="raw">Dictado bruto anonimizado</label><textarea id="raw" placeholder="Pega el dictado original sin identificadores">${escapeHtml(item.raw_input)}</textarea></div><div class="report-pane"><label class="field" for="final">Informe final propuesto</label><textarea id="final">${escapeHtml(item.final_report)}</textarea></div></div><div class="notes-wrap"><label class="field" for="notes">Notas de revision</label><textarea class="notes" id="notes">${escapeHtml(item.review_notes)}</textarea></div><div class="actions"><button class="button" onclick="move(-1)">Anterior</button><button class="button" onclick="move(1)">Siguiente</button><button class="button" onclick="saveCurrent()">Guardar</button><button class="button primary" onclick="save('approved')">Aprobar</button><button class="button danger" onclick="save('rejected')">Descartar</button><span class="status" id="status"></span></div>`}
function move(delta){const next=index+delta;if(next>=0&&next<cases.length){index=next;render()}}
function saveCurrent(){const item=active();return save(item&&item.approval_status?item.approval_status:'pending')}
async function save(status){const item=active();const payload={raw_input:el('raw').value,final_report:el('final').value,review_notes:el('notes').value,approval_status:status};el('status').textContent='Guardando...';const response=await fetch('/sft_revision/cases/'+encodeURIComponent(item.review_case_id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok){el('status').textContent=data.error||'No se pudo guardar';return}item.raw_input=data.case.raw_input;item.final_report=data.case.final_report;item.review_notes=data.case.review_notes;item.approval_status=data.case.approval_status;item.sft_eligible=data.case.sft_eligible;el('status').textContent=status==='approved'?'Aprobado':'Guardado';if(status!==el('state').value&&el('state').value!=='all')setTimeout(()=>loadCases(true),250)}
el('region').addEventListener('change',()=>loadCases());el('modality').addEventListener('change',()=>loadCases());el('origen').addEventListener('change',()=>loadCases());el('state').addEventListener('change',()=>loadCases());(async()=>{const response=await fetch('/sft_revision/cases?region=all&modality=all&origen=all&status=all');const data=await response.json();const regions=data.regions||[];el('region').innerHTML='<option value="all">Todas las regiones</option>'+regions.map(region=>`<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`).join('');const modalities=data.modalities||[];el('modality').innerHTML='<option value="all">Todas las modalidades</option>'+modalities.map(modality=>`<option value="${escapeHtml(modality)}">${escapeHtml(modality)}</option>`).join('');await loadCases()})()
</script></body></html>"""

PAGINA_REVISION_ESTILO = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>OPTIMUS - Revisión de estilo</title>
<style>:root{--bg:#f7f7f8;--panel:#fff;--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#10a37f;--danger:#b42318}html[data-theme="dark"]{--bg:#111827;--panel:#182131;--ink:#e8edf6;--muted:#aab7ca;--line:#2c3a50;--accent:#16b895}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px Inter,system-ui,sans-serif}.top{height:62px;background:var(--panel);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 24px}.top h1{margin:0;font-size:17px}.top span{display:block;color:var(--muted);font-size:12px;margin-top:3px}.back,.button{border:1px solid var(--line);background:#fff;border-radius:7px;padding:8px 11px;color:var(--ink);cursor:pointer;text-decoration:none;font-size:13px}html[data-theme="dark"] .back,html[data-theme="dark"] .button,html[data-theme="dark"] .filter,html[data-theme="dark"] textarea{background:#1e293b;color:var(--ink)}.button.primary{background:var(--accent);border-color:var(--accent);color:#fff}.button.danger{color:var(--danger)}.layout{height:calc(100vh - 62px);padding:18px 22px;display:grid;grid-template-columns:260px minmax(0,1fr);gap:18px}.sidebar,.editor{background:var(--panel);border:1px solid var(--line);border-radius:8px;min-height:0}.sidebar{padding:16px}.field{display:block;font-weight:600;font-size:12px;margin:0 0 5px;color:var(--muted)}.filter,textarea{width:100%;border:1px solid var(--line);border-radius:6px;padding:10px;background:#fff;color:var(--ink)}.filter{margin:0 0 12px}.summary{font-size:12px;line-height:1.6;color:var(--muted)}.editor{padding:20px;display:grid;grid-template-rows:auto minmax(0,1fr) auto auto;gap:12px}.meta{border-bottom:1px solid var(--line);padding-bottom:12px}.meta b{font-size:15px}.source{font:12px ui-monospace,monospace;color:var(--muted);margin-top:4px}.report{min-height:0;display:flex;flex-direction:column}.report textarea{height:100%;resize:none;font:13px ui-monospace,monospace;line-height:1.45}.notes{height:72px;resize:vertical}.actions{display:flex;gap:8px;align-items:center}.status{margin-left:auto;color:var(--muted);font-size:12px}.empty{padding:36px;text-align:center;color:var(--muted)}@media(max-width:800px){.layout{height:auto;min-height:calc(100vh - 62px);grid-template-columns:1fr;padding:12px}.editor{min-height:620px}.top{padding:0 14px}}</style></head><body>
<header class="top"><div><h1>Revisión de estilo</h1><span>Los ejemplos aprobados podrán servir como referencia de redacción; no cambian reglas clínicas.</span></div><div><button class="button" id="themeToggle" type="button" onclick="toggleTheme()">Modo claro</button> <a class="back" href="/">Volver a OPTIMUS</a></div></header>
<main class="layout"><aside class="sidebar"><label class="field" for="region">Región</label><select class="filter" id="region"></select><label class="field" for="state">Estado</label><select class="filter" id="state"><option value="candidate">Por revisar</option><option value="approved">Aprobados para estilo</option><option value="rejected">Descartados</option><option value="all">Todos</option></select><div class="summary" id="summary"></div></aside><section class="editor" id="editor"><div class="empty">Cargando candidatos de estilo…</div></section></main>
<script>const el=id=>document.getElementById(id);function applyTheme(theme){document.documentElement.dataset.theme=theme;localStorage.setItem('fab_theme',theme);el('themeToggle').textContent=theme==='dark'?'Modo claro':'Modo oscuro'}function toggleTheme(){applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')}applyTheme(localStorage.getItem('fab_theme')||'dark');let cases=[],index=0;const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');function active(){return cases[index]}async function loadCases(reset=true){const q=new URLSearchParams({region:el('region').value||'all',status:el('state').value||'candidate'});const r=await fetch('/style_revision/cases?'+q);const d=await r.json();if(!r.ok){el('editor').innerHTML='<div class="empty">'+esc(d.error||'No se pudo cargar la cola.')+'</div>';return}cases=d.cases||[];if(reset)index=0;const s=d.summary||{};el('summary').textContent=`${s.candidate||0} por revisar | ${s.approved||0} aprobados para estilo | ${s.rejected||0} descartados`;render()}function render(){const item=active();if(!item){el('editor').innerHTML='<div class="empty">No hay ejemplos para este filtro.</div>';return}const src=item.source||{},lines=Array.isArray(src.lines)?src.lines.join('-'):'';el('editor').innerHTML=`<div class="meta"><b>${esc(item.region)}</b><div class="source">${esc(src.file||'')}${lines?' (líneas '+esc(lines)+')':''} · ${index+1} de ${cases.length}</div></div><div class="report"><label class="field" for="report">Informe histórico</label><textarea id="report">${esc(item.report)}</textarea></div><div><label class="field" for="notes">Notas de revisión</label><textarea class="notes" id="notes">${esc(item.review_notes||'')}</textarea></div><div class="actions"><button class="button" onclick="move(-1)">Anterior</button><button class="button" onclick="move(1)">Siguiente</button><button class="button" onclick="save(active().approval_status)">Guardar</button><button class="button primary" onclick="save('approved')">Aprobar estilo</button><button class="button danger" onclick="save('rejected')">Descartar</button><span class="status" id="status"></span></div>`}function move(delta){const next=index+delta;if(next>=0&&next<cases.length){index=next;render()}}async function save(status){const item=active(),payload={report:el('report').value,review_notes:el('notes').value,approval_status:status};el('status').textContent='Guardando…';const r=await fetch('/style_revision/cases/'+encodeURIComponent(item.style_candidate_id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok){el('status').textContent=d.error||'No se pudo guardar';return}item.report=d.case.report;item.review_notes=d.case.review_notes;item.approval_status=d.case.approval_status;item.style_eligible=d.case.style_eligible;el('status').textContent=status==='approved'?'Aprobado para estilo':'Guardado';if(status!==el('state').value&&el('state').value!=='all')setTimeout(()=>loadCases(true),200)}el('region').addEventListener('change',()=>loadCases());el('state').addEventListener('change',()=>loadCases());(async()=>{const r=await fetch('/style_revision/cases?region=all&status=all'),d=await r.json();el('region').innerHTML='<option value="all">Todas las regiones</option>'+(d.regions||[]).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');await loadCases()})()</script></body></html>"""

@app.route("/")
def home():
    return Response(PAGINA, mimetype="text/html")


def _leer_cola_archivo(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("review_case_id"):
            rows.append(row)
    return rows


def _origen_de_cola(path):
    return "vuepacs" if path == VUEPACS_REVIEW_QUEUE else "general"


def _leer_cola_revision_sft():
    rows = []
    for path in SFT_REVIEW_QUEUES:
        origen = _origen_de_cola(path)
        for row in _leer_cola_archivo(path):
            tagged = dict(row)
            tagged["origen_cola"] = origen
            rows.append(tagged)
    return rows


def _localizar_cola_de_caso(case_id):
    """Devuelve el archivo de cola donde vive un caso, o None si no esta en ninguno."""
    for path in SFT_REVIEW_QUEUES:
        if any(row.get("review_case_id") == case_id for row in _leer_cola_archivo(path)):
            return path
    return None


def _guardar_cola_revision_sft(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _resumen_cola_sft(rows):
    summary = {status: 0 for status in SFT_REVIEW_STATUSES}
    for row in rows:
        status = row.get("approval_status", "pending")
        if status in summary:
            summary[status] += 1
    return summary


@app.route("/sft_revision")
def route_sft_revision_page():
    return Response(PAGINA_REVISION_SFT, mimetype="text/html")


@app.route("/sft_revision/cases")
def route_sft_revision_cases():
    region = (request.args.get("region") or "all").strip()
    modality = (request.args.get("modality") or "all").strip()
    origen = (request.args.get("origen") or "all").strip()
    status = (request.args.get("status") or "pending").strip()
    rows = _leer_cola_revision_sft()
    filtered = [
        row for row in rows
        if (region == "all" or row.get("region") == region)
        and (modality == "all" or row.get("modality") == modality)
        and (origen == "all" or row.get("origen_cola") == origen)
        and (status == "all" or row.get("approval_status", "pending") == status)
    ]
    return jsonify({
        "cases": filtered,
        "regions": sorted({row.get("region") for row in rows if row.get("region")}),
        "modalities": sorted({row.get("modality") for row in rows if row.get("modality")}),
        "summary": _resumen_cola_sft(rows),
    })


@app.route("/sft_revision/cases/<case_id>", methods=["PUT"])
def route_sft_revision_case_update(case_id):
    data = request.get_json() or {}
    status = (data.get("approval_status") or "pending").strip().lower()
    if status not in SFT_REVIEW_STATUSES:
        return jsonify({"error": "Estado de revision no valido."}), 400

    raw_input = (data.get("raw_input") or "").strip()
    final_report = (data.get("final_report") or "").strip()
    review_notes = (data.get("review_notes") or "").strip()
    if status == "approved":
        if not raw_input or not final_report:
            return jsonify({"error": "Para aprobar se requieren dictado bruto e informe final."}), 400
        if SFT_REVIEW_PII.search(raw_input) or SFT_REVIEW_PII.search(final_report):
            return jsonify({"error": "El caso contiene un posible identificador. Anonimizalo antes de aprobar."}), 400

    queue_path = _localizar_cola_de_caso(case_id)
    if queue_path is None:
        return jsonify({"error": "Caso de revision no encontrado."}), 404

    rows = _leer_cola_archivo(queue_path)
    row = next((item for item in rows if item.get("review_case_id") == case_id), None)
    if row is None:
        return jsonify({"error": "Caso de revision no encontrado."}), 404
    row.update({
        "raw_input": raw_input,
        "final_report": final_report,
        "review_notes": review_notes,
        "approval_status": status,
        "sft_eligible": status == "approved",
    })
    _guardar_cola_revision_sft(queue_path, rows)
    return jsonify({"ok": True, "case": row, "summary": _resumen_cola_sft(_leer_cola_revision_sft())})


def _leer_cola_estilo():
    if not STYLE_REVIEW_QUEUE.exists():
        return []
    rows = []
    for line in STYLE_REVIEW_QUEUE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("style_candidate_id"):
            rows.append(row)
    return rows


def _resumen_cola_estilo(rows):
    summary = {status: 0 for status in STYLE_REVIEW_STATUSES}
    for row in rows:
        status = row.get("approval_status", "candidate")
        if status in summary:
            summary[status] += 1
    return summary


def _referencia_estilo_para_region(region_id):
    """Un único ejemplo de estilo aprobado para la región, o (None, None).

    La selección es determinista por región y por contenido
    (style_candidate_id, que es un hash estable del informe): nunca por
    fecha de aprobación, porque la aprobación masiva deja marcas de
    tiempo casi idénticas en cientos de filas y dejaría de ser un
    criterio significativo. El texto se recorta a
    STYLE_REFERENCE_CHAR_LIMIT caracteres para acotar el coste añadido
    en proveedores cloud.
    """
    aprobados = [
        row
        for row in _leer_cola_estilo()
        if row.get("region") == region_id
        and row.get("approval_status") == "approved"
        and (row.get("report") or "").strip()
    ]
    if not aprobados:
        return None, None
    elegido = min(aprobados, key=lambda row: row.get("style_candidate_id") or "")
    texto = elegido["report"].strip()
    if len(texto) > STYLE_REFERENCE_CHAR_LIMIT:
        texto = texto[:STYLE_REFERENCE_CHAR_LIMIT].rstrip() + "…"
    return elegido.get("style_candidate_id"), texto


@app.route("/style_revision")
def route_style_revision_page():
    return Response(PAGINA_REVISION_ESTILO, mimetype="text/html")


@app.route("/style_revision/cases")
def route_style_revision_cases():
    region = (request.args.get("region") or "all").strip()
    status = (request.args.get("status") or "candidate").strip()
    rows = _leer_cola_estilo()
    filtered = [
        row for row in rows
        if (region == "all" or row.get("region") == region)
        and (status == "all" or row.get("approval_status", "candidate") == status)
    ]
    return jsonify({
        "cases": filtered,
        "regions": sorted({row.get("region") for row in rows if row.get("region")}),
        "summary": _resumen_cola_estilo(rows),
    })


@app.route("/style_revision/cases/<case_id>", methods=["PUT"])
def route_style_revision_case_update(case_id):
    data = request.get_json() or {}
    status = (data.get("approval_status") or "candidate").strip().lower()
    if status not in STYLE_REVIEW_STATUSES:
        return jsonify({"error": "Estado de revisión no válido."}), 400
    report = (data.get("report") or "").strip()
    review_notes = (data.get("review_notes") or "").strip()
    if status == "approved":
        if not report:
            return jsonify({"error": "Para aprobar se necesita un informe."}), 400
        if SFT_REVIEW_PII.search(report):
            return jsonify({"error": "El ejemplo contiene un posible identificador. Anonimízalo antes de aprobar."}), 400

    rows = _leer_cola_estilo()
    row = next((item for item in rows if item.get("style_candidate_id") == case_id), None)
    if row is None:
        return jsonify({"error": "Ejemplo de estilo no encontrado."}), 404
    row.update({
        "report": report,
        "review_notes": review_notes,
        "approval_status": status,
        "style_eligible": status == "approved",
        "reviewed_at": datetime.now().isoformat(timespec="seconds"),
    })
    _guardar_cola_revision_sft(STYLE_REVIEW_QUEUE, rows)
    return jsonify({"ok": True, "case": row, "summary": _resumen_cola_estilo(rows)})


@app.route("/style_revision/approve_all", methods=["POST"])
def route_style_revision_approve_all():
    """Aprueba en bloque solo candidatos de estilo completos y sin alertas PII."""
    rows = _leer_cola_estilo()
    approved = 0
    skipped_empty = 0
    skipped_pii = 0
    now = datetime.now().isoformat(timespec="seconds")
    for row in rows:
        if row.get("approval_status", "candidate") != "candidate":
            continue
        report = (row.get("report") or "").strip()
        if not report:
            skipped_empty += 1
            continue
        if SFT_REVIEW_PII.search(report):
            skipped_pii += 1
            continue
        row.update({
            "approval_status": "approved",
            "style_eligible": True,
            "reviewed_at": now,
            "review_notes": (row.get("review_notes") or "").strip() or "Aprobación masiva solicitada por el radiólogo.",
        })
        approved += 1
    _guardar_cola_revision_sft(STYLE_REVIEW_QUEUE, rows)
    return jsonify({
        "ok": True,
        "approved": approved,
        "skipped_empty": skipped_empty,
        "skipped_possible_pii": skipped_pii,
        "summary": _resumen_cola_estilo(rows),
    })


@app.route("/regiones")
def route_regiones():
    regiones = []
    for region in list_regions():
        region_id = region["region_id"]
        regiones.append({
            "region_id": region_id,
            "enabled": region["enabled"],
            "region_name": _nombre_region(region_id),
        })
    return jsonify({"current_region": current_region, "regions": regiones})


def _estado_proveedor(proveedor=None):
    proveedor = (proveedor or DEFAULT_PROVIDER or "openai").strip().lower()
    if proveedor == "llama_cpp":
        estado = _llama_provider().health_check()
        return {
            "active_provider": proveedor,
            "provider_configured": _llama_provider().is_configured(),
            "provider_reachable": bool(estado.get("reachable")),
            "provider_model": _llama_provider().get_model_name(),
            "provider_error_code": estado.get("error_code"),
        }
    if proveedor == "mock":
        return {"active_provider": "mock", "provider_configured": True, "provider_reachable": True, "provider_model": "mock-radiology", "provider_error_code": None}
    _, env_key, env_model = _provider_env_names(proveedor)
    return {
        "active_provider": proveedor,
        "provider_configured": bool(env_key and os.environ.get(env_key)),
        "provider_reachable": None,
        "provider_model": _modelo_configurado(proveedor),
        "provider_error_code": None,
    }


@app.route("/health")
def route_health():
    estado = _estado_proveedor(request.args.get("provider") or DEFAULT_PROVIDER)
    degradado = estado["active_provider"] == "llama_cpp" and not estado["provider_reachable"]
    return jsonify({
        "status": "degraded" if degradado else "ok",
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "registered_regions": [region["region_id"] for region in list_regions() if region.get("enabled")],
        "region_count": len([region for region in list_regions() if region.get("enabled")]),
        "data_dir_writable": os.access(DATA_DIR, os.W_OK),
        "gold_storage_available": os.access(DATASET.parent, os.W_OK),
        **estado,
    })


@app.route("/detectar_region", methods=["POST"])
def route_detectar_region():
    data = request.get_json() or {}
    caso = (data.get("caso") or "").strip()
    if not caso:
        return jsonify({"error": "Caso vacío."}), 400
    return jsonify(detectar_region_desde_texto(caso))


@app.route("/region", methods=["POST"])
def route_region():
    data = request.get_json() or {}
    region_id = (data.get("region") or data.get("region_id") or "").strip()
    if not region_id:
        return jsonify({"ok": False, "error": "Region no indicada."}), 400
    try:
        activar_region(region_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"No se pudo activar la region {region_id}: {e}"}), 400
    return jsonify({
        "ok": True,
        "region": current_region,
        "region_name": REGION_NAME,
        "prompt_version": prompt_version_efectiva(),
        "validator_version": VALIDATOR_VERSION,
        "dataset": str(DATASET),
        "cases_dir": str(CASOS_DIR),
    })


def _provider_env_names(proveedor):
    proveedor = (proveedor or "openai").strip().lower()
    if proveedor in {"claude", "anthropic"}:
        proveedor = "anthropic"
    env_key = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "llama_cpp": "OPTIMUS_LLAMA_API_KEY",
        "mock": "",
    }.get(proveedor, "OPENAI_API_KEY")
    env_model = {
        "openai": "OPENAI_MODEL",
        "anthropic": "ANTHROPIC_MODEL",
        "deepseek": "DEEPSEEK_MODEL",
        "llama_cpp": "OPTIMUS_LLAMA_MODEL",
        "mock": "",
    }.get(proveedor, "OPENAI_MODEL")
    return proveedor, env_key, env_model


def listar_modelos_disponibles(proveedor, api_key):
    """Devuelve modelos visibles para esa API key/proyecto cuando el proveedor lo permite."""
    proveedor = (proveedor or "openai").strip().lower()
    if proveedor in {"claude", "anthropic"}:
        proveedor = "anthropic"

    if proveedor == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        modelos = [m.id for m in client.models.list().data]
        # La lista pertenece al proyecto asociado a la clave: no filtramos por
        # prefijos para que la interfaz refleje íntegramente lo que la API expone.
        return sorted(modelos)

    if proveedor == "deepseek":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        modelos = [m.id for m in client.models.list().data]
        preferidos = ("deepseek-chat", "deepseek-reasoner")
        texto = sorted(modelos)
        return [m for m in preferidos if m in texto] + [m for m in texto if m not in preferidos]

    if proveedor == "anthropic":
        # Anthropic no siempre expone listado de modelos en instalaciones antiguas del SDK.
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            if hasattr(client, "models") and hasattr(client.models, "list"):
                resp = client.models.list()
                data = getattr(resp, "data", resp)
                modelos = [getattr(m, "id", None) for m in data]
                modelos = [m for m in modelos if m]
                if modelos:
                    return sorted(modelos)
        except Exception:
            pass
        return ["claude-sonnet-4-5", "claude-opus-4-1", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]

    if proveedor == "llama_cpp":
        model = os.environ.get("OPTIMUS_LLAMA_MODEL", "")
        return [model] if model else []

    if proveedor == "mock":
        return ["mock-radiology"]

    return []



@app.route("/config")
def route_config():
    return jsonify({
        "region": current_region,
        "region_name": REGION_NAME,
        "prompt_base": PROMPT_BASE,
        "prompt_override": APP_CONFIG.get("prompt_override"),
        "prompt_draft": APP_CONFIG.get("prompt_draft"),
        "prompt_efectivo": SYSTEM_PROMPT,
        "prompt_version": prompt_version_efectiva(),
        "config_path": str(CONFIG_PATH),
    })


def _llm_chat_text(proveedor, api_key, modelo, system, user):
    proveedor = (proveedor or "openai").strip().lower()
    if proveedor in {"claude", "anthropic"}:
        proveedor = "anthropic"
    if proveedor == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        return _openai_compat_chat(client, modelo, system, user)
    if proveedor == "deepseek":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        return _openai_compat_chat(client, modelo, system, user)
    if proveedor == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=modelo,
            max_tokens=5000,
            temperature=0.2,
            system=system,
            messages=[{"role":"user", "content":user}],
        )
        return _texto_anthropic(resp)
    raise ValueError(f"Proveedor no reconocido: {proveedor}")


def _extraer_json(texto):
    texto = (texto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?", "", texto).strip()
        texto = re.sub(r"```$", "", texto).strip()
    m = re.search(r"\{.*\}", texto, re.S)
    if m:
        texto = m.group(0)
    return json.loads(texto)


@app.route("/admin_chat", methods=["POST"])
def route_admin_chat():
    data = request.get_json() or {}
    mensaje = (data.get("mensaje") or "").strip()
    proveedor, env_key, env_model = _provider_env_names(data.get("provider") or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER or "openai")
    key = (data.get("key") or "").strip() or os.environ.get(env_key, "")
    modelo = (data.get("model") or _modelo_configurado(proveedor) or DEFAULT_MODELS.get(proveedor) or DEFAULT_MODEL).strip()
    if not mensaje:
        return jsonify({"error":"Mensaje vacío."})
    if not key:
        return jsonify({"error":f"No hay API key para {proveedor}. Escríbela o define {env_key}."})

    system = """Eres un editor experto de prompts para informes radiológicos. Tu tarea es proponer cambios seguros al prompt del sistema de una fábrica local de informes TC abdomen-pelvis. Debes conservar el criterio clínico, la trazabilidad y el estilo sobrio. No elimines reglas duras salvo que el usuario lo pida explícitamente. Devuelve SOLO JSON válido con estas claves: respuesta, nuevo_system_prompt, resumen_cambio. Si la petición no requiere cambiar prompt, deja nuevo_system_prompt como cadena vacía."""
    user = f"""PROMPT ACTUAL:\n{SYSTEM_PROMPT}\n\nPETICIÓN DEL USUARIO:\n{mensaje}\n\nDevuelve JSON válido."""
    raw = _llm_chat_text(proveedor, key, modelo, system, user)
    try:
        obj = _extraer_json(raw)
    except Exception:
        return jsonify({"respuesta": raw, "tipo":"texto"})
    nuevo = (obj.get("nuevo_system_prompt") or "").strip()
    respuesta = obj.get("respuesta") or obj.get("resumen_cambio") or "Propuesta preparada."
    if nuevo:
        # calcular el diff frente al prompt actual, para que veas exactamente qué cambia
        diff = diff_prompts(SYSTEM_PROMPT, nuevo)
        ULTIMA_PROPUESTA["prompt"] = nuevo
        ULTIMA_PROPUESTA["respuesta"] = respuesta
        ULTIMA_PROPUESTA["prompt_anterior"] = SYSTEM_PROMPT
        return jsonify({
            "respuesta": respuesta + "\n\nResumen: " + (obj.get("resumen_cambio") or ""),
            "tipo":"prompt",
            "diff": diff,
        })
    return jsonify({"respuesta": respuesta, "tipo":"texto"})


@app.route("/aplicar_prompt", methods=["POST"])
def route_aplicar_prompt():
    global SYSTEM_PROMPT, APP_CONFIG
    data = request.get_json(silent=True) or {}
    nuevo = ULTIMA_PROPUESTA.get("prompt") or APP_CONFIG.get("prompt_draft")
    anterior = SYSTEM_PROMPT
    if not nuevo:
        return jsonify({"ok":False, "error":"No hay una propuesta o borrador de prompt pendiente."})
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_origen = prompt_version_efectiva()
    nueva_version = _siguiente_override_version()
    diff = diff_prompts(anterior, nuevo)
    (HISTORIAL_DIR / f"prompt_{version_origen.replace('.', '_')}_{ts}.txt").write_text(anterior, encoding="utf-8")
    APP_CONFIG["prompt_override"] = nuevo
    APP_CONFIG["prompt_override_version"] = nueva_version
    APP_CONFIG.setdefault("notas", []).append({"ts": datetime.now().isoformat(timespec="seconds"), "resumen": ULTIMA_PROPUESTA.get("respuesta")})
    APP_CONFIG["version"] = int(APP_CONFIG.get("version", 1)) + 1
    _registrar_evento_prompt("aplicar_override", diff, version_origen, nueva_version, data.get("motivo") or ULTIMA_PROPUESTA.get("respuesta") or "")
    guardar_config(APP_CONFIG)
    SYSTEM_PROMPT = prompt_efectivo()
    ULTIMA_PROPUESTA["prompt"] = None
    return jsonify({"ok":True, "prompt_version":prompt_version_efectiva(), "diff":diff,
        "mensaje":f"Override aplicado ({prompt_version_efectiva()}). Copia de seguridad guardada en historial_prompts/."})


@app.route("/guardar_prompt_borrador", methods=["POST"])
def route_guardar_prompt_borrador():
    data = request.get_json(silent=True) or {}
    nuevo = data.get("prompt") or ULTIMA_PROPUESTA.get("prompt")
    if not nuevo:
        return jsonify({"ok":False, "error":"No hay prompt para guardar como borrador."}), 400
    diff = diff_prompts(SYSTEM_PROMPT, nuevo)
    draft_version = f"{PROMPT_VERSION}+draft.{len([e for e in APP_CONFIG.get('prompt_events', []) if e.get('accion') == 'guardar_borrador']) + 1}"
    APP_CONFIG["prompt_draft"] = nuevo
    APP_CONFIG["prompt_draft_version"] = draft_version
    _registrar_evento_prompt("guardar_borrador", diff, prompt_version_efectiva(), draft_version, data.get("motivo") or ULTIMA_PROPUESTA.get("respuesta") or "")
    guardar_config(APP_CONFIG)
    return jsonify({"ok":True, "prompt_version":prompt_version_efectiva(), "draft_version":draft_version, "diff":diff,
                    "mensaje":"Borrador guardado. El prompt efectivo no cambia hasta aplicar override."})


@app.route("/restaurar_prompt_base", methods=["POST"])
def route_restaurar_prompt_base():
    global SYSTEM_PROMPT, APP_CONFIG
    if not (APP_CONFIG.get("prompt_override") or "").strip():
        return jsonify({"ok":True, "prompt_version":PROMPT_VERSION, "mensaje":"El prompt base ya era el efectivo."})
    anterior = SYSTEM_PROMPT
    version_origen = prompt_version_efectiva()
    diff = diff_prompts(anterior, PROMPT_BASE)
    APP_CONFIG["prompt_override"] = None
    APP_CONFIG["prompt_override_version"] = None
    APP_CONFIG["version"] = int(APP_CONFIG.get("version", 1)) + 1
    _registrar_evento_prompt("restaurar_base", diff, version_origen, PROMPT_VERSION, "Restaurar prompt base versionado")
    guardar_config(APP_CONFIG)
    SYSTEM_PROMPT = prompt_efectivo()
    return jsonify({"ok":True, "prompt_version":prompt_version_efectiva(), "diff":diff,
                    "mensaje":"Prompt base restaurado como prompt efectivo."})


@app.route("/deshacer_prompt", methods=["POST"])
def route_deshacer_prompt():
    """Compatibilidad: deshacer restaura el prompt base versionado."""
    return route_restaurar_prompt_base()


# ----------------------------------------------------------------------
# BANDEJA DE REGLAS CANDIDATAS (propone, tú apruebas)
# ----------------------------------------------------------------------
def _leer_candidatas():
    filas = []
    if REGLAS_CANDIDATAS.exists():
        for linea in REGLAS_CANDIDATAS.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                filas.append(json.loads(linea))
            except Exception:
                continue
    return filas


def _guardar_candidatas(filas):
    REGLAS_CANDIDATAS.write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in filas) + ("\n" if filas else ""),
        encoding="utf-8")


@app.route("/candidatas")
def route_candidatas():
    """Devuelve las reglas candidatas pendientes, las de tipo 'regla' primero."""
    filas = [f for f in _leer_candidatas() if f.get("estado") == "pendiente"]
    orden = {"regla": 0, "puntual": 1}
    filas.sort(key=lambda f: (orden.get(f.get("tipo"), 2), f.get("ts","")), reverse=False)
    # los pendientes más útiles (tipo regla) arriba, y dentro, recientes primero
    filas.sort(key=lambda f: (orden.get(f.get("tipo"), 2), ""))
    return jsonify({"candidatas": filas, "total": len(filas)})


@app.route("/candidata_aceptar", methods=["POST"])
def route_candidata_aceptar():
    """Acepta una candidata: la prepara como propuesta de cambio de prompt (con diff),
       igual que si la hubieras pedido por el chat de sistema. No la aplica sola."""
    data = request.get_json() or {}
    ts = data.get("ts")
    filas = _leer_candidatas()
    fila = next((f for f in filas if f.get("ts") == ts), None)
    if not fila:
        return jsonify({"ok":False, "error":"Candidata no encontrada."})
    regla = fila.get("regla") or ""
    if not regla:
        return jsonify({"ok":False, "error":"Esta candidata no tiene una regla formulada (era puntual)."})
    # preparar propuesta: añadir la regla al prompt actual, mostrando diff
    nuevo = SYSTEM_PROMPT.rstrip() + f"\n- {regla}"
    diff = diff_prompts(SYSTEM_PROMPT, nuevo)
    ULTIMA_PROPUESTA["prompt"] = nuevo
    ULTIMA_PROPUESTA["respuesta"] = f"Añadir regla desde tus correcciones: {regla}"
    ULTIMA_PROPUESTA["prompt_anterior"] = SYSTEM_PROMPT
    # marcar la candidata como aceptada
    fila["estado"] = "aceptada"
    _guardar_candidatas(filas)
    return jsonify({"ok":True, "diff":diff,
        "mensaje":"Propuesta preparada en el chat de sistema. Revisa el diff y pulsa 'Aplicar cambio' para confirmarla."})


@app.route("/candidata_descartar", methods=["POST"])
def route_candidata_descartar():
    data = request.get_json() or {}
    ts = data.get("ts")
    filas = _leer_candidatas()
    fila = next((f for f in filas if f.get("ts") == ts), None)
    if not fila:
        return jsonify({"ok":False, "error":"Candidata no encontrada."})
    fila["estado"] = "descartada"
    _guardar_candidatas(filas)
    return jsonify({"ok":True})


# ----------------------------------------------------------------------
# IMPORTADOR DE CASOS DESDE TXT (puente hospital -> fábrica)
# ----------------------------------------------------------------------
# Formato de captura: cada caso entre marcadores claros. En el hospital
# pegas tu dictado bruto y el informe generado por ChatGPT/Claude entre
# estas etiquetas, un caso tras otro. En casa, "Importar" los mete todos.
PLANTILLA_CAPTURA = """### CASO ###
[REGION]: abdomen
[BRUTO]:
(tu dictado bruto, sin corregir)
[INFORME]:
(el informe final: datos clínicos, hallazgos, impresión, interpretación global y análisis de mejora)
[MEJORAS]:
(opcional: qué corregiste — terminología, reordenación, ortografía, redundancias…)
[NOTAS]:
(opcional: hallazgo principal, dificultad del caso, lo que quieras marcar)
### FIN ###
"""


TORAX_STUDY_TYPES = {"tc_torax", "angio_tc_tep", "cribado_pulmonar", "torax_abdomen_pelvis"}
TORAX_CONTEXTS = {"general", "oncologico", "infeccioso", "trauma", "postquirurgico"}
TORAX_PROTOCOLS = {"sin_contraste", "con_contraste", "angiografico_pulmonar", "baja_dosis", "tap"}


def _identificador(texto):
    normalizado = unicodedata.normalize("NFD", (texto or "").strip().lower())
    normalizado = "".join(c for c in normalizado if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s-]+", "_", normalizado)


REGION_DETECTION_SIGNALS = {
    "abdomen": {"abdomen": 3, "higado": 2, "vesicula": 2, "pancreas": 2, "bazo": 2, "rinon": 2, "renal": 1},
    "lumbar": {"lumbar": 3, "lumbosacra": 3, "l4 l5": 3, "l5 s1": 3, "cono medular": 3, "cauda equina": 3},
    "cervical": {"cervical": 3, "c3 c4": 3, "c4 c5": 3, "c5 c6": 3, "c6 c7": 3, "odontoides": 3},
    "rodilla": {"rodilla": 3, "menisco": 2, "ligamento cruzado": 2, "patelofemoral": 2, "rotula": 2, "tibiofemoral": 2},
    "mano_muneca": {"muneca": 3, "mano": 3, "carpo": 2, "escafoides": 2, "radio distal": 2, "metacarpiano": 2},
    "codo": {"codo": 3, "epicondilo": 2, "troclea": 2, "olecranon": 2, "cubital": 2, "radial": 1},
    "tobillo_pie": {"tobillo": 3, "antepie": 3, "retropie": 3, "pie": 3, "talocrural": 2, "aquiles": 2, "fascia plantar": 2, "metatarsiano": 2},
    "torax": {"torax": 3, "pulmon": 2, "pleural": 2, "mediastino": 2, "tep": 3, "coronario": 1},
}


def detectar_region_desde_texto(texto):
    """Clasifica el dictado con señales anatómicas explícitas, sin usar un LLM."""
    fuente = " " + re.sub(r"[^a-z0-9]+", " ", _identificador(texto)) + " "
    puntuaciones = {}
    for region_id, senales in REGION_DETECTION_SIGNALS.items():
        puntuaciones[region_id] = sum(peso for senal, peso in senales.items() if f" {senal} " in fuente)
    candidatas = sorted(
        ({"region": region, "score": score} for region, score in puntuaciones.items() if score),
        key=lambda item: (-item["score"], item["region"]),
    )
    if not candidatas:
        return {"confidence": "uncertain", "region": None, "candidates": []}
    principal = candidatas[0]
    segunda_puntuacion = candidatas[1]["score"] if len(candidatas) > 1 else 0
    confianza = "high" if principal["score"] >= 3 and principal["score"] > segunda_puntuacion else "uncertain"
    return {"confidence": confianza, "region": principal["region"], "candidates": candidatas[:3]}


def _metadatos_torax(data=None, texto_fuente=""):
    data = data or {}
    fuente = _identificador(" ".join([texto_fuente, str(data.get("study_type") or ""), str(data.get("protocol") or ""), str(data.get("clinical_context") or "")]))
    study_type = _identificador(data.get("study_type"))
    if study_type and study_type not in TORAX_STUDY_TYPES:
        pass
    elif study_type not in TORAX_STUDY_TYPES:
        if fuente == "tap" or any(alias in fuente for alias in ("torax_abdomen_pelvis", "_tap_", "tap_", "tc_tap")):
            study_type = "torax_abdomen_pelvis"
        elif any(alias in fuente for alias in ("cribado", "screening", "baja_dosis")):
            study_type = "cribado_pulmonar"
        elif fuente == "tep" or any(alias in fuente for alias in ("angiotc", "angio_tc", "_tep", "tep_", "tep", "angio_pulmonar")):
            study_type = "angio_tc_tep"
        else:
            study_type = "tc_torax"
    context = _identificador(data.get("clinical_context"))
    if context and context not in TORAX_CONTEXTS:
        pass
    elif context not in TORAX_CONTEXTS:
        context = next((valor for valor in TORAX_CONTEXTS if valor != "general" and valor in fuente), "general")
    protocol = _identificador(data.get("protocol"))
    if protocol and protocol not in TORAX_PROTOCOLS:
        pass
    elif protocol not in TORAX_PROTOCOLS:
        protocol = {"angio_tc_tep": "angiografico_pulmonar", "cribado_pulmonar": "baja_dosis", "torax_abdomen_pelvis": "tap"}.get(study_type, "sin_contraste")
    comparison = data.get("comparison_available", False)
    if isinstance(comparison, str):
        comparison = _identificador(comparison) in {"true", "si", "yes", "1"}
    return {
        "study_type": study_type,
        "clinical_context": context,
        "protocol": protocol,
        "contrast": data.get("contrast") or ("con_contraste" if protocol in {"angiografico_pulmonar", "tap", "con_contraste"} else "sin_contraste"),
        "comparison_available": bool(comparison),
        "anatomical_scope": data.get("anatomical_scope") or ("torax_abdomen_pelvis" if study_type == "torax_abdomen_pelvis" else "torax"),
    }


def _parsear_casos_txt(texto):
    """Trocea el txt de captura en casos. Tolerante a variaciones de espaciado.
       Devuelve lista de dicts: {region, bruto, informe, mejoras, notas}."""
    casos = []
    bloques = re.split(r"###\s*CASO\s*###", texto, flags=re.I)
    for bloque in bloques:
        if not bloque.strip():
            continue
        bloque = re.split(r"###\s*FIN\s*###", bloque, flags=re.I)[0]
        region = None
        region_declarada = None
        mreg = re.search(r"\[REGION\]\s*:\s*(.+)", bloque, flags=re.I)
        if mreg:
            region_declarada = mreg.group(1).strip().splitlines()[0].strip() or None
            region = _normalizar_region_importada(region_declarada)
        # extraer campos por sus etiquetas; cada uno va hasta la siguiente etiqueta o el fin
        etiquetas = ["BRUTO", "INFORME", "MEJORAS", "NOTAS", "MODALIDAD", "STUDY_TYPE", "CLINICAL_CONTEXT", "PROTOCOL", "CONTRAST", "COMPARISON_AVAILABLE"]
        def campo(nombre):
            siguientes = [etiqueta for etiqueta in etiquetas if etiqueta != nombre]
            limite = "|".join(r"\[" + s + r"\]\s*:" for s in siguientes) + r"|\Z"
            pat = r"\[" + nombre + r"\]\s*:\s*(.*?)(?=" + limite + r")"
            m = re.search(pat, bloque, flags=re.I|re.S)
            return (m.group(1).strip() if m else "")
        bruto = campo("BRUTO")
        informe = campo("INFORME")
        mejoras = campo("MEJORAS")
        notas = campo("NOTAS")
        modalidad = campo("MODALIDAD")
        # limpiar placeholders
        for ph in ["(tu dictado bruto, sin corregir)","(pega aquí tu dictado bruto)",
                   "(el informe final: datos clínicos, hallazgos, impresión, interpretación global y análisis de mejora)",
                   "(pega aquí el informe generado en el hospital)",
                   "(opcional: qué corregiste — terminología, reordenación, ortografía, redundancias…)",
                   "(opcional: hallazgo principal, dificultad del caso, lo que quieras marcar)"]:
            bruto=bruto.replace(ph,"").strip(); informe=informe.replace(ph,"").strip()
            mejoras=mejoras.replace(ph,"").strip(); notas=notas.replace(ph,"").strip()
        if bruto or informe:
            casos.append({"region":region, "region_declarada":region_declarada, "bruto":bruto, "informe":informe,
                          "mejoras":mejoras, "notas":notas, "modalidad":modalidad or None,
                          "study_type":campo("STUDY_TYPE"), "clinical_context":campo("CLINICAL_CONTEXT"),
                          "protocol":campo("PROTOCOL"), "contrast":campo("CONTRAST"),
                          "comparison_available":campo("COMPARISON_AVAILABLE")})
    return casos


def _normalizar_region_importada(region):
    """Normaliza solo los alias de importacion declarados por el registro."""
    if not region:
        return None
    normalizada = _identificador(region)
    return {
        "mano_muneca": "mano_muneca",
        "elbow": "codo",
        "tobillo_pie": "tobillo_pie",
        "pie_tobillo": "tobillo_pie",
        "torax": "torax",
        "tc_torax": "torax",
        "tac_torax": "torax",
        "angiotc_tep": "torax",
        "angio_tc_pulmonar": "torax",
        "tep": "torax",
        "screening_pulmonar": "torax",
        "cribado": "torax",
        "tap": "torax",
        "torax_abdomen_pelvis": "torax",
    }.get(normalizada, normalizada)


def _hay_bloqueos_criticos(flags):
    return any(bool(f.get("bloquea_gold", False)) for f in (flags or []))


def _calcular_gold_standard(registro):
    return bool(
        registro.get("validacion_humana")
        and (registro.get("region") or current_region) == current_region
        and registro.get("case_status") == "validated"
        and (registro.get("input") or "").strip()
        and (registro.get("informe_final") or "").strip()
        and not _hay_bloqueos_criticos(registro.get("flags"))
        and registro.get("dataset_schema_version")
    )


def _persistir_caso(caso, informe_ia, informe_final, correccion="", region=None,
                    origen="app_local", proveedor="", modelo="", explicacion="",
                    modalidad=None, validacion_humana=False, prompt_version=None,
                    validator_version=None, dataset_schema_version=None,
                    fecha_validacion="", validated_by="", case_status=None, study_metadata=None,
                    generation_metadata=None):
    """Guarda un caso en disco (.md + .json) y en el dataset. Reutilizable por
       el guardado normal y por el importador. Devuelve (ts, hubo_correccion)."""
    caso = (caso or "").strip()
    if not caso:
        raise ValueError("No se puede guardar un caso sin input bruto.")
    es_borrador_historico_incompleto = case_status == "imported_incomplete"
    if not (informe_final or "").strip() and not es_borrador_historico_incompleto:
        raise ValueError("No se puede guardar un caso sin informe final.")
    if _tiene_metainfo_visible(informe_final):
        raise ValueError("El informe final contiene TAGS/DATASET_ENTRY o análisis interno visible. Revísalo antes de guardar.")

    case_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if (CASOS_DIR / f"caso_{case_id}.json").exists():
        sufijo = 1
        while (CASOS_DIR / f"caso_{case_id}_{sufijo}.json").exists():
            sufijo += 1
        case_id = f"{case_id}_{sufijo}"
    timestamp = datetime.now().isoformat(timespec="seconds")
    region_id = region or current_region
    metadata_torax = _metadatos_torax(study_metadata, caso) if region_id == "torax" else None
    flags = validar(informe_final, metadata_torax) if (informe_final or "").strip() else []
    tiene_correccion = (informe_ia.strip() != informe_final.strip()) or bool(correccion)
    estados_validos = {"draft", "generated", "corrected", "validated", "rejected", "imported_pending", "imported_incomplete"}
    if case_status not in estados_validos:
        if origen == "importador_hospital":
            case_status = "imported_pending"
        elif validacion_humana:
            case_status = "validated"
        elif tiene_correccion:
            case_status = "corrected"
        else:
            case_status = "generated"
    region_name = _nombre_region(region_id)
    registro = {
        "case_id": case_id,
        "timestamp": timestamp,
        "dataset_schema_version": dataset_schema_version or DATASET_SCHEMA_VERSION,
        "region": region_id,
        "region_name": region_name,
        "origen": origen or "app_local",
        "modalidad": modalidad,
        "input": caso,
        "informe_ia": informe_ia or "",
        "correccion_radiologo": correccion or "",
        "informe_final": informe_final or "",
        "explicacion": explicacion or "",
        "proveedor": proveedor or "",
        "modelo": modelo or "",
        "prompt_version": prompt_version or prompt_version_efectiva(),
        "validator_version": validator_version or VALIDATOR_VERSION,
        "validacion_humana": bool(validacion_humana),
        "fecha_validacion": fecha_validacion or "",
        "validated_by": validated_by or "",
        "tiene_correccion": bool(tiene_correccion),
        "case_status": case_status,
        "flags": flags,
    }
    if generation_metadata:
        permitidos = {"provider", "model", "base_url", "request_timestamp", "response_timestamp", "latency_ms", "status", "token_usage", "error_code", "style_candidate_id"}
        registro["generation_metadata"] = {k: v for k, v in generation_metadata.items() if k in permitidos}
    if metadata_torax:
        registro.update(metadata_torax)
        registro["validation_status"] = case_status
        registro["gold_status"] = False
    registro["gold_standard"] = _calcular_gold_standard(registro)
    if metadata_torax:
        registro["gold_status"] = registro["gold_standard"]
    md = [f"# Caso {case_id}  ·  región: {registro['region']}  ·  origen: {registro['origen']}\n",
          "## Input bruto", caso, ""]
    if es_borrador_historico_incompleto:
        md += [
            "## Estado",
            "Borrador histórico incompleto: falta la impresión diagnóstica final. "
            "No es Gold Standard ni ejemplo SFT.",
            "",
        ]
        if informe_ia:
            md += ["## Contenido parcial disponible", informe_ia, ""]
    elif tiene_correccion:
        md += ["## Informe IA (original)", informe_ia, "",
               "## Corrección", correccion or "(edición directa sin nota)", ""]
        if explicacion:
            md += ["## Explicación", explicacion, ""]
        md += [
               "## Informe final", informe_final, ""]
    else:
        md += ["## Informe (aceptado sin cambios)", informe_final, ""]
    (CASOS_DIR / f"caso_{case_id}.md").write_text("\n".join(md), encoding="utf-8")
    (CASOS_DIR / f"caso_{case_id}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(DATASET, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return case_id, tiene_correccion


@app.route("/plantilla_captura")
def route_plantilla_captura():
    """Devuelve la plantilla que el usuario copia para rellenar en el hospital."""
    return Response(PLANTILLA_CAPTURA, mimetype="text/plain")


@app.route("/importar", methods=["POST"])
def route_importar():
    """Recibe el texto del txt de captura del hospital y guarda todos los casos."""
    data = request.get_json() or {}
    texto = data.get("texto") or ""
    if not texto.strip():
        return jsonify({"ok":False, "error":"No hay texto que importar."})
    casos = _parsear_casos_txt(texto)
    if not casos:
        return jsonify({"ok":False, "error":"No se reconoció ningún caso. ¿Usaste los marcadores ### CASO ### / ### FIN ###?"})
    resultados = []
    for c in casos:
        region_id = c.get("region")
        if not region_id:
            resultados.append({"region":"", "estado":"error",
                               "aviso":"Region ausente. Declara [REGION]: abdomen, lumbar, cervical, rodilla, mano_muneca, codo o tobillo_pie."})
            continue
        regiones_habilitadas = {r["region_id"] for r in list_regions() if r.get("enabled")}
        if region_id not in regiones_habilitadas:
            resultados.append({"region":region_id, "estado":"error",
                               "aviso":f"Region no registrada o no habilitada: {region_id}."})
            continue
        bruto, informe = c["bruto"], c["informe"]
        if not informe:
            resultados.append({"region":c["region"], "estado":"sin_informe",
                               "aviso":"Este caso solo tiene dictado bruto; genéralo en la fábrica."})
            continue
        # combinar mejoras + notas como la nota de corrección del caso
        nota_partes = []
        if c.get("mejoras"): nota_partes.append("Mejoras: " + c["mejoras"])
        if c.get("notas"): nota_partes.append("Notas: " + c["notas"])
        correccion = "\n".join(nota_partes)
        metadatos_torax = _metadatos_torax(c, " ".join(filter(None, [c.get("region_declarada"), bruto, informe]))) if region_id == "torax" else None
        region_anterior = current_region
        try:
            activar_region(region_id)
            case_id, _ = _persistir_caso(bruto, informe, informe, correccion=correccion,
                                         region=region_id, origen="importador_hospital",
                                         modalidad=c.get("modalidad"),
                                         study_metadata=metadatos_torax,
                                         case_status="imported_pending")
        except ValueError as e:
            resultados.append({"region":c["region"], "estado":"error", "aviso":str(e)})
            continue
        finally:
            if current_region != region_anterior:
                activar_region(region_anterior)
        validador_anterior = current_region
        activar_region(region_id)
        nflags = len(validar(informe, metadatos_torax))
        if current_region != validador_anterior:
            activar_region(validador_anterior)
        resultados.append({"region":c["region"], "estado":"importado", "ts":case_id, "case_id":case_id, "avisos":nflags})
    importados = sum(1 for r in resultados if r["estado"]=="importado")
    return jsonify({"ok":True, "importados":importados, "total":len(casos), "resultados":resultados})


@app.route("/modelos", methods=["POST"])
def route_modelos():
    data = request.get_json() or {}
    proveedor, env_key, env_model = _provider_env_names(data.get("provider") or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER or "openai")
    key = (data.get("key") or "").strip() or os.environ.get(env_key, "")
    if not key and proveedor not in {"llama_cpp", "mock"}:
        return jsonify({"error": f"No hay API key para {proveedor}. Escríbela en la configuración o define {env_key}."})
    try:
        modelos = listar_modelos_disponibles(proveedor, key)
    except Exception as e:
        return jsonify({"error": f"No se pudieron consultar modelos para {proveedor}: {e}"})
    configurado = _modelo_configurado(proveedor)
    # Una clave puede pertenecer a un proyecto con acceso distinto al modelo histórico
    # configurado. En ese caso elegimos uno de los modelos que la API confirma disponibles.
    preferido = configurado if configurado in modelos else (modelos[0] if modelos else configurado or DEFAULT_MODELS.get(proveedor) or DEFAULT_MODEL)
    return jsonify({"provider": proveedor, "models": modelos, "preferido": preferido})

@app.route("/generar", methods=["POST"])
def route_generar():
    data = request.get_json()
    caso = (data.get("caso") or "").strip()
    proveedor, env_key, env_model = _provider_env_names(data.get("provider") or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER or "openai")
    key = (data.get("key") or "").strip() or os.environ.get(env_key, "")
    modelo = (data.get("model") or _modelo_configurado(proveedor) or DEFAULT_MODELS.get(proveedor) or DEFAULT_MODEL).strip()
    if not key and proveedor not in {"llama_cpp", "mock"}:
        return jsonify({"error":f"No hay API key para {proveedor}. Escríbela en la configuración o define {env_key}."})
    if not caso:
        return jsonify({"error":"Caso vacío."})
    metadata_torax = _metadatos_torax(data, caso) if current_region == "torax" else None
    caso_para_modelo = caso
    if metadata_torax:
        caso_para_modelo = caso + "\n\n[METADATOS TORAX INTERNOS]\n" + json.dumps(metadata_torax, ensure_ascii=False)
    # Capa efimera de referencia de estilo: nunca toca SYSTEM_PROMPT ni
    # prompt_override, solo antepone un ejemplo ya aprobado al texto del
    # caso de ESTA peticion. Apagada por defecto; el radiologo la activa
    # caso a caso desde la casilla de la barra lateral.
    style_candidate_id = None
    if data.get("use_style_reference"):
        style_candidate_id, ejemplo_estilo = _referencia_estilo_para_region(current_region)
        if ejemplo_estilo:
            caso_para_modelo = STYLE_REFERENCE_PREFIX + ejemplo_estilo + STYLE_REFERENCE_SUFFIX + caso_para_modelo
    try:
        informe = generar_informe(caso_para_modelo, key, modelo, proveedor)
    except Exception as e:
        msg = str(e)
        if "model_not_found" in msg or "does not have access to model" in msg:
            msg += "\n\nEse proyecto/API key no tiene acceso al modelo elegido. Pulsa 'Detectar modelos disponibles' y selecciona uno de la lista."
        return jsonify({"error":msg})
    if not str(informe or "").strip():
        return jsonify({
            "error": "El modelo terminó sin devolver texto de informe. No se ha creado ni guardado ningún informe vacío.",
            "generation_metadata": {"provider": proveedor, "model": modelo, "status": "empty_response"},
        }), 502
    informe = normalizar_formato_pacs(
        informe,
        eliminar_analisis_calidad=current_region == "cervical",
    )
    if not informe.strip():
        return jsonify({
            "error": "El modelo devolvió una respuesta sin texto útil tras normalizarla. No se ha creado ni guardado ningún informe vacío.",
            "generation_metadata": {"provider": proveedor, "model": modelo, "status": "empty_normalized_response"},
        }), 502
    generation_metadata = dict(LAST_GENERATION_METADATA)
    if style_candidate_id:
        generation_metadata["style_candidate_id"] = style_candidate_id
    return jsonify({"informe":informe, "flags":validar(informe, metadata_torax), "provider":proveedor, "model":modelo, "study_metadata":metadata_torax, "generation_metadata":generation_metadata})

@app.route("/validar", methods=["POST"])
def route_validar():
    data = request.get_json() or {}
    informe = data.get("informe") or ""
    metadata_torax = _metadatos_torax(data, "") if current_region == "torax" else None
    return jsonify({"flags":validar(informe, metadata_torax)})

@app.route("/guardar", methods=["POST"])
def route_guardar():
    data = request.get_json()
    caso = (data.get("caso","") or "").strip()
    informe_ia = data.get("informe_ia","")      # lo que generó la IA, sin tocar
    informe_final = data.get("informe_final","")  # lo que dejaste tú tras editar
    correccion = data.get("correccion","").strip()  # tu nota: qué cambiaste y por qué
    proveedor, env_key, env_model = _provider_env_names(
        data.get("provider") or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER or "openai")
    modelo = (data.get("model") or _modelo_configurado(proveedor) or DEFAULT_MODELS.get(proveedor) or DEFAULT_MODEL).strip()
    explicacion = (data.get("explicacion") or "").strip()
    modalidad = (data.get("modalidad") or "").strip() or None
    validacion_humana = bool(data.get("validacion_humana", False))
    fecha_validacion = (data.get("fecha_validacion") or "").strip() if validacion_humana else ""
    validated_by = (data.get("validated_by") or "").strip() if validacion_humana else ""

    if not caso:
        return jsonify({"error":"No se puede guardar: el caso bruto está vacío.",
                        "flags":[{"regla":"INPUT_EMPTY","gravedad":"alta","mensaje":"El caso bruto está vacío.", "bloquea_gold":True}]}), 400
    if not (informe_final or "").strip():
        return jsonify({"error":"No se puede guardar: el informe final está vacío.",
                        "flags":[{"regla":"FINAL_EMPTY","gravedad":"alta","mensaje":"El informe final está vacío.", "bloquea_gold":True}]}), 400

    try:
        metadata_torax = _metadatos_torax(data, caso) if current_region == "torax" else None
        ts, hubo_correccion = _persistir_caso(
            caso, informe_ia, informe_final, correccion=correccion, region=current_region,
            origen="app_local", proveedor=proveedor, modelo=modelo, explicacion=explicacion,
            modalidad=modalidad,
            validacion_humana=validacion_humana, fecha_validacion=fecha_validacion,
            validated_by=validated_by, case_status=data.get("case_status"), study_metadata=metadata_torax,
            generation_metadata=data.get("generation_metadata"))
    except ValueError as e:
        return jsonify({"error":str(e), "flags":validar(informe_final)}), 400

    # captura de regla candidata (opción B: siempre que haya diferencia)
    candidata = None
    if hubo_correccion:
        key = (data.get("key") or "").strip() or os.environ.get(env_key, "")
        if key:
            prop = proponer_regla_desde_correccion(caso, informe_ia, informe_final, correccion, proveedor, key, modelo)
            if prop and isinstance(prop, dict):
                candidata = {
                    "ts": ts,
                    "tipo": prop.get("tipo","puntual"),
                    "categoria": prop.get("categoria","otro"),
                    "regla": (prop.get("regla") or "").strip(),
                    "motivo": (prop.get("motivo") or "").strip(),
                    "estado": "pendiente",
                }
                with open(REGLAS_CANDIDATAS, "a", encoding="utf-8") as f:
                    f.write(json.dumps(candidata, ensure_ascii=False) + "\n")

    return jsonify({"archivo":f"caso_{ts}", "hubo_correccion":hubo_correccion,
                    "tiene_correccion":hubo_correccion, "candidata": candidata})


@app.route("/casos")
def route_casos():
    """Lista los casos guardados, más recientes primero, para el panel lateral."""
    items = []
    for jf in sorted(CASOS_DIR.glob("caso_*.json"), reverse=True):
        try:
            d = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        ts = d.get("case_id") or d.get("ts","")
        # fecha legible: 20260101_143022[_n] -> 01/01/2026 14:30
        fecha = ts
        if len(ts) >= 15:
            fecha = f"{ts[6:8]}/{ts[4:6]}/{ts[0:4]} {ts[9:11]}:{ts[11:13]}"
        preview = (d.get("input","") or "").strip().replace("\n"," ")[:110]
        nflags = len(d.get("flags",[]))
        items.append({"id":ts, "fecha":fecha, "preview":preview,
                      "nflags":nflags, "limpio":nflags==0,
                      "corregido":d.get("tiene_correccion", d.get("hubo_correccion",False))})
    return jsonify({"casos":items})


@app.route("/caso/<cid>")
def route_caso(cid):
    """Devuelve un caso guardado para volver a verlo."""
    jf = CASOS_DIR / f"caso_{cid}.json"
    if not jf.exists():
        return jsonify({"error":"no encontrado"})
    d = json.loads(jf.read_text(encoding="utf-8"))
    if "case_id" not in d:
        d["case_id"] = d.get("ts", cid)
    if "timestamp" not in d:
        d["timestamp"] = d.get("ts", "")
    if "correccion_radiologo" not in d:
        d["correccion_radiologo"] = d.get("correccion", "")
    if "tiene_correccion" not in d:
        d["tiene_correccion"] = d.get("hubo_correccion", False)
    d.setdefault("region", current_region)
    d.setdefault("region_name", _nombre_region(d.get("region") or current_region))
    d.setdefault("origen", "")
    d.setdefault("modalidad", None)
    d.setdefault("explicacion", "")
    d.setdefault("proveedor", "")
    d.setdefault("modelo", "")
    d.setdefault("prompt_version", "")
    d.setdefault("validator_version", "")
    d.setdefault("dataset_schema_version", "")
    d.setdefault("validacion_humana", False)
    d.setdefault("fecha_validacion", "")
    d.setdefault("validated_by", "")
    d.setdefault("gold_standard", False)
    d.setdefault("case_status", "draft")
    return jsonify(d)

if __name__ == "__main__":
    print("="*60)
    print(f"  Fábrica de casos abierta en:  http://{OPTIMUS_HOST}:{OPTIMUS_PORT}")
    print("  Tus casos se guardan en:      ", CASOS_DIR)
    print("  Para parar: Ctrl+C")
    print("="*60)
    app.run(host=OPTIMUS_HOST, port=OPTIMUS_PORT, debug=OPTIMUS_DEBUG)
