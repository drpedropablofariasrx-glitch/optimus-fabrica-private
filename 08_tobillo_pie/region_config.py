from pathlib import Path


REGION_ID = "tobillo_pie"
REGION_NAME = "Tobillo y pie"
REGION_DIR = Path(__file__).resolve().parent
APP_DIR = REGION_DIR.parent / "00_APP"

PROMPT_PATH = REGION_DIR / "SYSTEM_PROMPT_tobillo_pie.txt"
VALIDATOR_MODULE = REGION_DIR / "validador_tobillo_pie.py"
CASES_DIR = APP_DIR / "casos_tobillo_pie"
DATASET_PATH = APP_DIR / "tobillo_pie_dataset.jsonl"
PROMPT_CONFIG_PATH = REGION_DIR / "fabrica_config.json"
PROMPT_HISTORY_DIR = REGION_DIR / "historial_prompts"
CANDIDATES_PATH = REGION_DIR / "reglas_candidatas.jsonl"

PROMPT_VERSION = "tobillo_pie-1.0"
VALIDATOR_VERSION = "tobillo_pie-1.1"
DATASET_SCHEMA_VERSION = "1.0"
