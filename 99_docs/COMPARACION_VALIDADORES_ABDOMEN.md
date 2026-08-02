# COMPARACION_VALIDADORES_ABDOMEN

**Proyecto:** OPTIMUS  
**Alcance:** comparacion entre validador compacto incrustado y `01_abdomen/validador_abdomen.py`  
**Fecha:** 2026-07-18  
**Estado:** auditoria. No se ha eliminado ni modificado ningun validador.

---

## Fuentes comparadas

1. Validador compacto incrustado en `00_APP/fabrica_abdomen.py`, funcion `validar()`.
2. Validador regional completo en `01_abdomen/validador_abdomen.py`.

El validador incrustado devuelve diccionarios:

```python
{"regla": "...", "gravedad": "...", "mensaje": "..."}
```

El validador regional devuelve objetos `Flag`:

```python
Flag(regla, gravedad, mensaje, fragmento)
```

Esta diferencia de tipo es relevante para integracion futura.

---

## Reglas presentes en ambos

| Regla | Descripcion | Incrustado | Regional |
|---|---|---:|---:|
| D1 | Numeros en palabras junto a unidades | si | si |
| D3 | Mayusculas sostenidas en Datos clinicos | si | si |
| D4 | Evitar "se realiza / se le realiza" en Datos clinicos | si | si |
| D8 | Coherencia esteatosis hepatica vs UH higado/bazo | si | si |
| D9 | Lipoma debe tener densidad grasa | si | si |
| D10 | No diagnosticar lipomatosis pancreatica con 40-60 UH | si | si |
| D12 | Aorta: aneurisma >=30 mm; normal <25 mm no ectasia/aneurisma | si | si |

---

## Reglas presentes solo en el validador regional

| Regla | Descripcion | Riesgo si la app usa solo el incrustado |
|---|---|---|
| D2 | Porcentajes con simbolo `%`; detectar "por ciento" | No se avisa de formato porcentual incorrecto. |
| D6 | Impresion diagnostica en bloque largo; separar ideas por lineas | La app puede aceptar impresiones largas en parrafo unico. |
| D7 | Pie `Informado por / Validado por` condicionado a formato clinico chileno | La app no controla presencia/ausencia del pie. |
| D11 | Realce verdadero: diferencia entre fases <10 UH = sin realce | La app no detecta incoherencias de realce aunque el prompt lo exija. |

---

## Reglas ausentes en ambos validadores

Estas reglas aparecen como criterio o formato en el prompt/reglas, pero no estan implementadas de forma determinista:

- No mostrar `TAGS` ni `DATASET_ENTRY`.
- No incluir datos demograficos/hospital fuera de contexto.
- No usar vinetas en impresion, salvo inferencia parcial por D6.
- No repetir medidas en impresion diagnostica.
- Sistemas de clasificacion como Bosniak/O-RADS/LI-RADS/Fleischner/TNM, salvo por instrucciones blandas.
- D5 de abdomen: organos no mencionados se asumen normales. El propio validador regional aclara que no es verificable solo con el output.

---

## Diferencias de comportamiento

### Tipo de salida

El incrustado retorna `dict`; el regional retorna `Flag`.

Impacto: la API Flask actual serializa sin problemas el incrustado. Si se sustituye por el regional, habra que convertir `Flag` a dict antes de responder JSON.

### Cobertura

El incrustado es una copia compacta y menos completa. Omite D2, D6, D7 y D11.

Impacto: la app actual no ejecuta todas las reglas duras de abdomen documentadas.

### Mensajes y fragmentos

El regional incluye `fragmento`, util para trazabilidad humana. El incrustado no.

Impacto: la UI actual muestra mensajes mas simples, pero pierde contexto del disparo.

### D1: numeros en palabras

El regional incluye mas palabras numericas (`cero`, `uno`, `cien`, `ciento`, `mil`) y una heuristica adicional para "por ... mil/cent". El incrustado empieza en `dos` y es mas corto.

Impacto: el incrustado tiene mas falsos negativos.

### D8: negaciones de esteatosis

Ambos intentan distinguir afirmacion de negacion. El regional contempla tambien `no esteatosis` y `sin\s+esteatosis`; el incrustado no contempla todas las variantes.

Impacto: el incrustado puede tener mas falsos positivos o falsos negativos ante negaciones no literales.

### D11: realce

El prompt incrustado exige diferencia >=10 UH para realce verdadero, pero el validador incrustado no lo comprueba. El regional si.

Impacto: incoherencia critica entre prompt y control de calidad visible en la app.

---

## Posibles falsos positivos

### D1 numeros en palabras

Puede marcar palabras numericas si aparecen cerca de unidades sin ser medida real. Riesgo aceptable si la gravedad se mantiene media/baja.

### D3 mayusculas

Puede marcar siglas no incluidas en `SIGLAS_OK`. Recomendacion: ampliar lista con casos reales, no relajar regla completa.

### D6 impresion en bloque

Puede marcar una impresion larga correctamente redactada como parrafo. Mantener baja gravedad.

### D7 pie chileno

Puede fallar si el formato chileno no contiene los marcadores detectados (`FONASA`, `ID paciente`, `prevision`, `RUT`) o si aparecen esos terminos en otro contexto.

### D8 esteatosis

Riesgo por negaciones complejas: "no debe afirmarse esteatosis", "descartar esteatosis", "sin criterios concluyentes de esteatosis". Ya se habia documentado como bug D8 en el estado del proyecto.

### D11 realce

Puede inferir fases por proximidad textual de forma imperfecta. Mantener media gravedad.

---

## Fuente unica de verdad recomendada

La fuente unica de verdad debe ser:

`01_abdomen/validador_abdomen.py`

Motivos:

1. Es el validador regional documentado.
2. Tiene mayor cobertura.
3. Mantiene trazabilidad con `Flag.fragmento`.
4. Es coherente con la futura arquitectura multirregion.
5. Evita divergencia entre app y carpeta regional.

La app deberia importar o cargar ese validador y convertir sus `Flag` a dict para la API.

No se recomienda seguir editando el validador incrustado salvo como parche temporal, porque consolida la duplicacion.

---

## Orden recomendado para estabilizar

1. Crear pruebas que documenten el comportamiento actual del validador incrustado.
2. Crear pruebas equivalentes contra `01_abdomen/validador_abdomen.py`.
3. Confirmar con casos clinicos reales los cambios de cobertura: D2, D6, D7, D11.
4. Cambiar la app para usar el validador regional como fuente unica.
5. Mantener adaptador de serializacion `Flag -> dict`.
6. Eliminar el validador incrustado solo cuando las pruebas de caracterizacion pasen.

