# INTEGRACION_RODILLA_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Estado:** abdomen + lumbar + cervical + rodilla funcionales; ninguna quinta region integrada.

---

## Configuracion rodilla

Se creo:

```text
05_rodilla/region_config.py
```

Define:

- `REGION_ID = "rodilla"`
- `REGION_NAME = "Rodilla"`
- `PROMPT_PATH = 05_rodilla/SYSTEM_PROMPT_rodilla.txt`
- `VALIDATOR_MODULE = 05_rodilla/validador_rodilla.py`
- `CASES_DIR = 00_APP/casos_rodilla`
- `DATASET_PATH = 00_APP/rodilla_dataset.jsonl`
- `PROMPT_CONFIG_PATH = 05_rodilla/fabrica_config.json`
- `PROMPT_HISTORY_DIR = 05_rodilla/historial_prompts`
- `CANDIDATES_PATH = 05_rodilla/reglas_candidatas.jsonl`
- `PROMPT_VERSION = "rodilla-1.0"`
- `VALIDATOR_VERSION = "rodilla-1.0"`
- `DATASET_SCHEMA_VERSION = "1.0"`

---

## Registro y selector

`00_APP/region_registry.py` declara explicitamente, en orden estable:

1. abdomen
2. lumbar
3. cervical
4. rodilla

El selector visible agrega:

- Rodilla

Abdomen sigue siendo la region por defecto. Al cambiar de region se mantiene la confirmacion si hay contenido no guardado.

---

## Aislamiento clinico

Rodilla conserva:

- evaluacion de menisco medial y lateral;
- ligamentos cruzados y colaterales;
- tendones cuadricipital y patelar;
- alineacion patelofemoral;
- cartilago patelofemoral y femorotibial;
- derrame y quiste de Baker;
- lesiones osteocondrales;
- impresion jerarquizada sin normales;
- condropatia en numeros romanos.

Rodilla no hereda:

- reglas cervicales de nomenclatura discal;
- prohibicion cervical de `receso lateral`;
- reglas lumbar de receso lateral;
- reglas de UH de abdomen;
- nervios obligatorios de mano-muneca;
- reglas de tobillo-pie.

---

## Indices patelofemorales

Los indices:

- `Insall-Salvati`
- `Caton-Deschamps`
- `TT-TG`
- `CDI`

se tratan como contenido contextual de rodilla, no como regla dura universal.

Comportamiento V1:

- no se exigen en una RM general;
- no bloquean Gold por ausencia;
- si el dictado los aporta, pueden conservarse en el informe/caso;
- cualquier activacion como regla dura requerira aprobacion y pruebas especificas.

---

## Persistencia

Los casos rodilla se guardan exclusivamente en:

```text
00_APP/casos_rodilla
00_APP/rodilla_dataset.jsonl
```

Cada registro incluye:

- `region = "rodilla"`
- `region_name = "Rodilla"`
- `origen`
- `modalidad`
- `proveedor`
- `modelo`
- `prompt_version = "rodilla-1.0"` salvo override regional
- `validator_version = "rodilla-1.0"`
- `dataset_schema_version`
- `case_status`
- `validacion_humana`
- `gold_standard`

No se mezclan datasets entre abdomen, lumbar, cervical y rodilla.

---

## Importador

El importador acepta:

```text
[REGION]: rodilla
```

El caso se valida con `validador_rodilla.py` y se persiste en rutas de rodilla.

Si falta region o se declara una region no habilitada, se rechaza con aviso claro. No se asume abdomen.

---

## Gold Standard

La politica Gold regional se conserva:

`gold_standard = true` solo si:

- `case_status == "validated"`;
- `validacion_humana == true`;
- `input` no esta vacio;
- `informe_final` no esta vacio;
- `dataset_schema_version` existe;
- no hay flags con `bloquea_gold == true`.

Los estados Gold son independientes entre las cuatro regiones.

---

## Riesgos pendientes

1. La app sigue usando estado regional global en un unico proceso Flask local.
2. La UI sigue embebida en `optimus_app.py`.
3. No se migran historicos.
4. No se integro mano-muneca, codo, tobillo-pie ni torax.
5. Los indices patelofemorales quedan documentados como contextuales, no automatizados.

