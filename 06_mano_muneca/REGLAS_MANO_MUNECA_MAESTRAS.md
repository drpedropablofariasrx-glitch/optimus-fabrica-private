# REGLAS_MANO_MUNECA_MAESTRAS

**Origen:** hilo ChatGPT del proyecto MSK codo/muñeca/mano (~223 casos)
**Archivo fuente:** Muñeca-mano.txt (18.597 líneas)

**Total: 3 reglas duras (validador) + 4 blandas (prompt)**

> Nota: este corpus contiene la taxonomía estructurada más detallada de todas las regiones (severidad y cronicidad con listas cerradas explícitas). Es el proyecto donde más formalizaste los metadatos del dataset.

---

## ⚠️ Alcance: el proyecto original era 'codo/muñeca/mano'

El hilo cubre codo, muñeca y mano como una sola región MSK. Las reglas de nervios (B1/B2) son específicas de mano/muñeca. Si en la fábrica quieres separar 'codo' de 'mano-muñeca', ten en cuenta que comparten la mayoría de reglas de formato pero las reglas neurológicas (mediano/cubital, túnel carpiano/Guyon) son de mano-muñeca. Se documenta como una región combinada, que es como lo trabajaste.

Además, parte del hilo (desde L3975) se dedicó a **ecografía en inglés** — un contexto distinto (idioma y modalidad). Esas reglas NO se incluyen aquí porque pertenecen a otro flujo; si informas ecografía en inglés de forma habitual, sería una configuración aparte.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| D1 | No incluir edad ni sexo del paciente en la sección Hallazgos ni en el cuerpo del informe (esa información solo va al DATASET_ENTRY interno cuando esté disponible) | "En la sección HALLAZGOS: No incluiré edad ni sexo del paciente. Esa información solo se usará en el bloque DATASET_ENTRY" | L6300 |
| D2 | Taxonomía de severidad cerrada: leve, moderada, moderada-avanzada, avanzada. No usar otros términos de gradación | "Mantendré siempre la taxonomía de severidad: leve, moderada, moderada-avanzada, avanzada" | L6133 |
| D3 | Taxonomía de cronicidad cerrada: aguda, subaguda, crónica, degenerativa, postraumática, postquirúrgica | "Mantendré siempre la taxonomía de cronicidad: aguda, subaguda, crónica, degenerativa, postraumática, postquirúrgica" | L6134 |

## B. REGLAS BLANDAS → PROMPT

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| B1 | En TODOS los informes de mano, valorar explícitamente en Hallazgos el nervio mediano y el nervio cubital (aunque sean normales). Redacción estándar: 'Nervio mediano y nervio cubital de señal y morfología conservadas sin signos de neuropatía compresiva en el campo incluido en el estudio' | "en todos los informes de mano incluiré siempre en Hallazgos la valoración explícita de: Nervio mediano, Nervio cubital, aunque sean normales" | L6756 |
| B2 | Si el estudio incluye muñeca, valorar además explícitamente el túnel carpiano y el canal de Guyon | "Si el estudio incluye muñeca también se valorará: túnel carpiano, canal de Guyon" | L6772 |
| B3 | Incluir siempre interpretación global + análisis complementario destinado a mejorar la calidad del informe (mismo patrón que en abdomen) | "A partir de ahora quiero que incluyas siempre un análisis complementario destinado a mejorar la calidad del informe" | L2089 |
| B4 | Distinguir siempre entre hallazgos normales, patológicos e incidentales; jerarquizar hallazgo principal y secundarios; señalar discordancia clínico-radiológica si existe; expresar confianza diagnóstica cuando el hallazgo sea dudoso o limítrofe | "Distinguiré siempre entre hallazgos normales, patológicos e incidentales / Jerarquizaré hallazgo principal y secundarios / Señalaré discordancia clínico-radiológica / Expresaré la confianza diagnóstica cuando el hallazgo sea dudoso" | L6135 |

---

## Observaciones

- **B1/B2 (valoración obligatoria de nervios)** son las reglas de mayor valor clínico y las más específicas de esta región: garantizan que ningún informe de mano/muñeca omita la valoración neurológica (mediano/cubital, túnel carpiano/Guyon). Directamente comprobable por código: si el informe es de mano y no menciona el nervio mediano → aviso.
- **D2/D3 (taxonomías cerradas)** son reutilizables como estándar de proyecto para TODAS las regiones — la severidad y la cronicidad no deberían variar entre abdomen, columna y extremidades. Candidatas a ser reglas transversales comunes.
- **B3 (análisis de mejora)** coincide exactamente con la regla B1 de abdomen — confirma que es una regla transversal del proyecto, no específica de una región.