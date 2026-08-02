# REGLAS_CODO_MAESTRAS

**Origen:** corpus histórico `Codo.txt`, compuesto por dictados, informes corregidos y
preferencias repetidas del proyecto MSK codo/antebrazo.

**Objetivo:** separar reglas comprobables por código de reglas de razonamiento y estilo.
El validador no corrige el informe; únicamente emite avisos trazables.

**Total inicial:** 5 reglas duras + 4 reglas blandas comprobables, además de reglas clínicas
de razonamiento incluidas en el SYSTEM_PROMPT.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla |
|---|---|
| D1 | No incluir edad, sexo, hospital ni datos administrativos en el cuerpo del informe. |
| D2 | No mostrar `TAGS`, `DATASET_ENTRY` ni contenido interno dentro del informe PACS. |
| D3 | Evitar la redundancia “epicondilitis ... con tendinosis ...”. Usar el diagnóstico clínico o la descripción estructural, sin duplicar ambos conceptos. |
| D4 | Si se diagnostica rotura completa del bíceps distal, debe describirse la retracción proximal. |
| D5 | No afirmar evolución, estabilidad, progresión o mejoría cuando se declara que no existen estudios previos comparables. |

---

## B. REGLAS BLANDAS COMPROBABLES → VALIDADOR / PROMPT

| ID | Regla |
|---|---|
| B1 | En RM de codo, valorar de forma explícita los nervios cubital, mediano y radial. |
| B2 | Realizar checklist tendinoso mínimo: conjunto extensor, conjunto flexor, bíceps distal y tríceps. |
| B3 | Si existen artefactos de movimiento o escasa colaboración, declarar la limitación diagnóstica. |
| B4 | En estudios bilaterales, separar los hallazgos de codo derecho e izquierdo y jerarquizar la asimetría. |

---

## C. REGLAS CLÍNICAS Y DE REDACCIÓN → SYSTEM PROMPT

### C1. Jerarquización de la patología dominante
La impresión debe priorizar la lesión de mayor relevancia clínica. La artrosis avanzada,
una rotura tendinosa, una insuficiencia ligamentaria o una neuropatía sintomática no deben
quedar subordinadas a una tendinosis leve incidental.

### C2. Tendón conjunto extensor
- Describir engrosamiento, heterogeneidad de señal y rotura cuando exista.
- Preferir “tendinosis del tendón conjunto extensor” frente a repetir simultáneamente
  “epicondilitis” y “tendinosis”.
- En casos avanzados, revisar el complejo ligamentario lateral.

### C3. Bíceps distal
En rotura completa revisar:
- retracción y unidad de medida;
- localización del cabo;
- edema muscular;
- infiltración grasa;
- signos de cronicidad.

### C4. Tríceps y contexto postquirúrgico
En pacientes intervenidos distinguir:
- fibrosis;
- material quirúrgico residual;
- pequeños focos de mineralización;
- osificación;
- recidiva verdadera.

No afirmar recurrencia de entesofito o calcificación si no existe correlato actual.

### C5. Nervios
Valorar siempre cubital, mediano y radial. En síntomas mediales o irradiados, prestar
especial atención al nervio cubital en el canal epitrocleo-olecraniano.

### C6. Estudios evolutivos
Sin comparación previa no puede afirmarse evolución real. Debe expresarse la limitación
comparativa.

### C7. Estudios bilaterales
Separar ambos codos y destacar la asimetría relevante.

### C8. Impresión diagnóstica
- Solo patología relevante.
- No repetir hallazgos normales.
- Líneas independientes.
- Evitar recomendaciones terapéuticas no solicitadas.

---

## D. CHECKLIST DE RM DE CODO

1. Congruencia articular, derrame y lesiones osteocondrales.
2. Edema óseo, fractura o contusión.
3. Tendón conjunto extensor.
4. Tendón conjunto flexor.
5. Bíceps distal.
6. Tríceps distal y bursa olecraniana.
7. Complejo colateral medial.
8. Complejo colateral lateral.
9. Nervios cubital, mediano y radial.
10. Vientres musculares y partes blandas.
11. Cambios postquirúrgicos, si procede.

---

## Observaciones de implementación

- El archivo ejecutable es `validador_codo.py`.
- Las reglas de checklist son avisos de baja o media gravedad porque un campo de visión
  limitado puede justificar omisiones.
- Antes de endurecer nuevas reglas deben validarse contra casos reales para evitar
  falsos positivos.
