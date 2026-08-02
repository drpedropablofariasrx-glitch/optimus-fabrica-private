# AUDITORIA_MANO_MUNECA_PREINTEGRACION

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-19

## Alcance auditado

Se revisaron `SYSTEM_PROMPT_mano_muneca.txt`, `validador_mano_muneca.py` y
`REGLAS_MANO_MUNECA_MAESTRAS.md` antes de habilitar la region.

## Hallazgos

1. No se detectaron referencias activas a columna cervical/lumbar, rodilla o
   patelofemoral, torax ni abdomen en el prompt o validador.
2. La regla B1 valora nervio mediano y cubital en estudios completos de mano.
   Se ajusto para que un estudio limitado de dedo/falange no active ese checklist.
3. La regla B2 valora tunel carpiano y canal de Guyon solo al identificar muneca.
   Ambas reglas son avisos y no bloquean Gold.
4. El prompt original no declaraba de forma explicita el alcance variable ni el
   TFCC, ligamentos carpianos, tendones flexores/extensores y estructuras del
   carpo. Se completo como guia blanda condicionada al campo y la modalidad.
5. No se anadieron requisitos de checklist para estudios parciales. TFCC,
   ligamentos carpianos, tunel carpiano y Guyon no se exigen fuera de campo.
6. D2 mantiene la taxonomia regional de severidad. D3 estaba declarado pero era
   un no-op; se corrige separadamente.
7. Los flags regionales se normalizan con `bloquea_gold = false` salvo una marca
   explicita o una condicion estructural de la aplicacion. B1, B2 y D3 no son
   bloqueos Gold.

## Riesgos clinicos pendientes

- La identificacion automatica del campo parte del encabezado de Exploracion y
  es intencionadamente conservadora; el radiologo conserva el criterio final.
- El validador no intenta inferir si todas las estructuras son visibles en una
  modalidad o protocolo concreto. Esa decision sigue siendo regional y clinica.
- El corpus historico combinado incluia codo; codo no se habilita ni se mezcla
  con mano-muneca en esta fase.
