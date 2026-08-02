# AUDITORIA_TORAX_PREINTEGRACION

**Fecha:** 2026-07-20  
**Estado:** hallazgos documentados; no se modifica prompt ni validador toracico.

## Contaminaciones y riesgos

| Fuente | Hallazgo | Riesgo | Accion futura propuesta |
|---|---|---|---|
| Prompt B1 y reglas maestras B1 | Ordena aplicar reglas de abdomen a abdomen superior incluido. | Duplica ownership clinico y mezcla la futura persistencia toracica con criterios abdominales. | Definir un checklist de abdomen superior toracico limitado, sin importar el validador de abdomen. |
| Reglas maestras B3 / prompt B3 | Incluyen macro PieloTC negativo. | PieloTC/urolitiasis no es un protocolo toracico; contenido obsoleto o contaminado. | Retirarlo o moverlo al futuro modulo urologico tras auditoria propia. |
| Validador D1 / prompt Exploracion | D1 marca titulos de estudio en el cuerpo, mientras el prompt exige nombre tecnico en Exploracion. | Posible falso positivo si Exploracion forma parte del texto validado. | Delimitar secciones o hacer D1 consciente de encabezados. |
| Validador D3 | VD/VI se aplica por menciones de TEP, sin resolver protocolo, calidad tecnica ni si la medicion es comparable. | Aviso clinico potencialmente sobredimensionado; gravedad alta podria interpretarse como bloqueo futuro. | Mantenerlo como aviso moderado condicionado a angio-TC TEP y ratio explicitamente declarado. |
| Validador D4 | Regla de pie chileno depende de inferencia de formato. | Puede generar ruido en borradores, docencia e informes internacionales; no es una regla anatomica toracica. | Separarla como politica de formato transversal, no convertirla en bloqueo Gold. |
| Prompt B2 | Lung-RADS se invoca cuando aplique sin detectar programa de cribado ni datos suficientes. | Riesgo de inventar categoria o elegibilidad. | Activar solo con `cribado_pulmonar` explicito y datos suficientes; de otro modo aviso informativo. |
| Validador D2 y capa comun | QA visible se solapa parcialmente con `META_VISIBLE` de la aplicacion. | Duplicacion de flags y mensajes. | Mantener una unica capa comun de metainformacion visible en la fase de integracion. |

## Reglas ausentes o no operativas para la futura region

- No existe clasificacion de modalidad, protocolo, contraste, campo anatomico, indicacion ni comparacion previa.
- No hay checklist anatomico base de TC de torax.
- No hay reglas diferenciadas para cribado, oncologia, infeccion, trauma o postquirurgico.
- No hay proteccion especifica contra afirmar estabilidad/progresion/recidiva sin comparacion.
- No hay logica para estudio parcial ni para TAP mas alla de referencias textuales.

## Bloqueos Gold

El validador toracico actual no declara `bloquea_gold`. En la aplicacion vigente, D3 de gravedad alta tampoco se convierte automaticamente en bloqueo. No debe cambiarse esa politica en una futura integracion sin caracterizacion clinica y aprobacion explicita.
