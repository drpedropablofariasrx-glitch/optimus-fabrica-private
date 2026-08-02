# POLITICA_VERSIONADO_PROMPTS

**Proyecto:** OPTIMUS  
**Region activa:** abdomen  
**Fecha:** 2026-07-18  
**Estado:** politica V1 para estabilizacion previa a multirregion.

---

## Principio

El prompt clinico versionado no debe modificarse automaticamente desde la app.

Para abdomen, la fuente base es:

```text
01_abdomen/SYSTEM_PROMPT_abdomen.txt
```

Ese archivo representa `PROMPT_VERSION = "abdomen-1.0"`.

La configuracion local:

```text
00_APP/fabrica_config.json
```

solo puede contener borradores u overrides aprobados. No reemplaza al archivo base.

---

## Tres conceptos obligatorios

| Concepto | Origen | Persistencia | Uso |
|---|---|---|---|
| `prompt_base` | `SYSTEM_PROMPT_abdomen.txt` | versionado en la region | Verdad base estable. |
| `prompt_override` | `fabrica_config.json` | local/runtime | Cambio aprobado por el radiologo sin tocar el base. |
| `prompt_efectivo` | derivado | no se escribe como fuente canonica | Prompt usado para generar informes. |

Regla de resolucion:

```text
prompt_efectivo = prompt_override aprobado si existe; si no, prompt_base
```

---

## Acciones permitidas

### Guardar borrador

Guarda una propuesta en `prompt_draft`.

- No cambia `SYSTEM_PROMPT`.
- No cambia `prompt_efectivo`.
- No cambia la version efectiva usada por informes.
- Registra evento con fecha, usuario, version origen, version destino, diff y motivo.

### Aplicar override

Convierte una propuesta o borrador en `prompt_override`.

- No modifica `SYSTEM_PROMPT_abdomen.txt`.
- Cambia `prompt_efectivo`.
- Actualiza `prompt_version` a una version trazable:

```text
abdomen-1.0+override.N
```

- Guarda una copia del prompt efectivo anterior en `00_APP/historial_prompts/`.
- Registra evento con `usuario = "radiologo"`.

### Restaurar base

Elimina el override local.

- Vuelve a usar `prompt_base`.
- Cambia `prompt_version` efectiva a `abdomen-1.0`.
- Registra evento con diff entre override y base.

---

## Trazabilidad minima

Cada evento de prompt conserva:

- `fecha`
- `usuario`: siempre `radiologo` en esta fase
- `accion`: `guardar_borrador`, `aplicar_override`, `restaurar_base`
- `version_origen`
- `version_destino`
- `diff`
- `motivo`

Los casos nuevos guardan el `prompt_version` efectivo en el momento de persistencia.

---

## Restricciones

1. La app no escribe sobre `01_abdomen/SYSTEM_PROMPT_abdomen.txt`.
2. Los borradores no son fuente clinica activa.
3. Un override aprobado es local y trazable, no una nueva version base regional.
4. La promocion de un override a nuevo prompt base queda fuera de esta fase.

