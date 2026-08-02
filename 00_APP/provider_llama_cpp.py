"""Cliente HTTP minimo para un llama-server externo compatible con OpenAI."""

import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


ERROR_CODES = {
    "provider_not_configured",
    "provider_unreachable",
    "timeout",
    "invalid_http_response",
    "invalid_json",
    "malformed_model_response",
    "empty_model_response",
    "generation_cancelled",
    "internal_provider_error",
}


class ProviderError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class GenerationResult:
    content: str
    metadata: dict


class LlamaCppProvider:
    def __init__(self, base_url, model="", timeout_seconds=120, api_key="", health_path="/health", max_tokens=None):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.timeout_seconds = int(timeout_seconds or 120)
        self.api_key = api_key or ""
        self.health_path = health_path or "/health"
        self.max_tokens = int(max_tokens) if max_tokens else None

    def is_configured(self):
        return self.base_url.startswith(("http://", "https://"))

    def get_model_name(self):
        return self.model

    def _sanitized_base_url(self):
        parts = urlsplit(self.base_url)
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))

    def get_provider_metadata(self):
        return {"provider": "llama_cpp", "base_url": self._sanitized_base_url(), "model": self.model}

    def health_check(self):
        if not self.is_configured():
            return {"reachable": False, "error_code": "provider_not_configured"}
        try:
            request = Request(self.base_url + self.health_path, method="GET")
            with urlopen(request, timeout=min(self.timeout_seconds, 10)) as response:
                return {"reachable": 200 <= response.status < 300, "status_code": response.status}
        except URLError:
            return {"reachable": False, "error_code": "provider_unreachable"}
        except TimeoutError:
            return {"reachable": False, "error_code": "timeout"}
        except Exception:
            return {"reachable": False, "error_code": "internal_provider_error"}

    def generate(self, system_prompt, case_text):
        if not self.is_configured():
            raise ProviderError("provider_not_configured", "llama_cpp no esta configurado.")
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": case_text},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "stream": False,
        }
        if self.model:
            payload["model"] = self.model
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.monotonic()
        request_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                raw = response.read()
                if response.status < 200 or response.status >= 300:
                    raise ProviderError("invalid_http_response", f"llama-server devolvio HTTP {response.status}.")
                if "json" not in content_type.lower():
                    raise ProviderError("invalid_http_response", "llama-server no devolvio JSON.")
        except HTTPError as exc:
            raise ProviderError("invalid_http_response", f"llama-server devolvio HTTP {exc.code}.") from exc
        except TimeoutError as exc:
            raise ProviderError("timeout", "Tiempo de espera agotado al contactar llama-server.") from exc
        except URLError as exc:
            raise ProviderError("provider_unreachable", "No se pudo contactar llama-server.") from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("internal_provider_error", "Error interno al contactar llama-server.") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ProviderError("invalid_json", "llama-server devolvio JSON invalido.") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("malformed_model_response", "Respuesta de llama-server sin choices[0].message.content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty_model_response", "llama-server devolvio contenido vacio.")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return GenerationResult(
            content=content.strip(),
            metadata={
                "provider": "llama_cpp",
                "model": self.model,
                "base_url": self._sanitized_base_url(),
                "request_timestamp": request_timestamp,
                "response_timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "token_usage": usage,
                "status": "success",
            },
        )
