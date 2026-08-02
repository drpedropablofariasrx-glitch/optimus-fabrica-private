from pathlib import Path


REGION_ID = "cervical"
REGION_NAME = "Columna cervical"
REGION_DIR = Path(__file__).resolve().parent
APP_DIR = REGION_DIR.parent / "00_APP"

PROMPT_PATH = REGION_DIR / "SYSTEM_PROMPT_cervical.txt"
VALIDATOR_MODULE = REGION_DIR / "validador_cervical.py"
CASES_DIR = APP_DIR / "casos_cervical"
DATASET_PATH = APP_DIR / "cervical_dataset.jsonl"
PROMPT_CONFIG_PATH = REGION_DIR / "fabrica_config.json"
PROMPT_HISTORY_DIR = REGION_DIR / "historial_prompts"
CANDIDATES_PATH = REGION_DIR / "reglas_candidatas.jsonl"

PROMPT_VERSION = "cervical-1.0"
VALIDATOR_VERSION = "cervical-1.0"
DATASET_SCHEMA_VERSION = "1.0"
