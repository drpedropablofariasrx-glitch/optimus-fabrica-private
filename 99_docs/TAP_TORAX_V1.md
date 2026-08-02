# TAP_TORAX_V1

TAP se implementa como `study_type = torax_abdomen_pelvis` dentro de la region torax. No es una novena region ni una composicion automatica de torax y abdomen.

El informe separa los tres territorios. El validador exige que Hallazgos incluya alguna valoracion de torax, abdomen y pelvis; su ausencia completa es un bloqueo estructural. La persistencia conserva `region = torax`, `study_type = torax_abdomen_pelvis` y su propio dataset, sin mezclar casos con abdomen.
