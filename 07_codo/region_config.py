from pathlib import Path


REGION_ID = "codo"
REGION_NAME = "Codo"
REGION_DIR = Path(__file__).resolve().parent
APP_DIR = REGION_DIR.parent / "00_APP"

PROMPT_PATH = REGION_DIR / "SYSTEM_PROMPT_codo.txt"
VALIDATOR_MODULE = REGION_DIR / "validador_codo.py"
CASES_DIR = APP_DIR / "casos_codo"
DATASET_PATH = APP_DIR / "codo_dataset.jsonl"
PROMPT_CONFIG_PATH = REGION_DIR / "fabrica_config.json"
PROMPT_HISTORY_DIR = REGION_DIR / "historial_prompts"
CANDIDATES_PATH = REGION_DIR / "reglas_candidatas.jsonl"

PROMPT_VERSION = "codo-1.0"
VALIDATOR_VERSION = "codo-1.1"
DATASET_SCHEMA_VERSION = "1.0"
