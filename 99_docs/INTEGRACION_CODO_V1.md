# INTEGRACION_CODO_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-19  
**Estado:** sexta region habilitada: `codo`.

## Configuracion y selector

`07_codo/region_config.py` define prompt, validador, casos, dataset, configuracion regional de prompt, historial y reglas candidatas.

- `CASES_DIR`: `00_APP/casos_codo`
- `DATASET_PATH`: `00_APP/codo_dataset.jsonl`
- `PROMPT_VERSION`: `codo-1.0`
- `VALIDATOR_VERSION`: `codo-1.1`

El registro explicito mantiene el orden abdomen, lumbar, cervical, rodilla, mano_muneca y codo. El selector carga `Codo` desde `/regiones`, conservando la confirmacion por contenido no guardado y el aislamiento de prompt, override, historial, candidatas y Gold.

## Auditoria y campo variable

La auditoria previa se documenta en `AUDITORIA_CODO_PREINTEGRACION.md`. El checklist completo se limita a RM de codo convencional. Antebrazo, insercion distal del biceps, region olecraniana, ecografia, TC y estudios parciales no exigen estructuras fuera de campo ni generan bloqueos Gold.

El contenido regional incluye articulaciones, lesiones osteocondrales, edema oseo, tendones extensores/flexores, biceps/triceps distales, complejos ligamentarios, nervios cubital/mediano/radial, musculos y partes blandas. No adopta TFCC, Guyon, tunel carpiano, reglas de columna, patelofemorales, Lisfranc, UH abdominales ni reglas toracicas.

## Reglas clinicas auditadas

D4 protege la medida de retraccion en rotura completa de biceps distal y esta documentada en `SEGURIDAD_UNIDADES_CODO.md`: conserva literalmente cm/mm, avisa por ausencia de unidad, discrepancia interna o ausencia de retraccion, y no corrige silenciosamente.

D3 avisa de forma conservadora ante redundancia de epicondilitis lateral y tendinosis del origen extensor en el mismo contexto. No modifica texto ni bloquea Gold. D5 avisa si se afirma estabilidad, progresion o mejoria pese a expresar que no hay estudios previos comparables. Los cambios postquirurgicos sin afirmacion de recidiva no generan falso positivo.

## Persistencia e importador

Los casos de codo se escriben exclusivamente en su carpeta y JSONL, con region, nombre, origen, modalidad cuando se aporta, proveedor, modelo, versiones, esquema, estado, validacion humana y Gold.

El importador acepta `codo` y el alias documentado `elbow`, ambos normalizados a `codo`; regiones desconocidas se rechazan.

## Gold Standard y riesgos

Gold requiere estado `validated`, validacion humana, input e informe final no vacios, version de esquema y ausencia de flags `bloquea_gold`. Checklist, campo limitado, unidades, redundancia y evolucion generan avisos no bloqueantes.

Riesgos pendientes: estado regional global dentro del proceso Flask y deteccion textual del campo. No se migran historicos ni se habilitan tobillo-pie o torax.
