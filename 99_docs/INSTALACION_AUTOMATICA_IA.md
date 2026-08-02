# Instalacion automatica de IA local

`INSTALAR_OPTIMUS_IA.bat` invoca el instalador PowerShell sin privilegios de administrador. Descarga solo la release oficial mas reciente de `ggml-org/llama.cpp` y el archivo oficial `Qwen/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf`. No inicia OPTIMUS ni el servidor al terminar, salvo opciones explicitas.

Antes de confirmar muestra GPU NVIDIA, driver, release, asset CUDA 12, modelo, espacio y destinos. Requiere espacio estimado mas 3 GB. Usa `.part`, backups fechados y sustitucion atomica del runtime. El modo `-NonInteractive` no muestra preguntas; `-VerifyOnly`, `-SkipLlama`, `-SkipModel`, `-ForceRedownload`, `-Repair`, `-StartServerAfterInstall` y `-RunNonClinicalTest` permiten controlar el flujo.

Las rutas locales quedan en `runtime/`, `models/qwen/`, `logs/` y `config/local/`; no se almacenan binarios ni modelos en `00_APP`.

Ejemplos:

```powershell
.\INSTALAR_OPTIMUS_IA.ps1
.\INSTALAR_OPTIMUS_IA.ps1 -NonInteractive
.\INSTALAR_OPTIMUS_IA.ps1 -VerifyOnly
```
