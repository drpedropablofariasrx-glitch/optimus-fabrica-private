#!/usr/bin/env python3
"""Smoke test local, aislado y sin llamadas a proveedores reales."""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "00_APP"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-llama", action="store_true")
    args = parser.parse_args()
    temp = Path(tempfile.mkdtemp(prefix="optimus_smoke_"))
    try:
        os.environ["OPTIMUS_DATA_DIR"] = str(temp / "data")
        os.environ["OPTIMUS_LOG_DIR"] = str(temp / "logs")
        os.environ["OPTIMUS_PROVIDER"] = "mock"
        sys.path.insert(0, str(APP_DIR))
        import optimus_app as app_module

        client = app_module.app.test_client()
        health = client.get("/health").get_json()
        assert health["region_count"] == 8
        assert health["data_dir_writable"]
        print("Regiones registradas:", ", ".join(health["registered_regions"]))
        print("Proveedor activo:", health["active_provider"], "escribible:", health["data_dir_writable"])
        for region in health["registered_regions"]:
            response = client.post("/region", json={"region": region})
            assert response.status_code == 200
            config = app_module.REGION_CONFIG
            assert config.PROMPT_PATH.exists()
            assert config.VALIDATOR_MODULE.exists()
        app_module.activar_region("abdomen")
        generated = client.post("/generar", json={"caso": "caso sintetico", "provider": "mock", "model": "mock-radiology"})
        assert generated.status_code == 200
        report = generated.get_json()["informe"]
        saved = client.post("/guardar", json={
            "caso": "caso sintetico",
            "informe_ia": report,
            "informe_final": report,
            "provider": "mock",
            "model": "mock-radiology",
            "case_status": "generated",
        })
        assert saved.status_code == 200
        records = list((temp / "data" / "casos_abdomen").glob("caso_*.json"))
        assert records and not json.loads(records[0].read_text(encoding="utf-8"))["gold_standard"]
        if args.check_llama:
            from provider_llama_cpp import LlamaCppProvider
            estado = LlamaCppProvider(
                os.environ.get("OPTIMUS_LLAMA_BASE_URL", "http://127.0.0.1:8080"),
                health_path=os.environ.get("OPTIMUS_LLAMA_HEALTH_PATH", "/health"),
            ).health_check()
            print("llama_cpp reachable:", estado.get("reachable", False))
        print("SMOKE OK: 8 regiones, persistencia sintetica no Gold, datos temporales limpios al salir.")
        return 0
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
