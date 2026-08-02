# AUDITORIA_TOBILLO_PIE_PREINTEGRACION

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-19

## Material revisado

Se revisaron `SYSTEM_PROMPT_tobillo_pie.txt`, `validador_tobillo_pie.py` y `REGLAS_TOBILLO_PIE_MAESTRAS.md`.

## Resultado

1. No se encontraron reglas activas heredadas de abdomen, columna, rodilla, mano-muneca o codo.
2. El prompt diferencia tobillo, retropie, mediopie, pie y antepie. Se hizo explicita la limitacion de campo para dedos, articulaciones concretas y estudios focales.
3. B1/B3 corresponden a pie, mediopie o antepie; B2/B4 a tobillo. No se aplican a ecografia ni TC, que no comparten automaticamente el checklist de RM.
4. Lisfranc se revisa como aviso bajo en RM de pie/mediopie/antepie, nunca en tobillo limitado o estudio focal de Aquiles. B6 recuerda que un estudio sin carga no excluye inestabilidad dinamica.
5. B4 individualiza LPAA, LPC y LPAP cuando se describe lesion lateral. La sindesmosis permanece condicionada al mecanismo o hallazgos y no se exige universalmente.
6. D2 conserva `distension de la bursa intermetatarsiana`; D3 conserva la causalidad `os trigonum con signos de pinzamiento posterior`; D5 evita repetir medidas de fascitis en la impresion.
7. B7 avisa si se etiqueta tenosinovitis del FHL solo por liquido fisiologico aislado. No diagnostica ni autocorrige.
8. Todos los avisos regionales carecen de `bloquea_gold`; no se convierten en bloqueos por gravedad.

## Riesgos pendientes

La modalidad y el campo se infieren del encabezado textual. La clasificacion osteocondral, estabilidad real de Lisfranc y valoracion de sindesmosis dependen de datos anatomicos y clinicos que el validador no inventa.
