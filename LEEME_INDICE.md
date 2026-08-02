# FÁBRICA RADIOLÓGICA MSK — Proyecto completo

Índice de todo el material del proyecto: la aplicación, y las **seis regiones**
analizadas, cada una con sus reglas extraídas, su validador determinista y su
prompt de sistema.

---

## Cómo está organizado

```
FABRICA_MSK/
├── 00_APP/          → La aplicación (programa Flask) + cómo arrancarla
├── 01_abdomen/      → 31 reglas (12 duras + 19 blandas)
├── 02_lumbar/       → 13 reglas (4 duras + 9 blandas)
├── 03_cervical/     → 7 reglas (3 duras + 4 blandas)
├── 04_torax/        → 7 reglas (4 duras + 3 blandas)
├── 05_rodilla/      → 10 reglas (4 duras + 6 blandas)
├── 06_mano_muneca/  → 7 reglas (3 duras + 4 blandas)
└── 99_docs/         → Estado del proyecto (resumen para presentar)
```

## Qué hay en cada carpeta de región

Cada región tiene (salvo abdomen, ver nota) tres archivos, que son los tres
entregables del método:

- **REGLAS_[REGION]_MAESTRAS.md** — la lista de reglas extraídas de tu año de
  trabajo en ChatGPT, cada una con su cita textual y el número de línea de
  origen. Es la documentación de referencia: qué reglas hay y de dónde salen.
- **validador_[region].py** — el código Python que comprueba las reglas DURAS
  (las objetivas: umbrales, medidas, formato). Se ejecuta sobre un informe y
  avisa de incoherencias. Probado contra casos reales de cada corpus.
- **SYSTEM_PROMPT_[region].txt** — las reglas BLANDAS (criterio clínico) escritas
  como instrucciones para el modelo generador.

> **Nota sobre abdomen:** su prompt de sistema vive todavía dentro de la
> aplicación (`fabrica_abdomen.py`), por eso en `01_abdomen/` solo están las
> reglas maestras y el validador. Cuando se generalice la app a multi-región,
> el prompt de abdomen se extraerá a su propio `SYSTEM_PROMPT_abdomen.txt`
> como en las demás regiones.

## Resumen de las seis regiones

| Región | Casos aprox. | Reglas duras | Reglas blandas | Regla estrella |
|--------|-------------|--------------|----------------|----------------|
| Abdomen | ~237 | 12 | 19 | Umbrales UH (esteatosis, lipoma, realce por fases) |
| Lumbar | ~159 | 4 | 9 | Jerarquía disco/faceta condicional a estenosis |
| Cervical | ~51 | 3 | 4 | Nomenclatura cerrada de hernias (no "posterolateral") |
| Tórax | ~93 | 4 | 3 | Índice VD/VI >0.9 en TEP (con cita bibliográfica) |
| Rodilla | (corpus fundacional) | 4 | 6 | Consolidar estructuras normales; condropatía en romanos |
| Mano-muñeca | ~223 | 3 | 4 | Valoración obligatoria de nervio mediano y cubital |

## Reglas transversales detectadas (comunes a varias regiones)

Estas reglas aparecen en más de una región y son candidatas a vivir en un lugar
común cuando se generalice la fábrica, en vez de repetirse:

- **Pie "Informado por / Validado por"** — regla universal: incluir si y solo si
  el informe tiene formato clínico chileno (FONASA/ID paciente/RUT). Ya unificada
  en las cuatro regiones donde aplicaba.
- **Análisis de oportunidades de mejora** — presente en abdomen y mano-muñeca con
  la misma formulación.
- **Taxonomías cerradas de severidad y cronicidad** — definidas con más detalle en
  mano-muñeca, pero aplicables a todas las regiones MSK.
- **Exclusión de datos demográficos** (edad/sexo/hospital) del cuerpo del informe.

## Diferencias legítimas entre regiones (NO unificar)

- **"Receso lateral"**: se usa en lumbar (existe el compartimento anatómico),
  NO se usa en cervical (no existe ahí). Diferencia anatómica real, documentada.

## Estado y siguiente paso

Las seis regiones están extraídas, con validador probado. El paso pendiente es
**generalizar la aplicación a multi-región**: añadir un selector que cargue el
prompt y el validador de cada región, sin mezclar reglas entre ellas. Con eso,
estos archivos dejan de ser material de referencia y pasan a ser el sistema
funcionando.

Ver `99_docs/ESTADO_PROYECTO_IA_RADIOLOGICA.md` para el resumen completo del
estado del proyecto.
