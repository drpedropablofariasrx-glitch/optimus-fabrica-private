# INTEGRACION_LUMBAR_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Estado:** abdomen + lumbar funcionales; ninguna tercera region integrada.

---

## Objetivo cumplido

Se integro `lumbar` como segunda region funcional manteniendo `abdomen` como region por defecto.

La app sigue arrancando igual:

```text
python 00_APP/fabrica_abdomen.py
```

No se creo `core/`, FastAPI, SQLite, plugins, Qwen ni selector para regiones no aprobadas.

---

## Configuracion regional lumbar

Se creo:

```text
02_lumbar/region_config.py
```

Define:

- `REGION_ID = "lumbar"`
- `REGION_NAME = "Columna lumbar"`
- `PROMPT_PATH = 02_lumbar/SYSTEM_PROMPT_lumbar.txt`
- `VALIDATOR_MODULE = 02_lumbar/validador_lumbar.py`
- `CASES_DIR = 00_APP/casos_lumbar`
- `DATASET_PATH = 00_APP/lumbar_dataset.jsonl`
- `PROMPT_CONFIG_PATH = 02_lumbar/fabrica_config.json`
- `PROMPT_HISTORY_DIR = 02_lumbar/historial_prompts`
- `CANDIDATES_PATH = 02_lumbar/reglas_candidatas.jsonl`
- `PROMPT_VERSION = "lumbar-1.0"`
- `VALIDATOR_VERSION = "lumbar-1.0"`
- `DATASET_SCHEMA_VERSION = "1.0"`

Abdomen usa estructura equivalente en `01_abdomen/region_config.py`.

---

## Registro regional

`00_APP/region_registry.py` mantiene un diccionario explicito:

```text
abdomen: enabled=True
lumbar: enabled=True
```

No hay descubrimiento dinamico. No se registraron cervical, torax, rodilla, mano-muneca, codo ni tobillo-pie.

`list_regions()` devuelve ambas regiones en orden estable: abdomen primero, lumbar despues.

---

## Selector visible

Se agrego un selector simple en la barra lateral:

- Abdomen
- Columna lumbar

Comportamiento:

- arranque por defecto: abdomen;
- cambio de region: llama a `/region`;
- recarga prompt efectivo, validador, rutas, dataset, versiones, historial y reglas candidatas;
- actualiza el titulo visible de la region;
- limpia el caso actual;
- si hay contenido no guardado, exige confirmacion.

No se redisenio la interfaz.

---

## Aislamiento regional

Cada region tiene aislados:

- prompt base;
- prompt override;
- prompt borrador;
- historial de cambios;
- reglas candidatas;
- carpeta de casos;
- dataset JSONL;
- versiones;
- validador;
- estado Gold por caso.

La configuracion de proveedores LLM sigue siendo global, como estaba permitido.

---

## Persistencia

Los casos nuevos escriben:

- `region`
- `region_name`
- `origen`
- `modalidad`
- `prompt_version`
- `validator_version`
- `dataset_schema_version`
- `case_status`
- `validacion_humana`
- `gold_standard`
- `proveedor`
- `modelo`

Lumbar se guarda exclusivamente en:

```text
00_APP/casos_lumbar
00_APP/lumbar_dataset.jsonl
```

Abdomen se mantiene en:

```text
00_APP/casos_abdomen
00_APP/abdomen_dataset.jsonl
```

---

## Importador hospital-casa

El importador enruta por `[REGION]`.

Acepta solo:

- `abdomen`
- `lumbar`

Si falta region o se declara una region no habilitada, el caso se rechaza con aviso claro. No se asume abdomen silenciosamente.

Cada caso importado se valida y persiste usando la configuracion de su region declarada.

---

## Prompt y validador lumbar

Lumbar conserva:

- estructura nivel por nivel;
- terminologia de canal y foramenes;
- uso de `receso lateral`;
- razonamiento disco/faceta;
- impresion diagnostica jerarquizada;
- pie chileno condicionado;
- exclusion de `TAGS` y `DATASET_ENTRY` visibles.

No se trasladaron reglas cervicales a lumbar.

---

## Gold Standard regional

La logica Gold se aplica por region activa:

`gold_standard = true` solo si:

- `case_status == "validated"`;
- `validacion_humana == true`;
- `input` e `informe_final` no estan vacios;
- `dataset_schema_version` existe;
- no hay flags con `bloquea_gold == true`;
- el registro pertenece a la region activa en el momento de calcular Gold.

Validar un caso lumbar no modifica el estado de casos abdomen.

---

## Correccion de contaminacion lumbar

Se retiraron de lumbar referencias a:

- `Insall-Salvati`
- `Caton-Deschamps`
- `TT-TG`
- `CDI`

No se activo ninguna regla nueva en rodilla. Queda documentado en:

```text
99_docs/CORRECCION_CONTAMINACION_LUMBAR.md
```

---

## Riesgos pendientes

1. La app sigue siendo un unico proceso Flask con estado regional global; para uso local esta bien, pero no es multiusuario.
2. La UI sigue embebida en `fabrica_abdomen.py`; no se extrajo frontend ni nucleo comun.
3. No se migran historicos.
4. El importador acepta solo abdomen/lumbar; otras regiones quedan fuera por decision de fase.
5. La capa `META_VISIBLE` sigue en la app, no en un modulo comun.

