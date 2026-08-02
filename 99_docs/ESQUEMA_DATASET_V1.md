# ESQUEMA_DATASET_V1

**Proyecto:** OPTIMUS  
**Region inicial:** abdomen  
**Version de esquema:** `1.0`  
**Fecha:** 2026-07-18

---

## Objetivo

Definir el esquema comun para casos nuevos guardados por las fabricas regionales activas, tanto desde la interfaz local como desde el importador hospital-casa.

Este esquema no reescribe automaticamente casos historicos.

---

## Campos obligatorios

| Campo | Tipo | Valores permitidos / formato | Descripcion |
|---|---|---|---|
| `case_id` | string | `YYYYMMDD_HHMMSS` con sufijo opcional `_N` | Identificador estable del caso y base del nombre de archivo. |
| `timestamp` | string | ISO 8601 local, segundos | Momento de persistencia. |
| `dataset_schema_version` | string | `1.0` | Version del esquema de dataset. |
| `region` | string | `abdomen`, `lumbar`, `cervical`, `rodilla`, `mano_muneca`, `codo`, `tobillo_pie`, `torax` | Region anatomica del caso. |
| `region_name` | string | `Abdomen`, `Columna lumbar`, `Columna cervical`, `Rodilla`, `Mano y muñeca`, `Codo`, `Tobillo y pie`, `Tórax` | Nombre humano de la region activa. |
| `origen` | string | `app_local`, `importador_hospital` | Camino por el que entro el caso. |
| `modalidad` | string o null | null si no se infiere de forma fiable | Modalidad del estudio. No se inventa. |
| `input` | string | no vacio | Dictado bruto original enviado o importado. |
| `informe_ia` | string | puede estar vacio solo si no disponible | Informe producido por IA o informe importado como version inicial. |
| `correccion_radiologo` | string | puede ser vacio | Nota/correccion del radiologo. |
| `informe_final` | string | no deberia estar vacio | Informe final aceptado para dataset. |
| `explicacion` | string | puede ser vacio | Explicacion adicional separada de la correccion. |
| `proveedor` | string | `openai`, `anthropic`, `deepseek` o vacio si no disponible | Proveedor realmente usado para generar el informe. |
| `modelo` | string | nombre del modelo o vacio si no disponible | Modelo realmente usado para generar el informe. |
| `prompt_version` | string | inicialmente `abdomen-1.0` | Version del prompt usada por el caso. |
| `validator_version` | string | inicialmente `abdomen-1.0` | Version del validador usado. |
| `validacion_humana` | boolean | `true` / `false` | Confirmacion explicita de validacion humana. Inicialmente `false` salvo confirmacion explicita. |
| `fecha_validacion` | string | ISO 8601 o cadena vacia | Fecha/hora de la accion explicita de validacion humana. |
| `validated_by` | string | `radiologo` o cadena vacia | Rol que valido explicitamente el caso. |
| `tiene_correccion` | boolean | `true` / `false` | Indica si informe IA y final difieren o existe nota de correccion. |
| `case_status` | string | `draft`, `generated`, `corrected`, `validated`, `rejected`, `imported_pending` | Estado editorial/dataset del caso. |
| `gold_standard` | boolean | `true` / `false` | Derivado: solo true si hay estado `validated`, validacion humana, input e informe final no vacios, sin flags `bloquea_gold` y con version de esquema. |
| `flags` | array | lista de objetos `{regla, gravedad, mensaje, bloquea_gold}` | Resultado de validacion determinista sobre el informe final. |

---

## Campos opcionales

El esquema V1 no exige campos opcionales adicionales. Los lectores deben tolerar campos extra en registros historicos o futuros.

Campos historicos conocidos:

- `ts`
- `correccion`
- `hubo_correccion`
- `output`

No se escriben como esquema nuevo, pero se leen como compatibilidad.

---

## Ejemplo completo

```json
{
  "case_id": "20260718_223000",
  "timestamp": "2026-07-18T22:30:00",
  "dataset_schema_version": "1.0",
  "region": "abdomen",
  "region_name": "Abdomen",
  "origen": "app_local",
  "modalidad": null,
  "input": "dolor abdominal. estudio TC abdomen y pelvis...",
  "informe_ia": "Datos clínicos: dolor abdominal...",
  "correccion_radiologo": "Ajusté terminología de vía urinaria.",
  "informe_final": "Datos clínicos: dolor abdominal...",
  "explicacion": "",
  "proveedor": "openai",
  "modelo": "gpt-4.1-mini",
  "prompt_version": "abdomen-1.0",
  "validator_version": "abdomen-1.0",
  "validacion_humana": false,
  "fecha_validacion": "",
  "validated_by": "",
  "tiene_correccion": true,
  "case_status": "corrected",
  "gold_standard": false,
  "flags": []
}
```

---

## Reglas de escritura

1. `/guardar` rechaza `input` vacio o compuesto solo por espacios.
2. `/guardar` no crea Markdown, JSON ni JSONL si falla la validacion de entrada.
3. El importador hospital-casa usa la misma funcion de persistencia que `/guardar`.
4. JSON individual y JSONL escriben el mismo registro esencial.
5. No se inventa `modalidad`; queda `null` si no se infiere de forma fiable.
6. `proveedor` y `modelo` deben venir de la generacion realmente realizada o quedar vacios si el caso se importo sin esa informacion.
7. Los flags sin `bloquea_gold` explicito se normalizan como `false`.
8. El importador hospital-casa escribe `case_status = "imported_pending"`.
9. `gold_standard` no depende solo de `validacion_humana`; exige `case_status = "validated"`.

---

## Compatibilidad historica

Los casos antiguos no se migran automaticamente.

La lectura de `/caso/<id>` rellena valores por defecto cuando faltan campos nuevos:

- `case_id`: usa `ts` o el id solicitado.
- `timestamp`: usa `ts` o cadena vacia.
- `correccion_radiologo`: usa `correccion` si existe.
- `tiene_correccion`: usa `hubo_correccion` si existe.
- `region`: region activa.
- `region_name`: nombre de la region activa.
- `origen`: cadena vacia.
- `modalidad`: `null`.
- `proveedor`, `modelo`, `prompt_version`, `validator_version`, `dataset_schema_version`: cadena vacia.
- `validacion_humana`: `false`.
- `fecha_validacion`: cadena vacia.
- `validated_by`: cadena vacia.
- `case_status`: `draft`.
- `gold_standard`: `false`.

Incompatibilidad conocida: registros JSONL historicos pueden tener `output` en lugar de `informe_final`. La fase actual no reescribe esos registros; cualquier exportador futuro debe contemplar ambos nombres.
