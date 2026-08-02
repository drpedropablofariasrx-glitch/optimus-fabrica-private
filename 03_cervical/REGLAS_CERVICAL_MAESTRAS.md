# REGLAS_CERVICAL_MAESTRAS

**Origen:** hilo único ChatGPT de RM columna cervical (~51 casos, corpus más reciente/pequeño que abdomen y lumbar)
**Archivo fuente:** RM_cervical.txt (9.086 líneas)
**Método:** idéntico al usado en abdomen y lumbar

**Total: 3 reglas duras (validador) + 4 blandas (prompt)**

---

## ✅ Corrección aplicada: el pie NO es una diferencia regional, es una regla universal

Se corrigió tras aclaración del radiólogo: el pie 'Informado por/Validado por' no depende de la región (lumbar vs. cervical), depende de si el informe tiene **formato clínico chileno**. Se aplicó la misma corrección a abdomen, lumbar, cervical y tórax.

## ⚠️ Diferencia real que SÍ es regional: 'receso lateral'

Esta sigue siendo una diferencia genuina entre regiones (razón anatómica, no de formato administrativo):

| Región | 'Receso lateral' |
|--------|-------------------|
| Lumbar | Se usa (terminología estándar; existe compartimento anatómico real) |
| Cervical | **NO se usa** — no existe ese compartimento en cervical (L8479-8492) |

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| D1 | Datos administrativos con formato completo (identificación, previsión, etc.): limpiar a 'Datos clínicos' sin ruido administrativo; NO incluir datos demográficos en el cuerpo. Pie 'Informado por/Validado por' — regla UNIVERSAL: incluir SOLO si hay formato clínico chileno (FONASA/ID paciente/RUT). **Corregido:** no es "siempre en cervical", es condicional; este caso concreto sí tenía formato chileno, por eso se veía como "siempre" | "al final de la impresión diagnóstica añadiré siempre: Informado por Dr Pedro Farias Lisboa / Validado por:" (caso con formato chileno) | L1197 |
| D2 | No usar el término 'receso lateral' en columna cervical: anatómicamente no existe ahí un compartimento equivalente al de la columna lumbar (a diferencia de lumbar, donde sí se usa) | "No utilizaría de forma rutinaria el término 'receso lateral' en columna cervical... no existe un compartimento diferenciado como en la columna lumbar" | L8483 |
| D3 | Nomenclatura de localización de hernias discales cervicales limitada a: Central / Paracentral / Paracentral-foraminal / Foraminal / Extraforaminal (con lateralidad). No usar 'posterolateral' de forma rutinaria | "No utilizar de forma rutinaria el término 'posterolateral', por ser menos preciso anatómicamente y menos reproducible" | L8941 |

## B. REGLAS BLANDAS → PROMPT

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| B1 | Separar siempre dos conceptos en la descripción de una hernia cervical: (1) localización de la hernia (central/paracentral/paracentral-foraminal/foraminal/extraforaminal) y (2) repercusión anatómica (estenosis de canal central, deformidad medular, mielopatía, estenosis foraminal) | "Separar siempre dos conceptos: 1. LOCALIZACIÓN DE LA HERNIA... 2. REPERCUSIÓN ANATÓMICA" | L8945 |
| B2 | Estilo 'top limpio': evitar 'simétrico' cuando no aporta valor clínico; eliminar frases como 'sin otros hallazgos a destacar' cuando ya está implícito; preferir concordancia gramatical directa | "Evitas 'simétrico' (no aporta valor clínico aquí) / Eliminado 'Sin otros hallazgos a destacar', ya está implícito" | L3027 |
| B3 | Workflow de validación: no generar el DATASET TRAINING ENTRY hasta que el radiólogo indique explícitamente 'mi corrección', 'validado' o 'no tengo correcciones'; solo esa versión confirmada pasa a ser Gold Standard | "Cuando diga 'mi corrección', 'no tengo correcciones', 'validado' o similar, esa versión pasa a ser Gold Standard" | L8195 |
| B4 | El razonamiento interno (interpretación global, análisis estructurado, extracción de datos, etiquetas, correlación clínico-radiológica, jerarquización) se realiza pero no se muestra; solo se entrega el informe (datos clínicos, exploración, hallazgos, impresión) y, cuando aporte valor, el análisis de calidad/oportunidades de mejora | "puedo realizar internamente: interpretación global, análisis estructurado, extracción de datos... Y mostrarte únicamente: INFORME RADIOLOGICO" | L6969 |

---

## Observaciones

- **D3/B1 (nomenclatura de hernias cervicales)** es la regla de mayor valor de este corpus: estandariza localización + repercusión anatómica como dos ejes separados, con lista cerrada de términos. Es directamente comprobable por código (si aparece 'posterolateral' → aviso).
- **B3 (gating del dataset)** ya está resuelto en tu fábrica actual: el sistema ya captura input/informe-IA/corrección y solo trata como 'con corrección' cuando hay diferencia o nota — es el mismo principio que tú mismo describes aquí, ya construido.
- El corpus es más pequeño (51 casos vs. 159 de lumbar y 237 de abdomen) — es esperable menos reglas. No implica peor calidad; el hilo es más reciente.