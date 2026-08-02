# REGISTRO_REGIONAL_V1

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Estado:** preparacion multirregion minima. Historico: inicialmente solo abdomen; fases posteriores habilitan lumbar, cervical, rodilla y mano-muneca.

**Actualizacion 2026-07-19:** codo queda habilitado como sexta region, despues de mano_muneca. El orden estable es abdomen, lumbar, cervical, rodilla, mano_muneca y codo.

**Actualizacion 2026-07-19 (tobillo-pie):** tobillo_pie queda habilitada como septima region. El orden estable es abdomen, lumbar, cervical, rodilla, mano_muneca, codo y tobillo_pie.

**Actualizacion 2026-07-20 (torax):** torax queda habilitada como octava region desde su ubicacion canonica `04_torax`. El orden estable es abdomen, lumbar, cervical, rodilla, mano_muneca, codo, tobillo_pie y torax.

---

## Objetivo

Introducir un registro regional explicito sin crear plataforma multirregion todavia.

No se anade selector visible, `core/`, FastAPI, SQLite, plugins ni integracion de las ocho regiones.

---

## Archivo creado

```text
00_APP/region_registry.py
```

Define un diccionario explicito:

```python
REGIONS = {
    "abdomen": {
        "config_module": "<ruta>/01_abdomen/region_config.py",
        "enabled": True,
    }
}
```

No hay autodiscovery. A fecha de esta actualizacion, las regiones habilitadas en orden estable son abdomen, lumbar, cervical, rodilla y mano_muneca. Las regiones futuras deberan declararse de forma consciente.

---

## API minima

| Funcion | Responsabilidad |
|---|---|
| `list_regions()` | Lista regiones registradas y si estan habilitadas. |
| `get_region_config(region_id)` | Carga el `region_config.py` de una region habilitada. |
| `load_region_prompt(region_id)` | Carga el prompt base regional. |
| `load_region_validator(region_id)` | Carga el validador regional y exige funcion `validar()`. |

---

## Region activa

La app mantiene:

```python
current_region = "abdomen"
```

La ejecucion no cambia:

```text
python 00_APP/fabrica_abdomen.py
```

No existe selector regional visible. El registro solo desacopla internamente rutas y componentes.

---

## Componentes que ahora salen de `region_config`

Para abdomen, `01_abdomen/region_config.py` gobierna:

- `PROMPT_PATH`
- `VALIDATOR_MODULE`
- `CASES_DIR`
- `DATASET_PATH`
- `PROMPT_CONFIG_PATH`
- `PROMPT_HISTORY_DIR`
- `CANDIDATES_PATH`
- `PROMPT_VERSION`
- `VALIDATOR_VERSION`
- `DATASET_SCHEMA_VERSION`

La app usa estos valores para guardado, JSONL, historial de prompts, reglas candidatas, carga de prompt y carga de validador.

---

## Elementos que siguen regionales

Permanecen en abdomen:

- prompt clinico;
- validador clinico;
- versiones de prompt y validador;
- carpeta de casos;
- dataset JSONL;
- reglas candidatas;
- configuracion local de prompt.

---

## Elementos aun no generalizados

Siguen dentro de `00_APP/fabrica_abdomen.py` por decision de fase:

- interfaz Flask local;
- HTML/CSS/JS embebido;
- rutas publicas;
- clientes de proveedores LLM;
- importador hospital-casa;
- capa `META_VISIBLE`;
- mensajes visibles con terminologia de abdomen;
- plantilla de captura de abdomen.

Estos elementos pueden moverse a comun en fases posteriores, pero hacerlo ahora aumentaria el alcance sin necesidad.

---

## Como se anade una futura region

En una fase posterior, una nueva region deberia agregarse con estos pasos minimos:

1. Crear carpeta regional con `SYSTEM_PROMPT_<region>.txt`, `validador_<region>.py` y `region_config.py`.
2. Declarar la region en `REGIONS` con `enabled = False` durante preparacion.
3. Verificar que `region_config.py` expone rutas y versiones equivalentes a abdomen.
4. Crear pruebas de carga de prompt, validador, rutas y persistencia.
5. Cambiar `enabled = True` solo cuando la region tenga caracterizacion propia.

No debe haber autodiscovery ni activacion implicita.

---

## Prompt base, override y efectivo

El registro carga el prompt base regional desde `PROMPT_PATH`.

La app conserva tres niveles:

- `prompt_base`: archivo regional versionado.
- `prompt_override`: cambio aprobado en `fabrica_config.json`.
- `prompt_efectivo`: override aprobado si existe; si no, base.

Los borradores no cambian el prompt efectivo. Aplicar override cambia la version efectiva de forma trazable, por ejemplo:

```text
abdomen-1.0+override.1
```

Restaurar base elimina el override efectivo y vuelve a `abdomen-1.0`.

---

## Bloqueos Gold

Los flags normalizados incluyen:

```text
bloquea_gold
```

El valor por defecto es `false` para mantener compatibilidad con validadores existentes.

`gold_standard` no mira solo la gravedad. Solo se bloquea cuando un flag declara `bloquea_gold = true` o cuando la app detecta condiciones estructurales bloqueantes, como input vacio, informe final vacio o metainformacion visible.

---

## `case_status`

Cada caso nuevo guarda un estado explicito:

- `draft`
- `generated`
- `corrected`
- `validated`
- `rejected`
- `imported_pending`

Solo `validated` puede producir `gold_standard = true`, y aun asi debe cumplir validacion humana, esquema presente, input/final no vacios y ausencia de flags bloqueantes.

---

## Criterios de aceptacion V1

1. Solo abdomen esta habilitado.
2. El arranque sigue siendo el mismo.
3. La interfaz visible no cambia a multirregion.
4. La app carga prompt y validador desde el registro.
5. Las rutas de almacenamiento salen de `region_config`.
6. Las pruebas automatizadas documentan el comportamiento.
