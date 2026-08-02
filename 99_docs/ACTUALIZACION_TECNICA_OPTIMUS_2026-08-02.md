# Actualización técnica OPTIMUS — 2 de agosto de 2026

## Propósito

Esta nota consolida los aprendizajes recientes sobre IA local, MedGemma y
conversaciones históricas. Sustituye la tendencia a incorporar novedades por
separado por decisiones verificables para la fábrica.

## Decisiones vigentes

| Área | Decisión | Motivo |
|---|---|---|
| Motor productivo | Mantener `llama-server` / `llama.cpp` como proveedor local de OPTIMUS. | Ya está integrado mediante API OpenAI-compatible y permite controlar memoria, modelo y servidor por separado. |
| LM Studio | Mantenerlo como laboratorio y alternativa local, no como dependencia clínica central. | Ofrece API compatible, MCP y JSON Schema, pero el comportamiento de producción debe permanecer fijado y testeado. |
| Hardware | Mantener la RTX 5060 de 8 GB para modelos pequeños/medianos cuantizados y una sola petición. | No hay evidencia aún de que más hardware reduzca el tiempo de revisión humana. |
| MedGemma | Usarlo exclusivamente para explorar capacidad visual y generación de texto; no para diagnóstico autónomo ni segmentación. | Sus pesos y entrenamiento no sustituyen validación radiológica, segmentadores ni mediciones especializadas. |
| Segmentación | Usar 3D Slicer + TotalSegmentator en experimentos de TC/RM. | Es una tarea distinta de la comprensión visual de un VLM. |
| RAG/vector DB | Aplazado. | Antes hay que medir que la recuperación de conocimiento mejora casos difíciles sin contaminar lateralidad, región o contexto. |
| Agentes/PACS | Sin agentes autónomos ni escritura directa en PACS. | Todo informe y toda promoción a Gold mantienen revisión humana. |

## Novedad que sí debe incorporarse: generación estructurada

Tanto `llama-server` como LM Studio permiten restringir una respuesta a un
JSON Schema. OPTIMUS debe evolucionar a dos fases, evitando pedir directamente
un texto PACS libre cuando la tarea sea compleja:

```text
Dictado o caso
  -> JSON clínico validado por esquema
  -> validadores deterministas por región
  -> renderizador de informe PACS
  -> revisión humana
```

El esquema no autoriza a inventar normalidad. Para cada estructura debe admitir
`no_mencionado` o `no_evaluable`; solo se afirmará normalidad si está sustentada
por el caso o por una regla clínica explícita.

Primera aplicación: crear un esquema pequeño por región con modalidad,
lateridad, hallazgos mencionados, medidas, impresión y campos `no_mencionado`.
No se reemplazarán los prompts actuales hasta compararlo contra una batería fija.

Fuentes técnicas:

- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://lmstudio.ai/docs/developer/openai-compat/structured-output

## Conversaciones y fábrica: contrato de entrada obligatorio

Las conversaciones de ChatGPT pueden incluir análisis, correcciones,
recordatorios y contenido no clínico. Por ello nunca se importará una
conversación completa como caso. El único objeto importable es un bloque
explícito, un archivo por caso:

```text
[OPTIMUS_CASE_V1]
CASE_ID_EXTERNO: <identificador único>
PROYECTO_ORIGEN: <proyecto o conversación>
REGION: rodilla
MODALIDAD: RM
ESTADO: final | incompleto

DATOS_CLINICOS:
...

EXPLORACION:
...

HALLAZGOS:
...

IMPRESION:
...
[/OPTIMUS_CASE_V1]
```

Reglas de ingreso:

1. `final` exige los cinco bloques y se incorpora como `imported_pending`.
2. `incompleto` conserva contexto y contenido parcial como
   `imported_incomplete`; nunca será Gold ni SFT.
3. Cualquier `TAGS`, `DATASET_ENTRY`, análisis docente o campo obligatorio
   ausente se mueve a cuarentena.
4. Se conserva el archivo, la conversación/proyecto de origen, el intervalo
   de líneas si procede y un hash normalizado para impedir duplicados.
5. Una versión corregida se enlaza con el mismo `CASE_ID_EXTERNO`, no se trata
   automáticamente como otro caso clínico.

## Buzón sincronizado: siguiente mejora de integración

Crear una carpeta sincronizada entre el ordenador de preparación y el del
hospital:

```text
OPTIMUS_FABRICA/
  01_ENTRADA/
  02_PROCESADOS/
  03_CUARENTENA/
  04_REGISTRO/
```

Google Drive for desktop puede sincronizar estos archivos entre equipos. La app
Google Drive de ChatGPT puede ayudar a encontrar, crear o actualizar archivos
según el plan y los permisos disponibles, pero no es el mecanismo de validación
ni una exportación automática fiable de cada conversación. El importador local
será siempre la autoridad sobre el estado del caso.

Fuentes:

- https://support.google.com/a/users/answer/13022292
- https://help.openai.com/en/articles/10948259-google-drive-synced-connectors-self-service-setup/

## Evaluación antes de adoptar modelos o hardware

Mantener un conjunto de regresión de 50–60 informes anonimizados, por región y
modalidad, con informes Gold separados de los casos pendientes. Para cada
cambio registrar:

- modelo, cuantización, motor y versión de prompt;
- tiempo hasta el primer token y tiempo total;
- VRAM/RAM máximas;
- validez del JSON al primer intento;
- errores de lateralidad, negación, medida y coherencia hallazgos-impresión;
- tiempo humano hasta informe listo para PACS;
- aceptación sin modificación clínica.

Un modelo, cuantización o GPU solo se adopta si mejora estas métricas frente a
la configuración base. Los benchmarks generalistas no bastan para justificar
un cambio de producción.

## Prioridad de ejecución

1. Implementar y probar el contrato `OPTIMUS_CASE_V1` y la cuarentena.
2. Construir el vigilante del buzón local con deduplicación y registro.
3. Preparar el primer JSON Schema regional y compararlo contra el flujo actual.
4. Construir la batería de regresión y almacenar métricas de cada ejecución.
5. Solo después evaluar RAG, ajuste fino, nuevos modelos o hardware.
