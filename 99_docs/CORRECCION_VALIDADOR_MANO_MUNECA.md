# CORRECCION_VALIDADOR_MANO_MUNECA

**Fecha:** 2026-07-19  
**Version de validador:** `mano_muneca-1.1`

## Problema

`regla_D3()` siempre devolvia una lista vacia. Por tanto la taxonomia aprobada
de cronicidad estaba documentada, pero no tenia ningun efecto comprobable.

## Correccion conservadora

La regla ahora revisa exclusivamente declaraciones estructuradas:

```text
Cronicidad: aguda | subaguda | cronica | degenerativa | postraumatica | postquirurgica
Evolucion: ...
Curso: ...
```

Si el valor declarado no pertenece a esa lista, emite `D3` de gravedad baja.
No exige que la cronicidad exista y no analiza lenguaje clinico libre, por
ejemplo `cambios cronicos`, para evitar falsos positivos.

`D3` no declara `bloquea_gold`; por tanto no bloquea Gold por ausencia ni por
una variante estilistica. No se reescriben terminos historicos ni se transforma
`severa` o equivalentes automaticamente.

## Ajuste de campo limitado

La B1 deja de activarse cuando Exploracion identifica un estudio de dedo,
falange o articulacion interfalangica. Asi no exige nervios mediano/cubital en
un campo anatomico que no los incluye.

Las pruebas cubren cronicidad valida, invalida, ausente y lenguaje clinico
libre, junto con muneca, mano y dedo limitado.
