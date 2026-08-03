# Corpus local de OPTIMUS

Este flujo prepara datos para el futuro modelo local. No entrena ni modifica
Fábrica, sus prompts, sus reglas clínicas ni los informes fuente.

## Activos generados

Ejecutar desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe scripts\preparar_corpus_entrenamiento_local.py
```

Los archivos se crean en `datasets/private/optimus_training_v1/`, excluidos de
Git:

- `perfiles_estilo_region_modalidad.json`: métricas de longitud, secciones y
  distribución de los informes aprobados, por región y modalidad cuando está
  disponible.
- `sft_train.jsonl`: pares aprobados para el futuro fine-tuning de Qwen, en
  formato de mensajes `system/user/assistant`.
- `benchmark_holdout.jsonl`: casos reservados para evaluar; nunca se deben usar
  durante el entrenamiento.
- `manifiesto_corpus.json`: trazabilidad, recuentos, criterios de exclusión y
  comprobación de que entrenamiento y evaluación no se solapan.

## Criterios actuales

1. Solo entran pares con `approval_status=approved` y `sft_eligible=true`.
2. Un filtro adicional excluye pares con posibles identificadores.
3. El 15 % de cada región con al menos ocho pares se reserva de forma estable
   para el benchmark. Las regiones escasas permanecen enteras en entrenamiento.
4. Los perfiles de estilo pueden incorporar informes históricos aprobados, pero
   esos informes no se convierten en ejemplos SFT si no tienen un par
   dictado→informe final confirmado.

## Antes de entrenar Qwen

- Revisar el manifiesto y una muestra de cada región/modalidad.
- Congelar una versión del corpus con fecha y hash.
- Medir el modelo base en `benchmark_holdout.jsonl`.
- Entrenar únicamente con `sft_train.jsonl` y repetir la evaluación exactamente
  sobre el mismo benchmark.

Un incremento de ejemplos no sustituye la revisión: para este proyecto gana el
modelo que reduce correcciones sin inventar hallazgos, lateralidad o negaciones.
