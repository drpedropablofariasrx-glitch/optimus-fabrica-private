# Seguridad de descargas e inferencia local

Las fuentes permitidas son exclusivamente la API y releases de `ggml-org/llama.cpp` en GitHub y `Qwen/Qwen3-8B-GGUF` en Hugging Face. Se registran URL, release o revision, tamanos, SHA-256 local y, cuando la fuente lo publica, hash esperado. No se guardan tokens, claves ni datos clinicos en los logs del instalador.

El servidor se limita a `127.0.0.1`; los scripts rechazan otra interfaz y no activan herramientas. La inferencia local no envia casos a Internet. Para volver al proveedor de pruebas, defina `OPTIMUS_PROVIDER=mock` en el entorno de arranque de OPTIMUS.
