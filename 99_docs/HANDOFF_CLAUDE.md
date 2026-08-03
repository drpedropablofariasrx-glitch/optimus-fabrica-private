# OPTIMUS — handoff operativo para Claude

Actualizado: 2026-08-04 · Leer este archivo antes de abrir el resto del repo.

## Objetivo

Construir un sistema y, más adelante, un modelo local tipo Qwen que reproduzca
el estilo del radiólogo en los proyectos MSK/Radiología. Mantener siempre
validación humana; no usarlo como sustituto diagnóstico.

## Estado funcional relevante

- Fábrica usa hasta 2 referencias de estilo aprobadas de la misma región por
  generación; se registra `style_candidate_ids` en `generation_metadata`.
- Son referencias efímeras: no alteran `prompt_base`, `prompt_override`,
  validadores, Gold Standard ni las reglas clínicas.
- La selección actual es por región, no por modalidad.
- El selector de modelos se filtra por proveedor y la app se ejecuta en
  `http://127.0.0.1:5000/`.

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

## Artefactos y comandos

```powershell
.venv\Scripts\python.exe scripts\preparar_corpus_entrenamiento_local.py
Push-Location tests; ..\.venv\Scripts\python.exe -m unittest test_preparar_corpus_entrenamiento_local test_extraer_pares_historicos_sft_v2 test_optimus_app_sft_revision test_optimus_app_style_reference -v; Pop-Location
```

- Generador: `scripts/preparar_corpus_entrenamiento_local.py`.
- Guía: `99_docs/CORPUS_LOCAL_QWEN.md`.
- Salidas privadas: perfiles por región/modalidad, SFT train, benchmark y
  manifiesto. No se suben a Git.

## Próximos pasos ordenados

1. Recuperar y aprobar más pares de VuePACS con dictado real; priorizar RM de
   rodilla, lumbar, hombro y cervical.
2. Mejorar clasificación región/modalidad sin inventar valores desconocidos.
3. Evaluar el modelo base sobre los 114 casos de benchmark antes de entrenar.
4. Congelar corpus/versionar manifiesto y hacer fine-tuning solo con train.
5. Repetir el benchmark: estilo, lateralidad, negaciones, omisiones, formato
   PACS y tiempo de corrección humana.

## Versiones recientes ya en Git

- `c8497ac` Preserve SFT pair provenance.
- `d461199` Prepare local style SFT and benchmark corpus.
- `9104574` Use approved style references by default.

## Antes de editar

- Ejecutar `git status --short`; hay trabajo local potencialmente ajeno.
- No tocar ni versionar `datasets/private/`, `config/local/`, `.env`, logs o
  informes fuente.
- Al terminar una tarea, actualizar este archivo de forma concisa (sustituir,
  no añadir historial) con cambio, pruebas, commit y siguiente acción.
