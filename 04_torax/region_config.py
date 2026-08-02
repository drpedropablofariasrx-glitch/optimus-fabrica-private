from pathlib import Path


REGION_ID = "torax"
REGION_NAME = "Tórax"
REGION_DIR = Path(__file__).resolve().parent
APP_DIR = REGION_DIR.parent / "00_APP"

PROMPT_PATH = REGION_DIR / "SYSTEM_PROMPT_torax.txt"
VALIDATOR_MODULE = REGION_DIR / "validador_torax.py"
CASES_DIR = APP_DIR / "casos_torax"
DATASET_PATH = APP_DIR / "torax_dataset.jsonl"
PROMPT_CONFIG_PATH = REGION_DIR / "fabrica_config.json"
PROMPT_HISTORY_DIR = REGION_DIR / "historial_prompts"
CANDIDATES_PATH = REGION_DIR / "reglas_candidatas.jsonl"

PROMPT_VERSION = "torax-1.0"
VALIDATOR_VERSION = "torax-1.0"
DATASET_SCHEMA_VERSION = "1.0"

STUDY_TYPES = ("tc_torax", "angio_tc_tep", "cribado_pulmonar", "torax_abdomen_pelvis")
CLINICAL_CONTEXTS = ("general", "oncologico", "infeccioso", "trauma", "postquirurgico")
PROTOCOLS = ("sin_contraste", "con_contraste", "angiografico_pulmonar", "baja_dosis", "tap")
