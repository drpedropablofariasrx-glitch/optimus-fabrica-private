# REGLAS_LUMBAR_MAESTRAS

**Origen:** hilo único ChatGPT de RM columna lumbar (~1 año, ~159 casos)
**Archivo fuente:** Columna_lumbar.txt (19.789 líneas)
**Método:** idéntico al usado en abdomen — extracción de instrucciones explícitas + correcciones implícitas, con trazabilidad a línea original

**Total: 3 reglas duras (validador) + 9 blandas (prompt)**

> Nota de calidad: este corpus contiene reglas de contención diagnóstica más sofisticadas que las de abdomen — en particular B3/B4 (espondiloartropatías) son reglas de razonamiento clínico condicional, no solo de formato. Alto valor.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| D1 | Medidas de protrusión/hernia con 2 dimensiones sin ejes especificados: asumir por defecto (transverso × anteroposterior); indicarlo entre paréntesis | "cuando aportes medidas... con dos dimensiones y no especifiques los ejes, asumiré por defecto (diámetro transverso × diámetro anteroposterior)" | L11935 |
| D2 | Pie 'Informado por Dr. ... / Validado por:' — regla UNIVERSAL: incluir SOLO si el informe tiene formato clínico chileno (FONASA/ID paciente/RUT). **Corregido:** no es "nunca en columna", es condicional; en este hilo los casos no llevaban formato chileno, por eso se observó como "nunca" | "A partir de ahora aplicaré esta regla: no incluiré al final Informado por / Validado por" (casos de este hilo sin formato chileno) | L18491 |
| D4 | Formato de entrega fijo: bloque de informe completo para copiar a PACS + interpretación global fuera del bloque, sin análisis estructurado visible, sin TAGS, sin DATASET_ENTRY en el cuerpo visible | "A partir de ahora el formato será: informe en bloque de texto + interpretación global fuera + sin análisis estructurado + sin TAGS + sin DATASET_ENTRY" | L12560 |

## B. REGLAS BLANDAS → PROMPT

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| B1 | Regla de jerarquía disco/faceta según haya o no estenosis: si HAY estenosis → 'abombamiento + hipertrofia facetaria que condicionan estenosis' (disco protagonista). Si NO hay estenosis → disco primero, faceta como acompañante. Si hay edema facetario → la faceta pasa a protagonista | "¿Hay estenosis? -> abombamiento+hipertrofia que condicionan / ¿No hay estenosis? -> disco primero, faceta acompañante / ¿Hay edema facetario? -> faceta protagonista" | L3358 |
| B2 | En la impresión diagnóstica: no repetir mecanismos degenerativos (abombamiento, osteofitos, hipertrofia facetaria) salvo que aporten información clínica relevante; priorizar la repercusión anatómica (estenosis, contacto radicular, compresión medular) | "No repetir los mecanismos degenerativos salvo que aporten información clínica relevante. Priorizar la repercusión anatómica" | L16368 |
| B3 | No afirmar automáticamente 'artropatía facetaria degenerativa' ante edema facetario en paciente con espondiloartropatía conocida (psoriásica, anquilosante, reactiva); describir como hallazgo inespecífico | "No deberíamos afirmar directamente que se trata de artropatía facetaria degenerativa... el edema perifacetario puede verse en artropatía inflamatoria por espondiloartritis" | L17734 |
| B4 | En estudios para descartar espondiloartritis axial: aplicar sistemáticamente evaluación por criterios ASAS (edema de médula ósea subcondral, erosiones, metaplasia grasa, esclerosis, puentes óseos, anquilosis, lesiones de Romanus/Andersson) | "En todos los estudios solicitados para descartar espondiloartritis axial debe aplicarse sistemáticamente una evaluación basada en criterios ASAS" | L18125 |
| B5 | No añadir de forma rutinaria 'raíces de la cauda equina sin alteraciones significativas' en informes normales; reservar la mención para cuando exista patología relevante en ese territorio | "En informes normales no aporta demasiado añadir siempre 'raíces de la cauda equina sin alteraciones significativas'. Lo reservaría para cuando exista patología" | L16354 |
| B6 | Quistes de Tarlov y otros hallazgos incidentales: consignarlos al final de la impresión diagnóstica, sin competir con la patología degenerativa principal | "Muy bien dejarlos al final de la impresión. Son un hallazgo incidental y no deben competir con la patología degenerativa principal" | L16360 |
| B7 | Añadir correlación clínica siempre que exista discordancia entre hallazgos radiológicos y clínica referida | "Mejora clave -> añadir correlación clínica siempre que haya discordancia" | L3490 |
| B8 | Homogeneizar terminología de estenosis entre hallazgos e impresión: 'estenosis foraminal' en el cuerpo de hallazgos (más directo); 'estenosis lateroforaminal' en la impresión diagnóstica | "prefiero tu cambio de 'estenosis foraminal' en hallazgos... mantener 'estenosis lateroforaminal' en la impresión, para homogeneizar el lenguaje del proyecto" | L18252 |
| B9 | Especificar siempre la lateralidad de protrusiones/hernias cuando el dictado bruto la mencione, incluso si es fácil de omitir en la redacción final | "la más importante es haber especificado la lateralidad izquierda en L4-L5, ya que el informe bruto hablaba de una protrusión sin especificarlo claramente" | L18250 |

---

## Observaciones sobre este corpus frente al de abdomen

- **B1 (regla disco/faceta condicional)** es la pieza más valiosa de todo el corpus: es una regla de *razonamiento*, no de formato. Decide qué estructura es 'protagonista' de la frase según haya o no estenosis/edema. Candidata ideal para ir también al validador como chequeo de coherencia (si hay estenosis mencionada, ¿la redacción sigue el patrón esperado?).
- **B3/B4 (espondiloartropatías)** son reglas de contención diagnóstica de alto valor clínico: evitan el sobre-diagnóstico de 'degenerativo' cuando el contexto clínico sugiere inflamatorio. Mismo patrón que la regla de pancreatitis aguda en abdomen (no afirmar sin contexto clínico que lo sostenga).
- La regla retirada sobre indices patelofemorales queda fuera de lumbar; si procede, debe evaluarse en la fase propia de rodilla.
- El corpus muestra que el propio flujo de trabajo fue cambiando de opinión sobre el formato de entrega (con TAGS/DATASET_ENTRY visible → sin ellos, ver D4). Se documenta la versión final, que es la vigente.

## Siguiente paso sugerido

Las 3 reglas duras son la especificación directa de un `validador_lumbar.py`, calcado en estructura a `validador_abdomen.py` pero con estas reglas. Las 9 blandas van al `SYSTEM_PROMPT` de lumbar. Con esto, la fábrica queda lista para generalizarse a multi-región añadiendo 'lumbar' como configuración.
