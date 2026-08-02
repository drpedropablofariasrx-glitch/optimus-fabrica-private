from pathlib import Path


REGION_ID = "mano_muneca"
REGION_NAME = "Mano y muñeca"
REGION_DIR = Path(__file__).resolve().parent
APP_DIR = REGION_DIR.parent / "00_APP"

PROMPT_PATH = REGION_DIR / "SYSTEM_PROMPT_mano_muneca.txt"
VALIDATOR_MODULE = REGION_DIR / "validador_mano_muneca.py"
CASES_DIR = APP_DIR / "casos_mano_muneca"
DATASET_PATH = APP_DIR / "mano_muneca_dataset.jsonl"
PROMPT_CONFIG_PATH = REGION_DIR / "fabrica_config.json"
PROMPT_HISTORY_DIR = REGION_DIR / "historial_prompts"
CANDIDATES_PATH = REGION_DIR / "reglas_candidatas.jsonl"

PROMPT_VERSION = "mano_muneca-1.0"
VALIDATOR_VERSION = "mano_muneca-1.1"
DATASET_SCHEMA_VERSION = "1.0"
