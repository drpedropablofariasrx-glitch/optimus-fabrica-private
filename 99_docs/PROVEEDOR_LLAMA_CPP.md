# PROVEEDOR_LLAMA_CPP

Un modelo es el archivo de pesos; llama.cpp es el motor; `llama-server` es el proceso HTTP externo. OPTIMUS solo es cliente HTTP: no descarga modelos, no usa bindings nativos y no inicia el servidor.

URL local por defecto: `http://127.0.0.1:8080`. Salud: `GET /health`. Generacion: `POST /v1/chat/completions` compatible con OpenAI, con `messages`, `temperature=0.1`, `top_p=0.9` y `stream=false`.

Variables: `OPTIMUS_PROVIDER=llama_cpp`, `OPTIMUS_LLAMA_BASE_URL`, `OPTIMUS_LLAMA_MODEL`, `OPTIMUS_LLAMA_TIMEOUT_SECONDS`, `OPTIMUS_LLAMA_API_KEY`, `OPTIMUS_LLAMA_HEALTH_PATH` y `OPTIMUS_LLAMA_MAX_TOKENS`.

Ejecute llama-server por separado y consulte `http://127.0.0.1:5000/health`. Si esta apagado, OPTIMUS arranca en estado degradado; inicie llama-server y vuelva a comprobar. Para cambiar de modelo, cambie `OPTIMUS_LLAMA_MODEL` y reinicie llama-server/OPTIMUS segun corresponda, sin modificar codigo.
