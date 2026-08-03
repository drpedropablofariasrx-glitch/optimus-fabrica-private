# OPTIMUS

OPTIMUS es una fabrica local de informes radiologicos con ocho regiones aisladas. El arranque operativo para Windows esta en `99_docs/ARRANQUE_OPTIMUS_WINDOWS.md`.

- `ARRANCAR_OPTIMUS.bat`: inicia Flask localmente.
- `COMPROBAR_OPTIMUS.bat`: ejecuta pruebas y smoke test aislado.
- `.env.example`: referencia de configuracion, sin secretos.

## Credenciales de proveedores

Para no introducir una clave en la interfaz en cada arranque, copie
`config/local/provider_runtime.example.env` a
`config/local/provider_runtime.env` y complete las variables necesarias. Ese
archivo está excluido de Git y lo carga `ARRANCAR_OPTIMUS.bat` solo en el equipo
local. No guarde claves en prompts, código, documentos ni archivos versionados.

El soporte `llama_cpp` es opcional y usa un llama-server externo por HTTP. No se descarga ni ejecuta ningun modelo automaticamente.

## IA local opcional

- `INSTALAR_OPTIMUS_IA.bat`: instala de forma interactiva llama.cpp y el GGUF oficial de Qwen, fuera de Flask.
- `ARRANCAR_LLAMA_SERVER.bat`: inicia el servidor exclusivamente en `127.0.0.1`.
- `COMPROBAR_LLAMA_SERVER.bat`: comprueba salud local; `--test-generation` ejecuta solo una consulta no clinica.
- `REPARAR_OPTIMUS_IA.bat` y `DESINSTALAR_OPTIMUS_IA.bat`: recuperan o retiran el runtime sin tocar OPTIMUS ni datos clinicos.

Consulte `99_docs/INSTALACION_AUTOMATICA_IA.md` y `99_docs/SEGURIDAD_DESCARGAS.md`. Las pruebas automatizadas no realizan descargas reales, y MedGemma no esta integrado.

## Corpus para el futuro modelo local

`scripts/preparar_corpus_entrenamiento_local.py` crea, solo a partir de pares
aprobados, los perfiles de estilo, el conjunto SFT y un banco de evaluación
separado bajo `datasets/private/optimus_training_v1/`. No modifica Fábrica ni
entrena un modelo. Consulte `99_docs/CORPUS_LOCAL_QWEN.md` antes de iniciar un
fine-tuning de Qwen.

## Handoff para asistentes de código

`CLAUDE.md` obliga a empezar por `99_docs/HANDOFF_CLAUDE.md`: un único estado
operativo compacto que debe sustituirse tras cada cambio verificado. Con ello,
Claude puede orientarse sin volver a leer el repositorio ni los datos privados.
