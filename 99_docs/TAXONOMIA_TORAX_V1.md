# TAXONOMIA_TORAX_V1

| Dimension | Valores cerrados | Significado |
|---|---|---|
| `study_type` | `tc_torax`, `angio_tc_tep`, `cribado_pulmonar`, `torax_abdomen_pelvis` | Alcance tecnico y checklist principal. |
| `clinical_context` | `general`, `oncologico`, `infeccioso`, `trauma`, `postquirurgico` | Contexto combinable; no sustituye el tipo. |
| `protocol` | `sin_contraste`, `con_contraste`, `angiografico_pulmonar`, `baja_dosis`, `tap` | Adquisicion; no es indicacion clinica. |
| `contrast` | `sin_contraste`, `con_contraste` | Metadato explicito de contraste. |
| `comparison_available` | booleano | Habilita lenguaje evolutivo sustentado. |

Reglas de coherencia: `angio_tc_tep` exige `angiografico_pulmonar`; `cribado_pulmonar`, `baja_dosis`; y `torax_abdomen_pelvis`, `tap`. Un valor explicito desconocido no se sustituye silenciosamente y bloquea Gold como incoherencia estructural.
