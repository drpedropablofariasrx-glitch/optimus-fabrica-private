# INVENTARIO_TORAX_PREINTEGRACION

**Proyecto:** OPTIMUS  
**Fecha:** 2026-07-20  
**Alcance:** preparacion de torax sin activar una octava region.

## Archivos encontrados

| Archivo | Estado | Observacion |
|---|---|---|
| `04_torax/SYSTEM_PROMPT_torax.txt` | Existe | Prompt clinico de TC de torax, con referencias a TAP y abdomen superior. |
| `04_torax/REGLAS_TORAX_MAESTRAS.md` | Existe | Fuente documental de cuatro reglas duras y tres blandas. |
| `04_torax/validador_torax.py` | Existe | Validador determinista con D1-D4. No esta registrado ni cargado por OPTIMUS. |

## Archivos ausentes

| Artefacto esperado | Estado | Consecuencia antes de integrar |
|---|---|---|
| `09_torax/region_config.py` | Ausente | No hay rutas, versiones ni identidad regional futura. |
| Configuracion de prompt regional | Ausente | No hay override, historial ni candidatas aisladas. |
| Dataset y carpeta de casos de torax | Ausentes por diseno | No se crean en esta fase. |
| Plantillas por protocolo | Ausentes | TEP, cribado, oncologia, trauma y postquirurgico no estan separados. |
| Pruebas automatizadas de torax | Ausentes | No existe caracterizacion clinica ni de integracion. |
| Ejemplos anonimizados por tipo de estudio | Ausentes | No hay corpus de regresion local reutilizable. |
| Documentacion de integracion y decision | Ausentes al inicio | Se cubre mediante los documentos de esta fase. |

## Estado frente a OPTIMUS

`04_torax` no aparece en `00_APP/region_registry.py`, no esta en el selector y no tiene rutas de persistencia. Las siete regiones activas permanecen sin cambios. No se encontraron datasets toracicos locales ni configuraciones de proveedor especificas de torax.
