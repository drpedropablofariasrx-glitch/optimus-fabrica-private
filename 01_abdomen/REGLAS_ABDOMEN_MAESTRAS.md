# REGLAS_ABDOMEN_MAESTRAS

**Documento consolidado** — todas las reglas extraídas del hilo ChatGPT de TC abdomen-pelvis (~1 año), capa 1 (explícitas) + capa 2 (implícitas), unificadas y agrupadas por función.

**Fuente:** Abdomen_y_pelvis.txt (18.619 líneas) · **Trazabilidad:** cada regla cita la línea original · **Capa:** 1 = la dictaste explícitamente; 2 = surge de una corrección tuya

**Total: 12 reglas duras (validador) + 19 blandas (prompt) + 5 plantillas-modelo**

> Las reglas duras D1, D2, D3, D6 coinciden con MSK_REGLAS_MAESTRAS_UNICAS.md → transversales a todas las regiones. El resto son específicas de abdomen/urogenital.

---

## A. REGLAS DURAS → VALIDADOR (comprobables por código)

### A.1 Formato y sintaxis
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| D1 | Números en formato numérico, nunca en palabras (44 mm, no 'cuarenta y cuatro') | "los números no en palabras sino por ejemplo (44 mm)" | L313 | 1 |
| D2 | Porcentajes con símbolo %; medidas siempre con unidad explícita mm o cm | "los porcentajes... usa el simbolo de porcentaje... mm o cm" | L509 | 1 |
| D3 | Datos clínicos en minúsculas: normalizar las mayúsculas del dictado | "cambiar las letras mayusculas que puedan aparecer en los datos clinicos a minusculas" | L11087 | 1 |
| D4 | No incluir la coletilla 'el paciente se realiza TC...' en Datos clínicos (es contexto del estudio, no dato clínico) | "no agregar en los datos clinicos de el paciente se realiza..." | L6589 | 1 |
| D5 | Órganos/sistemas no mencionados por el dictado se asumen normales y se redactan como normales | "los hallazgos que no he puesto, asumelos como normales" | L1606 | 1 |
| D6 | Separar cada idea/hallazgo en línea independiente | "las ideas separadas en distintas lineas" | L313 | 1 |
| D7 | Pie 'Informado por Dr. ... / Validado por:' — regla UNIVERSAL (misma en todas las regiones): incluir SI Y SOLO SI el informe tiene formato clínico chileno (FONASA/ID paciente/RUT/mayúsculas administrativas). Corregido tras aclaración del radiólogo — no es "cuando se indique" caso a caso, es una detección automática de contexto | "recuerda el informado por Validado por cuando lo pongo" (dictado siguiente en formato chileno mayúsculas) | L6452 | 1 |

### A.2 Umbrales cuantitativos (UH / mm) — núcleo del validador radiológico
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| D8 | Esteatosis hepática (TC): hígado <40 UH, o hígado >=10 UH menor que bazo. Si hígado > bazo -> NO esteatosis; no afirmarla sin dato objetivo | "higado mas denso que bazo -> NO esteatosis" | L12640 | 2 |
| D9 | Lipoma (TC): atenuación grasa -120 a -30 UH. ~3 UH NO es lipoma (es líquido simple) | "una densidad de 3.2 UH no es compatible con lipoma" | L8484 | 2 |
| D10 | Páncreas lipomatoso: 40-60 UH es parénquima normal; no diagnosticar lipomatosis en rango normal | "una densidad de 50 UH sin contraste NO es lipomatosis" | L11143 | 2 |
| D11 | Realce verdadero por fases: diferencia <10 UH entre fases = ausencia de realce | "una diferencia <10 UH entre fases se considera ausencia de realce verdadero" | L915 | 2 |
| D12 | Aorta abdominal infrarrenal: normal <30 mm, ectasia 25-29 mm, aneurisma >=30 mm; diámetros límite en mujer pueden ser normales | "aorta abdominal: normal <30, ectasia 25-29, aneurisma >=30" | L16827 | 2 |

---

## B. REGLAS BLANDAS → PROMPT / SISTEMA (requieren criterio clínico)

### B.1 Estructura de salida
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| B1 | Tras cada informe añadir SIEMPRE: análisis global del caso + análisis de oportunidades de mejora | "realizar siempre un analisis... / recuerda siempre dar el analisis global y de oportunidades de mejora" | L113 | 1 |
| B17 | Checklist fijo del análisis de mejora: ¿falta estructura según indicación? ¿hallazgo infra/sobreinterpretado? ¿terminología precisa (Bosniak/O-RADS/LI-RADS/Fleischner/TNM)? ¿cuantificar mejor? ¿recomendación de seguimiento? ¿inconsistencias internas? | "revisare sistematicamente: falta estructura / infra-sobreinterpretado / terminologia precisa / cuantificar / seguimiento / inconsistencias" | L18322 | 2 |

