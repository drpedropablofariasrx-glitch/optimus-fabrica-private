# CORRECCION_CONTAMINACION_LUMBAR

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-18  
**Region afectada:** lumbar  
**Estado:** corregido sin activar reglas en rodilla.

---

## Motivo

Se detecto contaminacion patelofemoral dentro de la region lumbar. Los terminos retirados fueron:

- `Insall-Salvati`
- `Caton-Deschamps`
- `TT-TG`
- `CDI`

Estos parametros corresponden a mediciones de rodilla/patelofemorales, no a columna lumbar.

---

## Lineas retiradas

Lineas detectadas antes de la correccion:

| Archivo | Linea original | Accion |
|---|---:|---|
| `02_lumbar/SYSTEM_PROMPT_lumbar.txt` | 16 | Eliminada la regla dura sobre indices cuantitativos patelofemorales. |
| `02_lumbar/validador_lumbar.py` | 115 | Eliminada la regla `regla_D3` que validaba esos indices. |
| `02_lumbar/REGLAS_LUMBAR_MAESTRAS.md` | 19 | Eliminada la fila D3 de reglas duras. |

Tambien se ajustaron textos derivados:

- `validador_lumbar.py`: descripcion de 4 a 3 reglas duras.
- `validador_lumbar.py`: `TODAS_LAS_REGLAS` ya no incluye la antigua `regla_D3`.
- `REGLAS_LUMBAR_MAESTRAS.md`: total de reglas duras actualizado de 4 a 3.

---

## Comprobacion

Se ejecuto busqueda textual sobre lumbar y rodilla:

```text
rg -n "Insall|Salvati|Caton|Deschamps|TT-TG|TTTG|TT TG|CDI" 02_lumbar 05_rodilla
```

Resultado: no quedan coincidencias en los archivos actuales revisados.

---

## Rodilla

No se activo ninguna regla nueva en rodilla durante esta fase.

Si en una fase posterior se decide incorporar indices patelofemorales, debe hacerse dentro de la fase propia de rodilla, con pruebas y versionado regional de rodilla.

---

## Pruebas

Se agregaron pruebas que aseguran:

- esos terminos no forman parte de prompt, validador ni reglas maestras lumbar;
- un informe lumbar que mencione esos terminos no dispara validacion lumbar por indices patelofemorales;
- `receso lateral` sigue siendo aceptado como terminologia lumbar.

