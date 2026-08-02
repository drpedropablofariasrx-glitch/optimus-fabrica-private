# INTEGRACION_TOBILLO_PIE_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-19  
**Estado:** septima region habilitada: `tobillo_pie`.

## Configuracion y selector

`08_tobillo_pie/region_config.py` define prompt, validador, casos, dataset, configuracion regional de prompt, historial y reglas candidatas.

- `CASES_DIR`: `00_APP/casos_tobillo_pie`
- `DATASET_PATH`: `00_APP/tobillo_pie_dataset.jsonl`
- `PROMPT_VERSION`: `tobillo_pie-1.0`
- `VALIDATOR_VERSION`: `tobillo_pie-1.1`

El registro explicito conserva el orden abdomen, lumbar, cervical, rodilla, mano_muneca, codo y tobillo_pie. El selector carga `Tobillo y pie` desde `/regiones`, con confirmacion ante contenido sin guardar y aislamiento de prompt, override, historial, candidatas y Gold.

## Subregiones y modalidades

La auditoria previa queda en `AUDITORIA_TOBILLO_PIE_PREINTEGRACION.md`. Se distinguen tobillo, retropie, mediopie, pie, antepie, dedos y estudios focales. Los checklists automaticos se aplican exclusivamente a RM con territorio apropiado; TC y ecografia no heredan el checklist de RM.

Lisfranc se valora en pie, mediopie o antepie. Una RM sin carga no permite excluir inestabilidad dinamica. El complejo lateral se individualiza en LPAA, LPC y LPAP ante lesion. Sindesmosis y retinaculos peroneos se revisan segun mecanismo y hallazgos, no como bloqueo universal.

El prompt conserva os trigonum con signos de pinzamiento posterior, fascitis sin repetir medidas en impresion y distension de la bursa intermetatarsiana. El validador avisa por terminologia no preferida o causalidad invertida, sin autocorregir. Tambien evita etiquetar tenosinovitis del FHL solo por liquido fisiologico.

## Persistencia, importador y Gold

Los casos se guardan solo en `casos_tobillo_pie` y `tobillo_pie_dataset.jsonl`, con region, nombre, origen, modalidad si existe, proveedor, modelo, versiones, esquema, estado, validacion humana y Gold.

El importador acepta `tobillo_pie`, `tobillo-pie`, `tobillo pie` y `pie_tobillo`, normalizados a `tobillo_pie`. Regiones desconocidas se rechazan.

Gold requiere estado `validated`, validacion humana, input e informe final no vacios, esquema presente y ausencia de flags `bloquea_gold`. Checklist parcial, campo limitado, ausencia de clasificacion y terminologia preferida no bloquean Gold.

## Riesgos pendientes

El proceso Flask mantiene estado regional global y el reconocimiento de modalidad/campo depende de texto. No se migran historicos ni se integra torax.
