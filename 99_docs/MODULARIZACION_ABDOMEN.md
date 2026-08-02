# MODULARIZACION_ABDOMEN

**Proyecto:** OPTIMUS  
**Region:** abdomen  
**Fecha:** 2026-07-18  
**Estado:** modularizacion controlada sin arquitectura multirregion.

---

## Que se extrajo

### SYSTEM_PROMPT

El prompt clinico de abdomen se extrajo desde `00_APP/fabrica_abdomen.py` a:

```text
01_abdomen/SYSTEM_PROMPT_abdomen.txt
```

El contenido corresponde a `PROMPT_VERSION = "abdomen-1.0"` y se extrajo sin cambios clinicos deliberados:

- no se resumieron reglas;
- no se fusionaron reglas;
- no se cambio el orden;
- no se cambio el formato visible esperado.

Si el archivo falta o esta vacio, la aplicacion aborta con un error claro.

### Configuracion regional

Se creo:

```text
01_abdomen/region_config.py
```

Contiene configuracion simple:

- `REGION_ID`
- `REGION_NAME`
- `PROMPT_PATH`
- `VALIDATOR_MODULE`
- `CASES_DIR`
- `DATASET_PATH`
- `PROMPT_VERSION`
- `VALIDATOR_VERSION`
- `DATASET_SCHEMA_VERSION`

No se crearon clases, plugins, selector regional ni `core/`.

### Validador

La fuente unica de verdad del validador de abdomen es:

```text
01_abdomen/validador_abdomen.py
```

La app lo carga explicitamente mediante `region_config.py` y convierte sus objetos `Flag` a diccionarios para mantener intacta la interfaz JSON actual.

Si la carga falla, la app muestra error claro y no continua con un validador parcial.

---

## Que sigue dentro de `fabrica_abdomen.py`

Sigue dentro de la app:

- servidor Flask;
- rutas publicas actuales;
- HTML/CSS/JS embebido;
- clientes OpenAI/Anthropic/DeepSeek;
- configuracion editable del prompt en runtime;
- guardado de casos;
- importador hospital-casa;
- bandeja de reglas candidatas;
- capa temporal `META_VISIBLE` para bloquear metainformacion interna visible.

No se modificaron:

- puerto;
- rutas Flask publicas;
- flujo visible de generacion;
- formato visible del informe;
- interfaz salvo el control minimo de validacion humana.

---

## Fuente unica del prompt

La fuente inicial del prompt de abdomen es:

```text
01_abdomen/SYSTEM_PROMPT_abdomen.txt
```

La version `abdomen-1.0` documenta el contenido actual extraido. La configuracion editable existente puede seguir cambiando `SYSTEM_PROMPT` en runtime como antes, pero la base modular de abdomen ya no vive incrustada como literal clinico dentro de la app.

---

## Fuente unica del validador

La app ya no ejecuta la copia compacta del validador.

El validador regional activo es:

```text
01_abdomen/validador_abdomen.py
```

Esto activa reglas que antes estaban documentadas pero no ejecutadas por la app compacta:

- D2: porcentajes con simbolo `%`.
- D6: impresion diagnostica en lineas independientes cuando el bloque es largo.
- D7: pie `Informado por / Validado por` condicionado a formato chileno.
- D11: coherencia de realce verdadero por diferencia de UH entre fases.

---

## Diferencias esperadas al activar el validador regional

El formato visible del informe no cambia, pero el control de calidad puede mostrar avisos nuevos.

Posibles falsos positivos nuevos:

- D2 puede marcar "por ciento" aunque el texto sea una cita o contexto no cuantitativo.
- D6 puede marcar una impresion larga que clinicamente sea aceptable en parrafo unico.
- D7 puede depender de si los marcadores chilenos aparecen de forma incompleta.
- D11 puede fallar por proximidad textual imperfecta entre fases y UH.

Se mantiene la filosofia: el validador avisa, no corrige.

---

## Gold Standard

Se anadio un control minimo visible:

```text
Validar como Gold Standard
```

Por defecto:

```text
validacion_humana = false
gold_standard = false
```

Solo una accion explicita del usuario marca:

- `validacion_humana = true`
- `fecha_validacion = <ISO timestamp>`
- `validated_by = "radiologo"`

`gold_standard` se calcula de forma derivada y solo es true si:

- `validacion_humana = true`;
- `case_status = "validated"`;
- `input` no esta vacio;
- `informe_final` no esta vacio;
- no hay flags con `bloquea_gold = true`;
- `dataset_schema_version` esta presente.

Los casos no Gold se conservan igualmente como borradores, corregidos no validados, rechazados o importados pendientes.

---

## Invalidacion tras editar

Si el usuario edita el informe despues de pulsar `Validar como Gold Standard`, la UI ejecuta automaticamente:

- `validacion_humana = false`
- `fecha_validacion = ""`
- `validated_by = ""`

No se infiere Gold Standard por tener correccion. La validacion es una accion humana explicita.

---

## Riesgos pendientes

1. La configuracion editable del prompt sigue existiendo para preservar comportamiento actual; en una fase posterior habra que decidir si los cambios aprobados se sincronizan al archivo regional.
2. La capa `META_VISIBLE` todavia vive en la app, no en el validador regional ni en un nucleo comun.
3. No se migran historicos automaticamente.
4. El resto de regiones todavia no consume configuracion modular.
5. No existe selector regional, `core/`, SQLite, FastAPI ni integracion multirregion.
