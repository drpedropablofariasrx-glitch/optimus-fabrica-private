# REGLAS_RODILLA_MAESTRAS

**Origen:** dos archivos (Rodilla.txt, Rodilla2.txt) — corpus más pequeño que las otras cuatro regiones, pero de naturaleza distinta y especialmente valiosa: contiene el **prompt de reglas original** que escribiste al inicio del proyecto completo, antes de abdomen/lumbar/cervical/tórax.
**Archivos fuente:** Rodilla.txt (2.091 líneas) + Rodilla2.txt (1.153 líneas)

**Total: 4 reglas duras (validador) + 6 blandas (prompt)**

---

## 📜 Nota histórica importante

Este corpus documenta el **origen de todo el proyecto**. En Rodilla2.txt (L2027-2031) está el mensaje original donde pediste 'casos representativos con input de mi informe y output del informe que realizas tú... para que Claude se haga cargo' — es, literalmente, el punto de partida de la conversación que ha producido las cuatro fábricas de región ya construidas.

También se documenta la **evolución del formato de salida**: el prompt original de rodilla (L551-557, L181-186) pedía SIEMPRE 5 bloques visibles — INFORME RADIOLOGICO, INTERPRETACION GLOBAL, ANALISIS ESTRUCTURADO DEL CASO, TAGS, DATASET_ENTRY. Esta fue la versión inicial. En los proyectos posteriores (lumbar, cervical, tórax) decidiste **simplificar a 2 bloques visibles** (informe + interpretación global), moviendo el análisis estructurado, tags y dataset a procesamiento interno no visible. Es decir: el formato correcto y vigente HOY es el simplificado, no el de 5 bloques que aparece en este corpus original. Al construir el prompt de rodilla para la fábrica, se usa el formato moderno (2 bloques), no el histórico.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| D1 | No incluir datos demográficos (edad, sexo, hospital) en el cuerpo del informe | "recuerda no poner los datos demograficos en el informe" | L139 |
| D2 | No usar viñetas en el informe radiológico; texto en prosa integrada | "No usar viñetas en el informe radiológico" | L563 |
| D3 | Grados de condropatía en números romanos (I, II, III, IV), no arábigos | "Usar grados de condropatía en números romanos" | L566 |
| D4 | En la impresión diagnóstica no incluir hallazgos normales (solo patología relevante) | "En la impresión diagnóstica no incluir hallazgos normales" | L565 |

## B. REGLAS BLANDAS → PROMPT

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| B1 | Terminología precisa de tipo de rotura meniscal; no citar 'Stoller' como referencia dentro del informe, usar el tipo de rotura directamente (horizontal, vertical, compleja, radial, en asa de cubo, etc.) | "Usar terminología precisa en menisco (tipo de rotura, no Stoller)" | L567 |
| B2 | Usar 'que condiciona' para expresar relaciones causa-efecto entre hallazgos | "Usar 'que condiciona' para relaciones causa-efecto" | L568 |
| B3 | Integrar los hallazgos en prosa fluida en vez de listarlos de forma aislada uno tras otro | "Integrar los hallazgos en vez de listarlos de forma aislada" | L569 |
| B4 | Cuando varias estructuras estén normales (ligamentos cruzados, colaterales, meniscos), consolidarlas en una sola frase conjunta en vez de describir cada una por separado | "para que no sea tan largo hablar de ligamento cruzado anterior y posterior, meniscos o colaterales de forma separada si ambos estan normales, mejor resumirlo asi" | L375 |
| B5 | No inventar datos clínicos no proporcionados en el dictado; no añadir recomendaciones clínicas no solicitadas | "No inventar datos que no estén en el caso original... No añadir recomendaciones clínicas" | L655 |
| B6 | [PENDIENTE DE FORMALIZAR — señalado por el radiólogo] Artefacto de movimiento declarado en los datos clínicos debe reflejarse explícitamente en el informe como limitación real; el diagnóstico diferencial (p.ej. lesión en rampa vs. rotura vertical periférica) debe matizarse cuando esa limitación aplique | "La presencia de artefacto de movimiento declarada en los datos clínicos debe reflejarse explícitamente en el informe como limitación real... [Pedro:] el prompt 3.0 no logro ponerlo en las reglas, creo que no cabe" | L984 |

---

## ⚠️ Regla B6 requiere tu decisión

Es la única regla de todo el corpus que tú mismo marcaste como no resuelta ('no logro ponerlo en las reglas, creo que no cabe'). Es clínicamente sólida — el artefacto de movimiento sí debe limitar la certeza diagnóstica declarada — pero no se aplicó formalmente en tu proyecto original. Queda aquí documentada para que decidas si la incorporas ahora al prompt de rodilla de la fábrica.

## Observaciones

- **D1 (sin datos demográficos)** coincide con el patrón general de discreción de identidad que ya aplicas en las demás regiones (D5 de abdomen, reglas de formato de lumbar/cervical/tórax).
- **B1 (no citar Stoller, usar tipo de rotura)** es una regla de estilo interesante y específica de MSK: prioriza la terminología descriptiva reproducible sobre la referencia bibliográfica dentro del informe clínico — la referencia queda para el conocimiento interno, no para el texto que ve el paciente/PACS.
- **B4 (consolidar estructuras normales)** es una regla de concisión que no había aparecido en las otras regiones con esta formulación explícita; vale la pena valorar si aplica también a abdomen/tórax (p.ej. 'bazo, páncreas y suprarrenales sin hallazgos' ya sigue este patrón implícitamente).
- Este corpus, a diferencia de los otros cuatro, no tiene un año de diálogo de corrección extenso — es más compacto porque documenta la fase de **diseño inicial** del proyecto, no un año de uso en producción. Es normal y esperable que tenga menos reglas.