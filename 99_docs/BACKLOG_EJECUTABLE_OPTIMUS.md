# Backlog ejecutable — OPTIMUS

Este backlog convierte la investigación técnica en entregables pequeños,
verificables y reversibles. No iniciar una fase si la anterior no tiene los
criterios de aceptación cumplidos. Mantener este archivo breve: marcar lo
hecho y actualizar el siguiente paso en `HANDOFF_CLAUDE.md`.

## P0 — Datos y evaluación (ahora)

- [x] **Corpus separado.** Perfiles de estilo, 638 pares SFT y 114 casos de
  benchmark privados y disjuntos.
- [ ] **Runner de benchmark base.** Crear `scripts/evaluar_modelo_local.py`:
  leer `benchmark_holdout.jsonl`, llamar solo a un endpoint local compatible
  con OpenAI y guardar métricas por caso en `datasets/private/`.
  - Métricas: latencia, tokens/s si el servidor los proporciona, lateralidad,
    negaciones, medidas, secciones PACS, omisiones y tiempo de corrección.
  - Aceptación: modo `--dry-run`, no modifica casos ni prompts, compara dos
    ejecuciones de forma reproducible.
- [ ] **Matriz de revisión humana.** Añadir a cada resultado campos editables
  `aceptado`, `tipo_correccion`, `segundos_revision` y `notas`.
  - Aceptación: exportable a JSONL/CSV privado; no incorpora resultados al SFT
    hasta aprobación explícita.

## P1 — Calidad del corpus

- [ ] **Clasificar modalidad de estilo.** Enriquecer candidatos de estilo solo
  cuando la modalidad esté documentada en la fuente; conservar `DESCONOCIDA`
  en lugar de inferir con certeza falsa.
  - Aceptación: perfiles por región/modalidad muestran procedencia y recuento.
- [ ] **Priorizar VuePACS.** Recuperar pares con dictado real de RM de rodilla,
  lumbar, hombro y cervical.
  - Aceptación: cada par tiene `candidate_type` y aprobación explícita.
- [ ] **Separar experimentos.** Poder filtrar SFT/benchmark por
  `candidate_type`, particularmente los pares VuePACS
  `historical_final_report_masked_impression` frente a dictados reales.

## P2 — Dictado local con Qwen3-ASR (prueba controlada)

- [ ] **Servicio ASR aislado.** Implementar un proceso local separado de
  Flask, con `/health` y `/transcribe`; empezar por Qwen3-ASR-0.6B.
  - Aceptación: sin audio ni red externa; el servicio se detiene/libera VRAM
    antes de generar con el LLM en la RTX 5060 de 8 GB.
- [ ] **Léxico versionado.** Crear vocabularios/hotwords por región y modalidad
  (p. ej. `asr_lexicon.py`) y registrar su versión en cada transcripción.
  - Aceptación: los hotwords son pistas, nunca se transforman en hallazgos.
- [ ] **Interfaz de dictado.** Botón de micrófono junto al cuadro de dictado;
  salida siempre editable y nunca genera un informe sin confirmación.
  - Aceptación: audio no se guarda por defecto; la región se detecta después de
    transcribir, igual que con texto pegado.
- [ ] **Benchmark ASR separado.** 30–50 dictados anonimizados y revisados;
  medir términos MSK, lateralidad, niveles, medidas y negaciones.

## P3 — Inferencia local estable

- [ ] **Fijar modelo base.** Evaluar Qwen local con el benchmark antes de
  comparar cuantizaciones o modificar prompts.
  - Aceptación: misma versión, GGUF, contexto y temperatura registrados.
- [ ] **Presupuesto de VRAM.** Una carga por vez: ASR o LLM, no ambos. Empezar
  por 4–8K de contexto y un usuario.
- [ ] **Salida estructurada.** Generar JSON validado y renderizar el informe
  PACS de forma determinista; no usar JSON para inventar campos no dictados.

## P4 — Fine-tuning experimental, no producción

- [ ] **Congelar corpus.** Copia privada con fecha, hash y manifiesto antes de
  entrenar; `benchmark_holdout` nunca entra en train.
- [ ] **Primer LoRA pequeño.** Entrenar fuera de Fábrica sobre `sft_train.jsonl`
  y registrar modelo base, hiperparámetros y origen de cada par.
  - Aceptación: mejora medible frente al modelo base en el mismo benchmark, sin
    aumento de errores de lateralidad, negación u omisiones.
- [ ] **Promoción manual.** Ningún adaptador se convierte en predeterminado sin
  revisión humana de los resultados y posibilidad de volver al modelo base.

## Decisiones ya tomadas

- Mantener `llama.cpp`/GGUF como ruta local inicial; no introducir vLLM,
  SGLang, multiusuario ni contexto extremo en la RTX 5060 de 8 GB.
- Las reglas clínicas, ejemplos de estilo, bibliografía RAG y datos SFT son
  capas diferentes; no mezclar sus funciones.
- Ganar minutos de corrección humana y reducir errores es más importante que
  aumentar tokens/s o parámetros.