### B.2 Redacción y estilo
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| B3 | Separar cada idea en línea independiente (criterio de redacción) | "las ideas separadas en distintas lineas" | L313 | 1 |
| B8 | Hallazgos sin correlación con la clínica: declararlo explícito ('sin hallazgos estructurales que justifiquen la clínica referida') | "'Sin hallazgos estructurales que justifiquen la clinica referida'" | L85 | 1 |
| B10 | No usar términos obsoletos ('sombras renales'); sustituir por valoración objetiva (contornos de psoas, ausencia de calcificaciones urinarias) | "no usar 'sombras renales' y sustituirlo por una frase mas util y objetiva" | L1290 | 2 |
| B11 | Hallazgos no relacionados anatómicamente se redactan como independientes; no encadenar lesiones sugiriendo relación inexistente | "la lesion anexial derecha no esta en contacto con los cambios perianexiales... eventos independientes" | L8068 | 2 |
| B12 | Uso correcto de 'se identifica/se observa': afirmativo solo cuando el hallazgo está presente | "me refiero al 'se'... si que se identifica" | L4868 | 2 |

### B.3 Contención diagnóstica (no sobreinterpretar)
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| B2 | No mencionar 'sin signos de pancreatitis aguda' salvo dolor agudo, sospecha dirigida o protocolo urgente | "como este caso no trata de patologia aguda no creo recomendable poner pancreatitis aguda" | L116 | 1 |
| B19 | Densidad suprarrenal 10-15 UH en estudio CON contraste: no cerrar adenoma; sugerir TC sin contraste o RM | "densidad >10-15 UH en estudio con contraste para diagnostico con certeza" | L138 | 1 |
| B4 | Septos quísticos renales ~3 mm (no <2 mm): no es Bosniak II; clasificar Bosniak IIF (control evolutivo) | "los septos de 3 mm... excluye Bosniak II... la categoria segura es IIF" | L204 | 1 |
| B5 | No usar O-RADS en TC; describir la lesión y recomendar caracterización (eco TV / RM) | "No pongas 'O-RADS 5 en TC'... describir y recomendar caracterizacion" | L14294 | 1 |
| B14 | No aplicar clasificaciones de RM/eco (O-RADS) en TC; describir agresividad en lenguaje llano y derivar a técnica adecuada | "no necesitas O-RADS para saber que esto no es banal" | L14322 | 2 |
| B16 | Diámetros vasculares en límite alto en mujer: no es imprescindible etiquetar 'ectasia'; consignar como límites altos de normalidad | "esos diametros... limites altos de la normalidad para una mujer, no imprescindible llamarlos ectasia" | L16862 | 2 |
| B18 | Nódulo pulmonar en contexto de neoplasia (p.ej. colorrectal): considerar potencialmente metastásico hasta demostrar lo contrario; priorizar en impresión | "el nodulo pulmonar debe considerarse potencialmente metastasico hasta demostrar lo contrario" | L10786 | 2 |

### B.4 Valoración sistemática y cuantificación
| ID | Regla | Cómo la dictaste/corregiste | Línea | Capa |
|----|-------|------------------------------|-------|------|
| B6 | Valorar y consignar esteatosis hepática por atenuación siempre; incluir valoración hepática | "recuerda incorporar esta valoracion siempre (esteatosis por UH)" | L12205 | 1 |
| B13 | Valorar SIEMPRE el hígado de forma extendida y, según clínica, ampliar la estructura más relevante (p.ej. riñones/vía urinaria en cólico) | "valoracion mas extendida siempre del higado y segun datos clinicos la estructura relevante" | L17351 | 2 |
| B7 | En litiasis: consignar densidad UH del cálculo (orienta dureza y planificación urológica) | "densidad de 950 UH sugiere calculo relativamente duro... util para tratamiento" | L18519 | 1 |
| B9 | Graduar obstrucción urinaria con terminología precisa (hidronefrosis/ureteropielocaliectasia grado II), no 'ectasia grado II' | "precisaria hidronefrosis grado II o ureteropielocaliectasia grado II" | L18524 | 1 |
| B15 | Lesión hepática en mujer joven: RM con contraste hepatoespecífico (Gd-EOB-DTPA) es pieza clave antes de plantear biopsia | "en lesion hepatica en mujer joven... falta pieza critica si no hay RM con hepatobiliar" | L14035 | 2 |

---

## C. PLANTILLAS-MODELO (informes de referencia a extraer a KNOWLEDGE_BASE)

| Plantilla | Línea |
|-----------|-------|
| TC abdomen-pelvis: orden y redacción estándar definitivo | L6909 |
| TC tórax-abdomen-pelvis: control oncológico cáncer de colon operado | L7008 |
| Pielo-TC sin contraste normal | L7085 |
| Ecografía abdominal / abdominopélvica | L14519 |
| Pielonefritis / litiasis (modelo de referencia) | L17453 |

---

## NOTA SOBRE SOLAPAMIENTOS

- **B3 / D6** (separar ideas en líneas): aparece como dura (formato verificable) y como blanda (criterio de redacción). Para el validador cuenta D6; B3 queda como recordatorio de estilo.
- **B5 / B14** (O-RADS en TC): dos formulaciones de la misma regla, extraídas de momentos distintos del hilo. Se mantienen ambas por trazabilidad; en el prompt se unifican en una.
- **B6 / B13** (valorar hígado/esteatosis siempre): complementarias — B6 fija el qué (esteatosis por UH), B13 el alcance (valoración hepática extendida + estructura relevante según clínica).

## SIGUIENTE PASO

Las 12 reglas duras de la sección A son la especificación directa del validador en Python. Las 5 de A.2 (umbrales UH/mm) son las de mayor valor: permiten detectar contradicción entre un diagnóstico y las cifras que el propio informe contiene.