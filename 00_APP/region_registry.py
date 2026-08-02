import importlib.util
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent

REGIONS = {
    "abdomen": {
        "config_module": str(PROJECT_ROOT / "01_abdomen" / "region_config.py"),
        "enabled": True,
    },
    "lumbar": {
        "config_module": str(PROJECT_ROOT / "02_lumbar" / "region_config.py"),
        "enabled": True,
    },
    "cervical": {
        "config_module": str(PROJECT_ROOT / "03_cervical" / "region_config.py"),
        "enabled": True,
    },
    "rodilla": {
        "config_module": str(PROJECT_ROOT / "05_rodilla" / "region_config.py"),
        "enabled": True,
    },
    "mano_muneca": {
        "config_module": str(PROJECT_ROOT / "06_mano_muneca" / "region_config.py"),
        "enabled": True,
    },
    "codo": {
        "config_module": str(PROJECT_ROOT / "07_codo" / "region_config.py"),
        "enabled": True,
    },
    "tobillo_pie": {
        "config_module": str(PROJECT_ROOT / "08_tobillo_pie" / "region_config.py"),
        "enabled": True,
    },
    "torax": {
        "config_module": str(PROJECT_ROOT / "04_torax" / "region_config.py"),
        "enabled": True,
    }
}


def list_regions():
    return [
        {"region_id": region_id, "enabled": data.get("enabled", False)}
        for region_id, data in REGIONS.items()
    ]


def get_region_config(region_id):
    data = REGIONS.get(region_id)
    if not data:
        raise KeyError(f"Región no registrada: {region_id}")
    if not data.get("enabled", False):
        raise ValueError(f"Región no habilitada: {region_id}")
    path = Path(data["config_module"])
    if not path.exists():
        raise FileNotFoundError(f"No se encontró la configuración regional: {path}")
    spec = importlib.util.spec_from_file_location(f"optimus_region_config_{region_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_region_prompt(region_id):
    config = get_region_config(region_id)
    prompt_path = Path(config.PROMPT_PATH)
    if not prompt_path.exists():
        raise FileNotFoundError(f"No se encontró el SYSTEM_PROMPT regional: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError(f"El SYSTEM_PROMPT regional está vacío: {prompt_path}")
    return prompt.rstrip("\n")


def load_region_validator(region_id):
    config = get_region_config(region_id)
    validator_path = Path(config.VALIDATOR_MODULE)
    if not validator_path.exists():
        raise FileNotFoundError(f"No se encontró el validador regional: {validator_path}")
    spec = importlib.util.spec_from_file_location(f"optimus_validator_{region_id}", validator_path)
    module = importlib.util.module_from_spec(spec)
    # dataclass con anotaciones diferidas necesita el modulo visible al ejecutarse.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "validar"):
        raise AttributeError(f"El validador regional no expone validar(): {validator_path}")
    return module
