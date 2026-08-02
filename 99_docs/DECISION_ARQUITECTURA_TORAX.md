# DECISION_ARQUITECTURA_TORAX

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-20  
**Decision:** preparar una unica region futura `torax` con perfiles internos cerrados. No activar en esta fase.

## Respuesta ejecutiva

1. Torax puede integrarse como una sola region porque comparte modalidad predominante (TC), checklist anatomico y contrato de persistencia.
2. Necesita subtipos internos para impedir que las reglas de TEP, cribado, oncologia, infeccion, trauma y postquirurgico se apliquen fuera de contexto.
3. TAP debe manejarse inicialmente como `study_type = torax_abdomen_pelvis` dentro de la futura region torax, no como composicion automatica ni como una nueva region. El registro conserva `region = torax` y anade el tipo de estudio al registro futuro.
4. Los unicos bloqueos Gold futuros deben ser estructurales: input/final vacios, metainformacion visible, error interno del validador o contradiccion estructural definida y caracterizada. Las reglas clinicas comienzan como avisos.
5. TEP VD/VI, calidad de contraste, checklist, Lung-RADS, RECIST, comparacion, TAP, trauma y postquirurgico deben ser avisos contextuales, no bloqueos por defecto.
6. Faltan configuracion regional, taxonomia, pruebas, ejemplos anonimizados y perfiles de protocolo.

## Taxonomia cerrada propuesta

Separar conceptos evita usar una indicacion como si fuera protocolo:

| Dimension | Valores iniciales | Uso |
|---|---|---|
| `study_type` | `tc_torax`, `angio_tc_tep`, `cribado_pulmonar`, `torax_abdomen_pelvis` | Define el alcance tecnico principal y checklist. |
| `clinical_context` | `general`, `oncologico`, `infeccioso`, `trauma`, `postquirurgico` | Puede coexistir con cualquier tipo compatible. |
| `protocol` | `sin_contraste`, `con_contraste`, `angiografico_pulmonar`, `baja_dosis_cribado`, `tap_con_contraste` | Describe adquisicion; no sustituye la indicacion. |
| `comparison_available` | `unknown`, `no`, `yes` | Habilita solo lenguaje evolutivo sustentado. |

`oncologico`, `infeccioso`, `trauma` y `postquirurgico` son contextos clinicos, no tipos anatomicos. Pueden combinarse con `tc_torax` o, con reglas explicitas futuras, con TAP.

## Matriz de perfiles futuros

| Tipo | Modalidad / contraste | Checklist adicional | Reglas blandas | Bloqueos Gold propuestos |
|---|---|---|---|---|
| `tc_torax` | TC sin o con contraste | Base anatomica | Campo parcial, hallazgos incidentales | Ninguno clinico inicial |
| `angio_tc_tep` | TC angiografica pulmonar | Arterias pulmonares, calidad, VD/VI si medido, alternativas | Opacificacion suboptima, VD/VI incoherente | Solo error tecnico explicitamente definido tras caracterizacion |
| `cribado_pulmonar` | TC baja dosis | Nodulos, tamano, morfologia, crecimiento si hay previo | Lung-RADS solo con datos suficientes | Ninguno |
| `tc_torax` + `oncologico` | Segun protocolo | Lesion diana y comparacion | RECIST/estabilidad/progresion solo con previo | Ninguno |
| `tc_torax` + `infeccioso` | Segun indicacion | Patron, distribucion, complicaciones | Etiologia no sustentada | Ninguno |
| `tc_torax` + `trauma` | Con contraste si corresponde | Costillas, esternon, pleura, pulmon, vasos si campo/protocolo | Estructuras fuera de campo | Ninguno |
| `tc_torax` + `postquirurgico` | Segun cirugia | Material, cambios esperables, complicaciones | Recidiva o evolucion sin evidencia | Ninguno |
| `torax_abdomen_pelvis` | TAP con contraste segun fase | Base toracica y abdomen/pelvis declarados por perfil | Separacion anatomica y comparacion | Ninguno clinico inicial |

## Checklist anatomico base de TC de torax

Siempre que el campo sea TC de torax completo: pulmones, via aerea central, pleuras, mediastino, hilios, corazon/pericardio, grandes vasos, ganglios, pared toracica y estructuras oseas.

Dependientes de protocolo: arterias pulmonares y VD/VI en TEP; lesion diana/comparacion en oncologia; parrilla costal/esternon/vasos en trauma; material y complicaciones en postquirurgico.

Incidental y sin exigencia automatica: abdomen superior incluido, coronarias, tiroides, mama y hallazgos extratoracicos. Un estudio parcial no debe exigir estructuras fuera de campo.

## TAP: opciones evaluadas

| Opcion | Ventaja | Riesgo | Decision |
|---|---|---|---|
| A. Torax con extension | Minima complejidad | Ambiguedad de ownership abdominal | No recomendada como nombre conceptual. |
| B. Region combinada independiente | Dataset muy explicito | Crea una novena region y duplica infraestructura | Diferir. |
| C. Composicion torax + abdomen | Maxima reutilizacion teorica | Requiere coordinacion de prompts, validadores, Gold y persistencia que OPTIMUS aun no posee | No implementar ahora. |
| D. Tipo interno `torax_abdomen_pelvis` | Una sola configuracion, trazabilidad con `study_type`, sin core nuevo | Requiere checklist TAP propio y evita importar reglas abdominales a ciegas | Recomendada para V1. |

## Diseno futuro de configuracion

`09_torax/region_config.py` debera exponer `REGION_ID = "torax"`, `REGION_NAME = "Torax"`, `PROMPT_PATH`, `VALIDATOR_MODULE`, `CASES_DIR`, `DATASET_PATH`, `PROMPT_VERSION`, `VALIDATOR_VERSION`, `DATASET_SCHEMA_VERSION` y `STUDY_TYPE_TAXONOMY` con los valores anteriores. No se crea ni registra en esta fase.

## Diseno del validador y plan de pruebas

El futuro validador debe resolver primero modalidad, tipo, protocolo, contraste, campo, contexto, comparacion y si es TAP. Despues aplicara solo reglas del perfil correspondiente.

Plan minimo de pruebas: TC general, TEP con contraste adecuado/suboptimo y VD/VI, cribado con y sin datos para Lung-RADS, oncologico con y sin previo, infeccioso, trauma, postquirurgico, parcial, TAP, aislamiento frente a abdomen, persistencia regional y Gold regional.

## Orden exacto de implementacion

1. Corregir y caracterizar el material toracico existente sin activarlo.
2. Aprobar la taxonomia y perfiles de esta decision.
3. Crear prompt y validador conscientes de perfil, con pruebas unitarias clinicas.
4. Crear `09_torax/region_config.py` y sus rutas regionales.
5. Agregar pruebas de integracion, importador y Gold aislado.
6. Registrar torax como octava region y mostrarlo en selector solo tras regresion completa.
