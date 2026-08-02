# INTEGRACION_TORAX

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-20  
**Estado:** torax integrado como octava region funcional.

## Ubicacion canonica

La ubicacion canonica es `04_torax`. Se conserva por ser la carpeta historica existente. No se creo `09_torax`, no se movieron archivos y no existen dos configuraciones toracicas activas.

## Archivos y contaminaciones corregidas

Se creo `04_torax/region_config.py` y se actualizaron el prompt y validador existentes. Se elimino la reutilizacion de reglas abdominales, la macro PieloTC y la contradiccion sobre titulos de estudio. TAP dispone de checklist propio; no importa prompt, validador, dataset ni persistencia de abdomen.

## Taxonomia y validacion

La region separa `study_type`, `clinical_context`, `protocol`, `contrast` y `comparison_available`. El detalle se documenta en `TAXONOMIA_TORAX_V1.md`.

Bloqueos Gold iniciales: tipo/contexto/protocolo desconocido, incoherencia critica tipo-protocolo, Angio-TC TEP sin valoracion arterial pulmonar, TAP sin uno de sus tres territorios y macro claramente incompatible.

VD/VI, calidad angiografica, Lung-RADS, RECIST y lenguaje evolutivo son avisos contextuales, no bloqueos por defecto.

## Resultado

Torax aparece una sola vez en registro y selector. Sus casos se escriben exclusivamente en `00_APP/casos_torax` y `00_APP/torax_dataset.jsonl`. Las pruebas de integracion, TAP, aliases, perfiles y aislamiento pasan junto a las siete regiones previas.
