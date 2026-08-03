# OPTIMUS — handoff operativo para Claude

Actualizado: 2026-08-04 · Leer este archivo antes de abrir el resto del repo.

## Objetivo

Construir un sistema y, más adelante, un modelo local tipo Qwen que reproduzca
el estilo del radiólogo en los proyectos MSK/Radiología. Mantener siempre
validación humana; no usarlo como sustituto diagnóstico.

## Estado funcional relevante

- Fábrica usa hasta 2 referencias de estilo aprobadas de la misma región por
  generación; se registra `style_candidate_ids` en `generation_metadata`.
- Nueva capa de bibliografía RAG, 100% local: `00_APP/rag_biblioteca.py`
  (embeddings BGE-M3, búsqueda por similitud coseno en memoria, sin servidor).
  Activada por defecto en `/generar` (casilla "Usar bibliografía local"):
  busca automáticamente a partir del propio dictado y antepone hasta 3
  fragmentos como referencia explícitamente etiquetada (nunca instrucción
  clínica, nunca dato del paciente). IDs usados en
  `generation_metadata.bibliografia_chunk_ids`.
  - Ingesta: `scripts/preparar_biblioteca_rag.py` (pdfplumber, troceado por
    estructura con recomposición de guiones de corte de línea).
  - Consulta manual: ruta `/biblioteca`.
  - Índice actual solo cubre regiones `rodilla` y `tobillo_pie` (540 chunks,
    fuente: curso Stoller MSK). El resto de regiones no tiene bibliografía
    indexada todavía — la casilla simplemente no encuentra nada, sin error.
  - Dependencia opcional: `requirements-biblioteca.txt` (pdfplumber; BGE-M3
    ya requiere torch/sentence-transformers, ya instalados en este equipo).
- Ambas capas (estilo y bibliografía) son efímeras: no alteran `prompt_base`,
  `prompt_override`, validadores, Gold Standard ni las reglas clínicas.
- La selección de estilo es por región, no por modalidad.
- El selector de modelos se filtra por proveedor y la app se ejecuta en
  `http://127.0.0.1:5000/` (puerto 5000 puede estar ocupado por otro
  proceso ajeno; usar `OPTIMUS_PORT` para arrancar en otro puerto si hace
  falta probar en paralelo).

## Corpus local actual (privado, no Git)

Fuente: `datasets/private/optimus_training_v1/manifiesto_corpus.json`.

- 807 informes aprobados para estilo.
- 752 pares SFT aprobados y elegibles.
- 638 pares en `sft_train.jsonl`.
- 114 casos en `benchmark_holdout.jsonl`, disjuntos del entrenamiento.
- 168/168 casos recuperados de VuePACS están aprobados.
- No se ha entrenado ningún modelo local todavía.

Matiz: los pares VuePACS llevan `candidate_type`
`historical_final_report_masked_impression`; son informes propios históricos
reconstruidos, no asumir que equivalen a dictado original natural. Preservar
este campo para ponderar o separar experimentos.

Bibliografía RAG (separada del corpus de estilo/SFT anterior):
`datasets/private/optimus_biblioteca_v1/` — chunks + embeddings + metadatos,
por región. No mezclar con reglas clínicas ni con el corpus de estilo.

## Artefactos y comandos

```powershell
.venv\Scripts\python.exe scripts\preparar_corpus_entrenamiento_local.py
.venv\Scripts\python.exe scripts\preparar_biblioteca_rag.py --input-dir <carpeta_pdfs> --region <region_id>
Push-Location tests; ..\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v; Pop-Location
```

- Generador SFT/estilo: `scripts/preparar_corpus_entrenamiento_local.py`.
- Bibliografía: `scripts/preparar_biblioteca_rag.py` + `00_APP/rag_biblioteca.py`.
- Guía SFT: `99_docs/CORPUS_LOCAL_QWEN.md`.
- Salidas privadas: perfiles por región/modalidad, SFT train, benchmark,
  manifiesto, índice de bibliografía. No se suben a Git.

## Próximos pasos ordenados

1. Ampliar la bibliografía RAG a más regiones (hoy solo rodilla/tobillo_pie).
2. Recuperar y aprobar más pares de VuePACS con dictado real; priorizar RM de
   rodilla, lumbar, hombro y cervical.
3. Mejorar clasificación región/modalidad sin inventar valores desconocidos.
4. Evaluar el modelo base sobre los 114 casos de benchmark antes de entrenar.
5. Congelar corpus/versionar manifiesto y hacer fine-tuning solo con train.
6. Repetir el benchmark: estilo, lateralidad, negaciones, omisiones, formato
   PACS y tiempo de corrección humana.

## Versiones recientes ya en Git

- `612dedb` Add local RAG bibliography layer for report generation.
- `c8497ac` Preserve SFT pair provenance.
- `d461199` Prepare local style SFT and benchmark corpus.
- `9104574` Use approved style references by default.

## Antes de editar

- Ejecutar `git status --short`; hay trabajo local potencialmente ajeno
  (p.ej. `scripts/capturar_vuepacs.py` puede tener cambios locales sin
  commitear de otra tarea: no revertir ni incluir sin que te lo pidan).
- No tocar ni versionar `datasets/private/`, `config/local/`, `.env`, logs o
  informes fuente.
- Al terminar una tarea, actualizar este archivo de forma concisa (sustituir,
  no añadir historial) con cambio, pruebas, commit y siguiente acción.
