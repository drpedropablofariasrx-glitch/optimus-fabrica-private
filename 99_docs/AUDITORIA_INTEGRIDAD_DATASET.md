# AUDITORIA_INTEGRIDAD_DATASET

**Proyecto:** OPTIMUS  
**Alcance:** `00_APP/fabrica_abdomen.py`  
**Fecha:** 2026-07-18  
**Estado:** auditoria previa a refactorizacion. No se han corregido archivos de produccion.

---

## Resumen ejecutivo

La aplicacion actual funciona como fabrica local de abdomen, pero el flujo de guardado tiene un riesgo real de perdida de integridad del dataset: despues de generar un informe, el frontend borra el campo visible del caso bruto y despues usa ese mismo campo vacio para llamar a `/guardar`.

Esto permite que un caso se guarde con:

- `input` vacio en el JSON individual;
- `input` vacio en `abdomen_dataset.jsonl`;
- informe IA y final presentes, pero sin dictado bruto trazable.

Ademas, existen dos caminos de persistencia con esquemas diferentes:

- `/guardar`, usado por el flujo normal local;
- `_persistir_caso()`, usado por el importador hospital-casa.

El importador conserva `region` y `origen`; el guardado normal no.

---

## A. Campo de caso bruto vacio tras generar

### Evidencia

En el frontend, `generar()` lee el caso desde `#caso`, lo manda a `/generar` y acto seguido borra el textarea:

`00_APP/fabrica_abdomen.py`, funcion JS `generar()`:

```js
const caso=$('caso').value.trim();
...
$('caso').value='';
...
body:JSON.stringify({...cfg(),caso})
```

Despues, `guardar()` construye el payload usando de nuevo el valor actual del textarea:

```js
const payload={...cfg(),caso:$('caso').value,informe_ia:informeIA,informe_final:inf.innerText,correccion:...}
```

### Impacto

Si el usuario genera un informe y pulsa guardar sin volver a pegar el caso bruto, `/guardar` recibe `caso: ""`.

El backend no valida que `caso` tenga contenido:

```python
caso = data.get("caso","")
```

Por tanto se puede persistir un caso sin input original.

### Severidad

Alta para integridad del dataset. No afecta necesariamente al informe clinico visible, pero si contamina el dataset de entrenamiento y rompe trazabilidad.

### Recomendacion

Guardar el caso bruto en estado de frontend, por ejemplo `casoActual`, cuando se genera el informe, y usar ese valor en `guardar()`. En backend, rechazar `/guardar` si `caso` esta vacio salvo importacion explicita documentada.

---

## B. Diferencias entre `/guardar` y `_persistir_caso()`

### `/guardar`

Guarda:

```python
registro = {
    "input": caso,
    "informe_ia": informe_ia,
    "informe_final": informe_final,
    "correccion": correccion,
    "hubo_correccion": hubo_correccion,
    "ts": ts,
    "flags": flags,
}
```

JSONL:

```python
{
    "input": caso,
    "output": informe_final,
    "informe_ia": informe_ia,
    "correccion": correccion,
    "ts": ts,
    "flags": flags
}
```

No guarda `region` ni `origen`.

### `_persistir_caso()`

Guarda:

```python
registro = {
    "input": caso,
    "informe_ia": informe_ia,
    "informe_final": informe_final,
    "correccion": correccion,
    "hubo_correccion": hubo_correccion,
    "region": region,
    "origen": origen,
    "ts": ts,
    "flags": flags
}
```

JSONL:

```python
{
    "input": caso,
    "output": informe_final,
    "informe_ia": informe_ia,
    "correccion": correccion,
    "region": region,
    "origen": origen,
    "ts": ts,
    "flags": flags
}
```

### Diferencias relevantes

| Campo | `/guardar` JSON | `/guardar` JSONL | `_persistir_caso()` JSON | `_persistir_caso()` JSONL |
|---|---:|---:|---:|---:|
| `input` | si | si | si | si |
| `informe_ia` | si | si | si | si |
| `informe_final` | si | no, se llama `output` | si | no, se llama `output` |
| `output` | no | si | no | si |
| `correccion` | si | si | si | si |
| `hubo_correccion` | si | no | si | no |
| `region` | no | no | si | si |
| `origen` | no | no | si | si |
| `ts` | si | si | si | si |
| `flags` | si | si | si | si |

### Impacto

El dataset mezcla registros con y sin `region`/`origen` segun el camino de entrada. En una futura fabrica multirregion esto impedira filtrar de forma fiable por region y procedencia.

### Recomendacion

Unificar todo guardado, incluido `/guardar`, a traves de una unica funcion de persistencia. No cambiar aun el formato clinico ni los validadores.

---

## C. Diferencias de esquema entre JSON individual, JSONL e importador

### JSON individual del flujo local

Fuente: `/guardar`.

