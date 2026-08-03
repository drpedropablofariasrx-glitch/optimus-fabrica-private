# Handoff mínimo para Claude

Antes de investigar el proyecto, leer solo `99_docs/HANDOFF_CLAUDE.md`.
Ese archivo es la fuente breve del estado actual, cambios recientes, comandos
de verificación y próximos pasos. No releer el repositorio completo salvo que
la tarea lo requiera.

## Regla de eficiencia

1. Empieza por el handoff y `git status --short`.
2. Inspecciona únicamente los archivos enumerados allí o los que exige la
   tarea. Usa búsquedas dirigidas (`rg`) antes de abrir archivos extensos.
3. No leas `datasets/private/`, `.env`, credenciales ni informes fuente salvo
   que la tarea lo requiera expresamente. Nunca los subas a Git.
4. Conserva cambios locales ajenos; no uses reset, checkout destructivo ni
   reformateos masivos.
5. Tras un cambio verificado, sustituye el contenido de
   `99_docs/HANDOFF_CLAUDE.md` por un resumen compacto y actualizado. No lo
   conviertas en un historial acumulativo: máximo aproximado de 100 líneas.

## Contrato clínico y de datos

- OPTIMUS ayuda a redactar y revisar; no sustituye la validación del radiólogo.
- No mezclar informes de estilo con reglas clínicas ni prompts persistentes.
- Todo uso de datos para SFT exige pares aprobados y trazabilidad de origen.
- El benchmark reservado nunca entra en entrenamiento.
