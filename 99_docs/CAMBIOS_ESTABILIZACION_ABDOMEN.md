# CAMBIOS_ESTABILIZACION_ABDOMEN

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Alcance:** estabilizacion de abdomen antes del nucleo multirregion.

---

## Entorno Python

Antes de los cambios no existia entorno reproducible en el proyecto:

- no habia `requirements.txt`;
- no habia `.venv`;
- `python`, `py` y `pip` no estaban disponibles en PATH;
- el runtime empaquetado de Codex no tenia Flask instalado.

Se creo:

- `requirements.txt`
- `.venv` local del proyecto

Dependencias minimas declaradas:

```text
flask
openai
anthropic
```

La instalacion se realizo dentro de `.venv`, no globalmente.

---

## Resultado inicial real de pruebas

Tras crear `.venv` e instalar dependencias, antes de cambiar produccion:

```text
Ran 7 tests
FAILED (failures=1)
```

Resultado:

- 6 pruebas pasaban.
- 1 prueba fallaba.

Fallo detectado:

- `test_importacion_hospital_casa_usa_persistir_caso`
- causa: el parser de `[NOTAS]` no conservaba el contenido cuando el campo no tenia etiquetas posteriores. Se guardaba `Mejoras: ...`, pero se perdia `Notas: ...`.

---

## Cambios realizados

### 1. Preservacion del caso bruto

Se anadio estado minimo en JavaScript:

- `currentCaseInput`
- `currentProvider`
- `currentModel`

`generar()` guarda internamente el texto exacto enviado a `/generar` antes de limpiar el textarea visible.

`guardar()` envia `currentCaseInput`, no el contenido actual del textarea.

El estado se limpia despues de guardado exitoso o al pulsar nuevo caso.

### 2. Bloqueo de input vacio

`/guardar` rechaza input vacio o compuesto solo por espacios con HTTP 400.

Si falla, no crea:

- Markdown;
- JSON individual;
- entrada JSONL.

### 3. Persistencia unificada

`/guardar` usa ahora `_persistir_caso()`.

El importador hospital-casa tambien usa `_persistir_caso()`.

Se elimino la implementacion paralela de escritura dentro de `/guardar`.

### 4. Esquema dataset V1

Se anadieron constantes:

```python
PROMPT_VERSION = "abdomen-1.0"
VALIDATOR_VERSION = "abdomen-1.0"
DATASET_SCHEMA_VERSION = "1.0"
```

Los casos nuevos guardan:

- `case_id`
- `timestamp`
- `dataset_schema_version`
- `region`
- `origen`
- `modalidad`
- `input`
- `informe_ia`
- `correccion_radiologo`
- `informe_final`
- `explicacion`
- `proveedor`
- `modelo`
- `prompt_version`
- `validator_version`
- `validacion_humana`
- `tiene_correccion`
- `flags`

### 5. Compatibilidad historica

`/caso/<id>` tolera registros antiguos sin campos nuevos y rellena valores por defecto.

No se migran ni reescriben automaticamente casos historicos.

### 6. TAGS / DATASET_ENTRY visibles

Se anadio una comprobacion temporal en la validacion de salida para detectar:

- `TAGS`
- `TAGS / ETIQUETAS`
- `DATASET_ENTRY`
- `ANALISIS ESTRUCTURADO DEL CASO`

Produce flag:

```text
META_VISIBLE | alta
```

Y bloquea `/guardar` hasta que el usuario revise el informe.

No se borra ni modifica automaticamente el contenido del modelo.

### 7. Importador hospital-casa

Se corrigio el parser de campos finales para que `[NOTAS]` conserve su contenido aunque no tenga etiqueta posterior.

El importador guarda `origen = "importador_hospital"`.

---

## Resultado final de pruebas

Comando:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fabrica_abdomen_characterization
```

Resultado:

```text
............
----------------------------------------------------------------------
Ran 12 tests in 3.274s

OK
```

No quedo ninguna prueba omitida.

---

## Riesgos y decisiones pendientes

1. `requirements.txt` queda sin versiones fijadas porque no existia referencia previa. En una fase posterior conviene congelar versiones conocidas buenas.
2. `modalidad` queda `null` porque no se infiere de forma fiable sin reglas adicionales.
3. `validacion_humana` queda `false` salvo envio explicito; la UI todavia no tiene control visible para confirmarla.
4. El validador incrustado sigue existiendo; no se ha sustituido por el regional.
5. Los JSONL historicos pueden tener `output` en vez de `informe_final`; no se migraron.
6. El bloqueo `META_VISIBLE` es temporal en la app de abdomen; mas adelante deberia vivir en una regla comun o en el validador regional, segun se apruebe.
7. No se inicio arquitectura multirregion.

