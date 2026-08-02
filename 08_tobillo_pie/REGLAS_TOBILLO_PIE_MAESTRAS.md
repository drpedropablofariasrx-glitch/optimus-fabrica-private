# REGLAS_TOBILLO_PIE_MAESTRAS

**Origen:** corpus histórico `Tobillo-pie.txt`, con dictados, correcciones, consultas
anatómicas y preferencias acumuladas del proyecto MSK de tobillo, retropié, mediopié,
pie y antepié.

**Objetivo:** separar las reglas deterministas del validador y las reglas clínicas y de
estilo del SYSTEM_PROMPT.

**Total inicial:** 5 reglas duras + 5 reglas blandas comprobables, además de reglas clínicas
y checklists específicos por subregión.

---

## A. REGLAS DURAS → VALIDADOR

| ID | Regla |
|---|---|
| D1 | No incluir edad, sexo, hospital ni datos administrativos en el cuerpo del informe. |
| D2 | No usar “distensión bursátil”; usar “distensión de la bursa intermetatarsiana”. |
| D3 | Expresar la causalidad como “os trigonum con signos de pinzamiento posterior”, no al revés. |
| D4 | No mostrar `TAGS` ni `DATASET_ENTRY` dentro del informe PACS. |
| D5 | En la impresión de fascitis plantar, evitar repetir medidas ya descritas en Hallazgos. |

---

## B. REGLAS BLANDAS COMPROBABLES → VALIDADOR / PROMPT

| ID | Regla |
|---|---|
| B1 | En estudios de pie o antepié, valorar el complejo de Lisfranc. |
| B2 | En RM de tobillo, revisar tendones principales, complejos ligamentarios, seno del tarso y fascia plantar. |
| B3 | En RM de pie/antepié, revisar fracturas por estrés, tendones, placas plantares, neuroma de Morton, bursas intermetatarsianas, sesamoideos y almohadilla plantar. |
| B4 | Cuando exista lesión del complejo lateral, describir LPAA, LPC y LPAP de forma individual. |
| B5 | La impresión diagnóstica debe excluir hallazgos normales y limitarse a la patología relevante. |

---

## C. REGLAS CLÍNICAS Y DE REDACCIÓN → SYSTEM PROMPT

### C1. Anatomía por subregiones
Distinguir:
- tobillo;
- retropié;
- mediopié;
- antepié.

En estudios combinados, separar cada territorio.

### C2. Causalidad
Usar la estructura causal correcta:
- “Os trigonum con signos de pinzamiento posterior”.
- “Proceso de Stieda con cambios inflamatorios compatibles con pinzamiento posterior”.
- “Fascitis plantar con rotura parcial”, evitando formulaciones que inviertan la causa.

### C3. Bursas intermetatarsianas
Usar “distensión de la bursa intermetatarsiana”. No utilizar “distensión bursátil”.

### C4. Fascitis plantar
En Hallazgos puede describirse grosor, señal, edema y rotura. En la impresión debe resumirse:
- “Hallazgos compatibles con fascitis plantar”.
- “Rotura de espesor parcial de fibras profundas”, cuando exista.

### C5. Complejo lateral
Describir individualmente:
- ligamento peroneoastragalino anterior;
- ligamento peroneocalcáneo;
- ligamento peroneoastragalino posterior.

La pérdida del patrón fibrilar orienta a rotura de alto grado o completa; el engrosamiento
con patrón conservado puede corresponder a lesión parcial o cambio fibrocicatricial.

### C6. Complejo deltoideo
Cuando esté afectado, diferenciar componentes superficial y profundo y relacionar el edema
óseo con las inserciones ligamentarias cuando sea posible.

### C7. Tendones peroneos
Valorar:
- peroneo largo y corto;
- rotura longitudinal;
- tenosinovitis;
- subluxación;
- retináculos peroneos superior e inferior.

### C8. Líquido en vainas
No diagnosticar tenosinovitis solo por líquido potencialmente fisiológico, especialmente en
la vaina del flexor largo del primer dedo en comunicación con el receso posterior. Exigir
alteración de señal/morfología o inflamación adyacente.

### C9. Lisfranc
En lesión de Lisfranc:
- describir continuidad del ligamento;
- edema óseo asociado;
- diástasis M1-M2/C1-M2;
- recordar que la RM suele realizarse sin carga;
- no excluir inestabilidad dinámica únicamente por ausencia de diástasis en descarga.

### C10. Lesiones osteocondrales
Usar una clasificación apropiada para RM cuando existan datos suficientes. No inventar el
estadio. Describir siempre localización, tamaño, integridad de la superficie, edema/quistes
subcondrales y estabilidad del fragmento.

### C11. Antepié
Checklist:
- articulaciones;
- fracturas por estrés;
- Lisfranc;
- tendones;
- placas plantares;
- neuroma de Morton;
- bursas intermetatarsianas;
- sesamoideos;
- almohadilla plantar;
- fascia plantar incluida.

### C12. Impresión diagnóstica
- Solo patología relevante.
- Sin repetir estructuras normales.
- Jerarquizar lesión principal, lesiones asociadas e incidentales.
- Evitar recomendaciones no solicitadas.

---

## D. CHECKLIST DE RM DE TOBILLO

1. Tibiotalar y subtalares.
2. Derrame y lesiones osteocondrales.
3. LPAA, LPC y LPAP.
4. Deltoideo superficial y profundo.
5. Sindesmosis si procede.
6. Aquiles y grasa de Kager.
7. Peroneos y retináculos.
8. Tibial posterior.
9. Flexores largos.
10. Extensores.
11. Seno del tarso.
12. Fascia plantar.

---

## E. CHECKLIST DE RM DE PIE/ANTEPIÉ

1. Articulaciones.
2. Fracturas y lesiones por estrés.
3. Lisfranc.
4. Tendones flexores y extensores.
5. Placas plantares.
6. Neuroma de Morton.
7. Bursas intermetatarsianas.
8. Sesamoideos.
9. Almohadilla plantar.
10. Fascia plantar incluida.
11. Zona marcada por el paciente, si existe.

---

## Observaciones de implementación

- El archivo ejecutable es `validador_tobillo_pie.py`.
- Los avisos de checklist deben mantenerse inicialmente con gravedad baja o media.
- Las clasificaciones osteocondrales no deben automatizarse por completo sin datos
  morfológicos suficientes.
- Antes de endurecer nuevas reglas deben probarse contra casos reales de tobillo y antepié.
