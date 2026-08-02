# POLITICA_BLOQUEOS_GOLD

**Proyecto:** OPTIMUS  
**Region activa:** abdomen  
**Fecha:** 2026-07-18  
**Estado:** politica V1.

---

## Objetivo

Separar avisos de calidad de bloqueos para Gold Standard.

Un flag puede advertir sin impedir que el caso sea Gold. Para eso cada flag nuevo expone:

```json
{
  "regla": "D11",
  "gravedad": "media",
  "mensaje": "...",
  "bloquea_gold": false
}
```

Si el validador regional no declara `bloquea_gold`, la app asume `false`.

---

## Condiciones para Gold Standard

`gold_standard` solo puede ser `true` si se cumplen todas:

1. `case_status == "validated"`
2. `validacion_humana == true`
3. `input` no esta vacio
4. `informe_final` no esta vacio
5. `dataset_schema_version` esta presente
6. Ningun flag tiene `bloquea_gold == true`

La validacion humana es una accion explicita del radiologo. No se infiere por haber guardado o corregido un caso.

---

## Bloqueos Gold en abdomen V1

Bloquean Gold:

- `INPUT_EMPTY`: caso bruto vacio.
- `FINAL_EMPTY`: informe final vacio.
- `META_VISIBLE`: presencia visible de `TAGS`, `DATASET_ENTRY`, `ETIQUETAS` o analisis interno.
- Error interno del validador detectado en el mensaje del flag.
- Incoherencias clinico-cuantitativas criticas marcadas por el validador con gravedad alta:
  - `D8`
  - `D9`
  - `D10`
  - `D11`
  - `D12`

No bloquean por defecto:

- avisos de estilo;
- recomendaciones blandas;
- flags de gravedad baja o media sin `bloquea_gold`;
- diferencias editoriales que el radiologo valida explicitamente.

---

## Estados de caso

Los estados permitidos son:

| Estado | Significado |
|---|---|
| `draft` | Caso aun no generado o reiniciado en UI. |
| `generated` | Informe generado por IA y pendiente de guardado/validacion. |
| `corrected` | Informe editado o guardado con diferencia/nota. |
| `validated` | Validacion humana explicita para Gold. |
| `rejected` | Caso rechazado explicitamente. |
| `imported_pending` | Caso importado desde hospital-casa pendiente de revision local. |

Transiciones actuales:

- generar informe: `generated`
- editar informe: `corrected`
- validar como Gold Standard: `validated`
- importar hospital-casa: `imported_pending`
- rechazar explicitamente por payload: `rejected`

---

## Riesgo controlado

La politica no cambia criterios clinicos del validador. Solo anade una capa de decision de dataset para impedir que casos incompletos, contaminados por metadatos o con incoherencias criticas entren como Gold Standard.

