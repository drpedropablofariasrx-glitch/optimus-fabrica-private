# REGLAS_TORAX_MAESTRAS

**Origen:** hilo único ChatGPT de TC de tórax (predominantemente, con valoración conjunta torácica-abdominal-pélvica) — ~93 casos, principalmente informes con formato clínico chileno (FONASA)
**Archivo fuente:** Torax.txt (7.576 líneas)
**Nota de alcance:** este hilo contiene casi exclusivamente TC de tórax (260 menciones de TC vs 17 de RM; 894 de tórax/pulmón vs 1 de cerebro). Los casos de RM cerebro/neuro que mencionas deben venir de otro hilo — si los tienes, se procesan aparte como región 'neuro', no mezclados aquí.

**Total: 4 reglas duras (validador) + 3 blandas (prompt)**

---

## ✅ Esta es la regla universal correcta (confirmada por el radiólogo)

Lo que en abdomen/lumbar/cervical parecían comportamientos distintos por región eran en realidad la MISMA regla condicional observada en hilos con distinta mezcla de casos (formato chileno vs. no chileno). La regla real, aplicada ahora a las cuatro regiones: incluir el pie **si y solo si** el informe tiene formato clínico chileno (FONASA, ID paciente, previsión, RUT), independientemente de la región anatómica.

## 🔗 Este corpus SE APOYA en las reglas de abdomen ya extraídas

La regla B1 lo dice explícitamente: cuando un TC de tórax incluye cortes de abdomen superior, esos hallazgos se revisan **según las normas del proyecto abdominal** — es decir, las 31 reglas de `REGLAS_ABDOMEN_MAESTRAS.md` no son exclusivas de esa fábrica: se reutilizan aquí. Esto es una señal arquitectónica real: al generalizar a multi-región, conviene que 'tórax' pueda *heredar o consultar* las reglas de abdomen para hallazgos abdominales incidentales, en vez de duplicarlas.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| D1 | No incluir el título del estudio dentro del informe (p.ej. 'TC DE TÓRAX SIN CONTRASTE', 'ANGIO-TC DE ARTERIAS PULMONARES') | "A partir de ahora no pondré el título del estudio (por ejemplo, 'TC DE TÓRAX SIN CONTRASTE'...)" | L7501 |
| D2 | No incluir líneas de proceso interno / QA en el cuerpo del informe (p.ej. 'Checklist de calidad torácico aplicado y validado') | "Checklist de calidad torácico aplicado y validado no pongas esto en el informe" | L48 |
| D3 | TEP — índice VD/VI (ventrículo derecho/izquierdo): >0.9 = sospecha de sobrecarga derecha y mayor mortalidad; <1 aprox. normal. Referencia: Emergency Radiology – The Requisites (2017) | "Right ventricle enlargement is suspected with CT when the ratio of the right to left ventricular diameters exceed 0.9" | L414 |
| D4 | Pie 'Informado por Dr. Pedro Farias Lisboa / Validado por:' — incluir SOLO cuando el informe tiene formato clínico chileno (ID paciente, nombre, edad/sexo, FONASA, mayúsculas tipo RIS); NO incluir en borradores, docencia, o corrección parcial | "Cuando el informe incluya ID paciente/Nombre/Edad-sexo/FONASA/mayúsculas RIS -> asumo informe clínico formal para Chile -> termina con Informado por/Validado por. No añadir si es borrador/docencia/corrección parcial" | L5691 |

## B. REGLAS BLANDAS → PROMPT

| ID | Regla | Cita | Línea |
|----|-------|------|-------|
| B1 | Valoración simultánea torácica + abdominal + pélvica cuando el estudio combinado lo incluya, sin repetir contexto: si hay masa pulmonar, valorar hígado/suprarrenales/retroperitoneo; si hay hallazgo abdominal inflamatorio, valorar correlato torácico (atelectasias, derrame, trombos en cava); los cortes de abdomen superior incluidos en un TC de tórax se revisan conforme a las normas del proyecto de abdomen | "hago valoración simultánea torácica + abdominal + pélvica... si la exploración es torácica pero incluyes cortes de abdomen superior, los reviso conforme a normas del proyecto abdominal" | L524 |
| B2 | Cribado de cáncer pulmonar: cuando aplique, clasificar según categoría Lung-RADS y confirmar elegibilidad/periodicidad del programa de cribado | "Si este paciente pertenece a programa tipo Lung-RADS, sería clasificado como categoría 1 (negativo). Es conveniente confirmar elegibilidad" | L183 |
| B3 | Plantillas estándar guardadas como macro base: PieloTC sin contraste negativo para urolitiasis (adaptar solo datos variables); frase estándar fija para AngioTC de TEP negativo | "guarda esto como informe standard... utilizaré este texto como macro base, adaptando solo los datos variables" | L2957 |

---

## Observaciones

- **D3 (VD/VI en TEP)** es la regla de mayor valor clínico: umbral numérico con respaldo bibliográfico explícito citado en tu propio hilo. Comprobación directa por código: si el informe menciona sobrecarga/hipertensión pulmonar en contexto de TEP, verificar coherencia con el valor VD/VI si está consignado.
- **D4** es la regla más compleja de las tres corpus analizados hasta ahora: no es un simple sí/no, sino una detección de contexto (¿es esto un informe clínico formal chileno?) que determina el comportamiento. El validador puede aproximarlo detectando marcadores de formato chileno (FONASA, ID Paciente, mayúsculas RIS) y comprobando consistencia con la presencia/ausencia del pie.
- **D1/D2** son ambas del tipo 'fuga de metainformación al informe final' — el modelo mete en el cuerpo algo que no debería (título del estudio, línea de checklist interno). Mismo patrón de riesgo que los TAGS/DATASET_ENTRY visibles que se corrigieron en lumbar.