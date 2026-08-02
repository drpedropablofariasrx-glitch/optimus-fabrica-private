# SEGURIDAD_UNIDADES_CODO

**Validador:** `codo-1.1`  
**Fecha:** 2026-07-19

## Regla de biceps distal

Ante una rotura completa del biceps distal, D4 verifica que exista una
descripcion de retraccion. No corrige ni reescribe el informe.

- `8 cm` se conserva como `8 cm`.
- `8 mm` se conserva como `8 mm`.
- Una retraccion numerica sin unidad genera un aviso bajo para revision.
- Dos medidas de retraccion internamente incompatibles generan un aviso bajo.
- La ausencia de retraccion en una rotura completa genera un aviso bajo.
- Un informe sin rotura completa no activa D4.

La regla nunca convierte cm a mm ni mm a cm. Solo usa una conversion interna
para detectar discrepancias, sin modificar texto, valores ni unidades. D4 no
declara `bloquea_gold`, por lo que no bloquea Gold por defecto.
