# DIAGNOSTICO_DE_ERRORES

| Codigo | Significado | Accion |
|---|---|---|
| `provider_not_configured` | URL local ausente o invalida | Configure `OPTIMUS_LLAMA_BASE_URL`. |
| `provider_unreachable` | llama-server no responde | Inicie llama-server por separado y revise URL/puerto. |
| `timeout` | El servidor no respondio a tiempo | Revise carga local o aumente el timeout de forma consciente. |
| `invalid_http_response` | HTTP no exitoso o contenido no JSON | Revise endpoint y version de llama-server. |
| `invalid_json` | Cuerpo JSON invalido | Revise logs de llama-server. |
| `malformed_model_response` | Falta `choices[0].message.content` | Use endpoint OpenAI-compatible. |
| `empty_model_response` | Contenido vacio | Revise modelo y servidor; no se inventa informe. |
| `internal_provider_error` | Error no clasificado | Consulte `logs/optimus.log` sin exponer datos clinicos. |

Las generaciones fallidas no se convierten en Gold ni se guardan como informes. Los logs registran codigo y estado, no el caso clinico completo, API keys ni cabeceras de autorizacion.
