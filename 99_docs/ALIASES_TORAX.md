# ALIASES_TORAX

Todos los aliases siguientes enrutan a `region = torax`:

| Alias | `study_type` inferido |
|---|---|
| `torax`, `tc torax`, `tac torax` | `tc_torax` |
| `angiotc tep`, `angio tc pulmonar`, `tep` | `angio_tc_tep` |
| `screening pulmonar`, `cribado` | `cribado_pulmonar` |
| `tap`, `torax abdomen pelvis` | `torax_abdomen_pelvis` |

Un texto ambiguo se normaliza a `tc_torax`, conserva la inferencia en metadatos y no activa reglas especializadas.
