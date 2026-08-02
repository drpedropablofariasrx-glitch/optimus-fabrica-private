# INTEGRACION_MANO_MUNECA_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-19  
**Estado:** quinta region habilitada: `mano_muneca`.

## Configuracion regional

`06_mano_muneca/region_config.py` define el prompt, validador, directorio de
casos, dataset, configuracion de prompt, historial y reglas candidatas propios.

- `CASES_DIR`: `00_APP/casos_mano_muneca`
- `DATASET_PATH`: `00_APP/mano_muneca_dataset.jsonl`
- `PROMPT_VERSION`: `mano_muneca-1.0`
- `VALIDATOR_VERSION`: `mano_muneca-1.1`

El registro explicito declara cinco regiones, en orden: abdomen, lumbar,
cervical, rodilla y mano_muneca. No hay descubrimiento dinamico.

## Selector y aislamiento

El selector se alimenta de `/regiones` y muestra `Mano y muñeca`. Al activarla
recarga prompt, validador, rutas, versiones, historial, borrador, override,
reglas candidatas y estado Gold de esa region. La confirmacion ante contenido
sin guardar se conserva.

Abdomen sigue como region por defecto. No se modificaron los prompts o
validadores clinicos de las cuatro regiones anteriores.

## Campo anatomico, modalidad y reglas clinicas

La region admite mano, muneca, dedos, carpo o articulacion concreta en RM, TC o
ecografia. El prompt trata TFCC, ligamentos escafolunar/lunopiramidal, tendones,
nervios, tunel carpiano, Guyon, huesos, articulaciones, gangliones, variantes y
partes blandas como contenido condicionado al campo.

Los avisos B1/B2 solo se aplican cuando corresponde: B1 para mano completa y
B2 para muneca. Un estudio limitado de dedo no exige nervios, tunel, Guyon ni
TFCC y esos avisos no bloquean Gold.

La severidad se mantiene regional: leve, moderada, moderada-avanzada, avanzada.
La cronicidad se mantiene regional: aguda, subaguda, cronica, degenerativa,
postraumatica, postquirurgica. La correccion D3 esta documentada en
`CORRECCION_VALIDADOR_MANO_MUNECA.md`.

## Persistencia e importador

Cada caso conserva `region`, `region_name`, origen, modalidad si se aporta,
proveedor, modelo, versiones, esquema, estado, validacion humana y Gold. No se
mezcla con los datasets de las otras cuatro regiones.

El importador acepta `mano_muneca`, `mano-muneca` y `mano muñeca`, y los
normaliza internamente a `mano_muneca`. Las regiones desconocidas se rechazan.

## Gold Standard

La politica existente no cambia: Gold requiere estado `validated`, validacion
humana, input e informe final no vacios, version de esquema y ausencia de flags
con `bloquea_gold = true`. Los avisos de checklist y campo limitado no bloquean.

## Riesgos pendientes

1. La app mantiene estado regional global dentro del proceso Flask local.
2. La deteccion de campo es textual y no sustituye la revision clinica.
3. No se migran historicos ni se habilitan codo, tobillo-pie o torax.
