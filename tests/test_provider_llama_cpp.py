import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parents[1] / "00_APP"
sys.path.insert(0, str(APP_DIR))
from provider_llama_cpp import LlamaCppProvider, ProviderError


def response(status=200, content_type="application/json", payload=None):
    mocked = MagicMock()
    mocked.status = status
    mocked.headers.get.return_value = content_type
    mocked.read.return_value = json.dumps(payload if payload is not None else {
        "choices": [{"message": {"content": "Informe válido"}}],
    }).encode("utf-8")
    mocked.__enter__.return_value = mocked
    return mocked


class LlamaCppProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = LlamaCppProvider("http://127.0.0.1:8080", model="local-model", timeout_seconds=3)

    def test_configuracion_y_metadatos_no_exponen_api_key(self):
        provider = LlamaCppProvider("http://127.0.0.1:8080", model="m", api_key="secret")
        self.assertTrue(provider.is_configured())
        self.assertEqual(provider.get_model_name(), "m")
        self.assertNotIn("api_key", provider.get_provider_metadata())

    @patch("provider_llama_cpp.urlopen")
    def test_health_y_respuesta_valida(self, mocked_urlopen):
        mocked_urlopen.side_effect = [response(), response(payload={
            "choices": [{"message": {"content": "Informe local"}}],
            "usage": {"completion_tokens": 12},
        })]
        self.assertTrue(self.provider.health_check()["reachable"])
        result = self.provider.generate("sistema", "caso")
        self.assertEqual(result.content, "Informe local")
        self.assertEqual(result.metadata["token_usage"]["completion_tokens"], 12)
        self.assertGreaterEqual(result.metadata["latency_ms"], 0)

    @patch("provider_llama_cpp.urlopen")
    def test_json_y_estructura_invalidos(self, mocked_urlopen):
        invalid = response()
        invalid.read.return_value = b"no-json"
        mocked_urlopen.return_value = invalid
        with self.assertRaisesRegex(ProviderError, "JSON invalido"):
            self.provider.generate("s", "c")

        mocked_urlopen.return_value = response(payload={"choices": []})
        with self.assertRaisesRegex(ProviderError, "choices"):
            self.provider.generate("s", "c")

    @patch("provider_llama_cpp.urlopen")
    def test_contenido_vacio_y_content_type_invalido(self, mocked_urlopen):
        mocked_urlopen.return_value = response(payload={"choices": [{"message": {"content": " "}}]})
        with self.assertRaisesRegex(ProviderError, "contenido vacio"):
            self.provider.generate("s", "c")
        mocked_urlopen.return_value = response(content_type="text/html")
        with self.assertRaisesRegex(ProviderError, "no devolvio JSON"):
            self.provider.generate("s", "c")

    def test_servidor_no_configurado_no_arranca_procesos(self):
        provider = LlamaCppProvider("")
        self.assertFalse(provider.is_configured())
        self.assertEqual(provider.health_check()["error_code"], "provider_not_configured")
        with self.assertRaisesRegex(ProviderError, "no esta configurado"):
            provider.generate("s", "c")

    @patch("provider_llama_cpp.urlopen", side_effect=URLError("offline"))
    def test_servidor_no_disponible(self, mocked_urlopen):
        estado = self.provider.health_check()
        self.assertFalse(estado["reachable"])
        self.assertEqual(estado["error_code"], "provider_unreachable")
        with self.assertRaises(ProviderError) as captured:
            self.provider.generate("s", "c")
        self.assertEqual(captured.exception.code, "provider_unreachable")


if __name__ == "__main__":
    unittest.main()
