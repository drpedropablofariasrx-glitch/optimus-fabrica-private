# Auditoría de corpus de estilo MSK — 2026-08-02

## Resultado

OPTIMUS ya dispone de un corpus activo de **594 informes aprobados**. Además,
se ha localizado una biblioteca histórica independiente de **1.108 registros
MSK** en la copia histórica del proyecto. No se ha incorporado automáticamente
como conocimiento clínico ni como casos aprobados.

El preparador local descartó duplicados textuales contra las colas operativas y
dejó **807 informes completos nuevos** en una bandeja separada de candidatos de
estilo. Esta bandeja requiere aprobación humana antes de participar en ejemplos
de estilo o en un futuro entrenamiento supervisado.

## Corpus activo (solo aprobado)

| Región | Informes aprobados |
| --- | ---: |
| Hombro | 210 |
| Lumbar | 91 |
| Mano-muñeca | 79 |
| Abdomen-pelvis | 74 |
| Cadera-pelvis | 66 |
| Tórax | 23 |
| Cervical | 16 |
| Tobillo-pie | 16 |
| Codo | 9 |
| Rodilla | 8 |
| Otras/sin clasificar | 2 |

Este es el único conjunto que puede considerarse actualmente como referencia
activa del estilo del radiólogo.

## Casos históricos recuperables

| Región | Registros históricos | Informes completos | Duplicados excluidos | Candidatos nuevos |
| --- | ---: | ---: | ---: | ---: |
| Cadera-pelvis | 172 | 158 | 5 | 153 |
| Cervical | 57 | 47 | 0 | 47 |
| Codo | 28 | 20 | 0 | 20 |
| Lumbar | 198 | 148 | 4 | 144 |
| Mano-muñeca | 252 | 213 | 9 | 204 |
| Rodilla | 112 | 27 | 1 | 26 |
| Tobillo-pie | 189 | 130 | 4 | 126 |
| Tórax | 100 | 93 | 6 | 87 |
| **Total** | **1.108** | **836** | **29** | **807** |

La aparente escasez de rodilla en la pantalla SFT no representaba el material
disponible: hay 112 registros históricos de rodilla, 27 informes completos y
26 candidatos nuevos después de deduplicar. Los otros 85 son fragmentos y no
deben entrar como ejemplos de estilo sin reconstrucción o revisión adicional.

## Fuentes auditadas

- Exportaciones históricas de columna cervical, rodilla (dos archivos),
  tobillo-pie, tórax, cadera-pelvis, codo, lumbar y mano-muñeca.
- Colas operativas `optimus_sft_v1` y de importación VuePACS.
- Biblioteca histórica `optimus_curation_v1` de la copia de OneDrive.
- Importación de la conversación principal MSK hombro: 906 turnos recuperados,
  212 pares detectados y 210 candidatos introducidos en la cola para revisión.

Las exportaciones raíz de las dos ubicaciones son idénticas salvo la de codo;
la de la carpeta activa es la más reciente y se toma como referencia. El
resumen de hombro documenta otra conversación separada que no aparece entre
los archivos localizables: sigue siendo una fuente pendiente de aportar o
exportar, no se ha inventado ni contabilizado.

## Qué se ha preparado

El script `scripts/preparar_corpus_estilo_optimus.py` genera localmente, dentro
de `datasets/private/optimus_style_v1/` (excluido de Git):

- `perfil_estilo_activo.json`: métricas por región calculadas solo desde los
  594 aprobados.
- `candidatos_estilo_por_revisar.jsonl`: 807 informes completos históricos,
  deduplicados y marcados como `candidate`.
- `resumen_auditoria_estilo.json`: trazabilidad de los recuentos.

El proceso no cambia prompts, reglas regionales, casos Gold ni estados de la
cola SFT.

## Próximo paso recomendado

1. Revisar primero por regiones de alto valor: rodilla, cervical y lumbar.
2. Promover únicamente informes que reflejen el estilo final deseado a
   `style_eligible`.
3. Usar los aprobados como recuperación de ejemplos por región/modalidad, no
   como instrucciones clínicas nuevas.
4. Mantener por separado entrenamiento de estilo, reglas clínicas y casos
   Gold. Un informe bien redactado no convierte por sí mismo su contenido
   diagnóstico en una regla.

Antes de enviar ejemplos completos a un proveedor cloud habrá que confirmar el
modo de recuperación y el coste. El perfil estadístico y la auditoría actuales
son completamente locales.
