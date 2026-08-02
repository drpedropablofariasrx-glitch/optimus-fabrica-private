# INTEGRACION_CERVICAL_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Estado:** abdomen + lumbar + cervical funcionales; ninguna cuarta region integrada.

---

## Renombrado de la aplicacion

El nuevo punto de entrada principal es:

```text
python 00_APP/optimus_app.py
```

El archivo antiguo queda como wrapper de compatibilidad:

```text
python 00_APP/fabrica_abdomen.py
```

El wrapper importa la app desde `optimus_app.py`, no duplica rutas, HTML, validadores ni logica de persistencia. Al ejecutarse, muestra un aviso no bloqueante indicando el comando recomendado.

---

## Configuracion cervical

Se creo:

```text
03_cervical/region_config.py
```

Define:

- `REGION_ID = "cervical"`
- `REGION_NAME = "Columna cervical"`
- `PROMPT_PATH = 03_cervical/SYSTEM_PROMPT_cervical.txt`
- `VALIDATOR_MODULE = 03_cervical/validador_cervical.py`
- `CASES_DIR = 00_APP/casos_cervical`
- `DATASET_PATH = 00_APP/cervical_dataset.jsonl`
- `PROMPT_CONFIG_PATH = 03_cervical/fabrica_config.json`
- `PROMPT_HISTORY_DIR = 03_cervical/historial_prompts`
- `CANDIDATES_PATH = 03_cervical/reglas_candidatas.jsonl`
- `PROMPT_VERSION = "cervical-1.0"`
- `VALIDATOR_VERSION = "cervical-1.0"`
- `DATASET_SCHEMA_VERSION = "1.0"`

---

## Registro regional

`00_APP/region_registry.py` declara explicitamente, en orden estable:

1. abdomen
2. lumbar
3. cervical

Las tres estan `enabled=True`.

No se registraron torax, rodilla, mano-muneca, codo ni tobillo-pie.

---

## Selector

El selector visible ahora muestra:

- Abdomen
- Columna lumbar
- Columna cervical

Abdomen sigue siendo la region por defecto al arrancar.

Al cambiar de region se recargan:

- prompt efectivo;
- validador;
- rutas de casos y dataset;
- versiones;
- configuracion editable regional;
- historial;
- borrador/override;
- reglas candidatas.

Si existe contenido no guardado, la UI pide confirmacion antes de limpiar el estado actual.

---

## Aislamiento cervical/lumbar

Cervical conserva sus reglas anatomicas propias:

- `receso lateral` genera flag en cervical;
- `posterolateral` genera flag en cervical;
- las localizaciones validas son central, paracentral, paracentral-foraminal, foraminal y extraforaminal;
- se separa localizacion de repercusion anatomica.

Lumbar conserva sus reglas propias:

- puede usar `receso lateral`;
- no hereda la prohibicion cervical;
- mantiene razonamiento disco/faceta;
- no hereda la taxonomia cerrada cervical.

No se crearon reglas globales para estas diferencias.

---

## Persistencia

Los casos cervicales se guardan exclusivamente en:

```text
00_APP/casos_cervical
00_APP/cervical_dataset.jsonl
```

Cada registro cervical incluye:

- `region = "cervical"`
- `region_name = "Columna cervical"`
- `origen`
- `modalidad`
- `proveedor`
- `modelo`
- `prompt_version = "cervical-1.0"` salvo override regional
- `validator_version = "cervical-1.0"`
- `dataset_schema_version`
- `case_status`
- `validacion_humana`
- `gold_standard`

No se mezclan datasets entre abdomen, lumbar y cervical.

---

## Importador

El importador acepta:

- `[REGION]: abdomen`
- `[REGION]: lumbar`
- `[REGION]: cervical`

Si la region falta o no esta habilitada, el caso se rechaza con aviso claro. No se asume abdomen.

Cada caso importado se valida y persiste con el validador y las rutas de su region declarada.

---

## Gold Standard

La politica Gold se mantiene regional:

`gold_standard = true` solo si:

- `case_status == "validated"`;
- `validacion_humana == true`;
- `input` no esta vacio;
- `informe_final` no esta vacio;
- `dataset_schema_version` existe;
- no hay flags con `bloquea_gold == true`.

Los estados de abdomen, lumbar y cervical son independientes.

---

## Riesgos pendientes

1. La app sigue usando estado regional global en un unico proceso Flask local; no es multiusuario.
2. La UI sigue embebida en `optimus_app.py`; no se creo nucleo comun.
3. No se migran historicos.
4. No se integro ninguna cuarta region.
5. La capa `META_VISIBLE` sigue dentro de la app.