Campos actuales:

- `input`
- `informe_ia`
- `informe_final`
- `correccion`
- `hubo_correccion`
- `ts`
- `flags`

### JSONL del flujo local

Fuente: `/guardar`.

Campos actuales:

- `input`
- `output`
- `informe_ia`
- `correccion`
- `ts`
- `flags`

Pierde `hubo_correccion`, `region` y `origen`.

### JSON individual del importador hospital-casa

Fuente: `_persistir_caso()`.

Campos actuales:

- `input`
- `informe_ia`
- `informe_final`
- `correccion`
- `hubo_correccion`
- `region`
- `origen`
- `ts`
- `flags`

### JSONL del importador hospital-casa

Fuente: `_persistir_caso()`.

Campos actuales:

- `input`
- `output`
- `informe_ia`
- `correccion`
- `region`
- `origen`
- `ts`
- `flags`

### Observacion sobre importacion

En `/importar`, el informe importado se persiste como `informe_ia == informe_final == informe`. Esto es razonable si el informe ya fue corregido en el hospital, pero semanticamente no distingue entre:

- informe generado por IA;
- informe final validado por radiologo;
- informe importado sin version IA original.

Recomendacion: conservar este comportamiento por ahora, pero anadir `origen: "hospital"` y en una fase posterior un campo como `modo_ingesta: "importado_final"` o `informe_ia_disponible: false`.

---

## D. Campos actualmente no guardados

### `region`

- Presente en importador.
- Ausente en guardado normal.

Debe guardarse siempre. En la fase abdomen puede ser constante: `"abdomen"`.

### `origen`

- Presente en importador como `"hospital"`.
- Ausente en guardado normal.

Debe guardarse siempre. En guardado normal puede ser `"local"`.

### `proveedor`

El frontend envia `provider` dentro de `cfg()`, y `/guardar` lo usa solo para proponer reglas candidatas. No queda persistido en JSON ni JSONL.

Debe guardarse para auditoria del dataset: OpenAI, Anthropic, DeepSeek, etc.

### `modelo`

El frontend envia `model`, y `/guardar` lo usa solo para proponer reglas candidatas. No queda persistido en JSON ni JSONL.

Debe guardarse porque el rendimiento y el estilo dependen del modelo.

### `prompt_version`

Existe version en `APP_CONFIG["version"]`, pero no se persiste por caso.

Debe guardarse por caso. Si un informe fue generado con prompt v3 y otro con v7, el dataset debe saberlo.

### `validator_version`

No existe campo ni constante.

Debe crearse antes de entrenar o comparar datasets. Al inicio podria ser manual, por ejemplo `abdomen_validator_v1`.

---

## Reglas candidatas

El flujo de reglas candidatas se activa en `/guardar` cuando:

- `hubo_correccion` es verdadero;
- hay API key disponible;
- `proponer_regla_desde_correccion()` devuelve un JSON interpretable.

La candidata guarda:

- `ts`
- `tipo`
- `categoria`
- `regla`
- `motivo`
- `estado`

No guarda:

- `case_id` explicito separado de `ts`;
- `region`;
- `proveedor`;
- `modelo`;
- version de prompt que produjo el informe;
- diff completo entre informe IA e informe final.

Recomendacion: no cambiar aun la logica, pero cuando se estabilice persistencia, vincular cada candidata al registro de caso y a la version de prompt/modelo.

---

## TAGS / DATASET_ENTRY visibles

La app no elimina automaticamente `TAGS` ni `DATASET_ENTRY` si aparecen en el informe devuelto por el LLM.

La funcion `copiarInforme()` copia `innerText` del informe visible. No filtra secciones internas.

El validador compacto incrustado tampoco tiene una regla para detectar `TAGS` o `DATASET_ENTRY`.

### Impacto

Si el modelo devuelve metainformacion interna, puede quedar:

- visible en la interfaz;
- copiada al PACS;
- guardada en Markdown;
- guardada en JSON;
- guardada en JSONL.

### Recomendacion

Primero decidir politica:

1. bloquear guardado si aparecen marcadores internos;
2. advertir con flag de validador;
3. filtrar para copia al PACS pero guardar el texto bruto en auditoria.

La opcion mas segura para fase actual: flag de alta/media gravedad y no correccion automatica.

---

## Prioridad de correccion recomendada

1. Conservar `caso` en frontend tras generar y usarlo en `/guardar`.
2. Validar en backend que `/guardar` no acepte `input` vacio.
3. Unificar `/guardar` y `_persistir_caso()`.
4. Guardar siempre `region` y `origen`.
5. Guardar `proveedor`, `modelo`, `prompt_version` y `validator_version`.
6. Anadir regla/flag para `TAGS` y `DATASET_ENTRY` visibles.
7. Normalizar esquema JSON individual vs JSONL.

