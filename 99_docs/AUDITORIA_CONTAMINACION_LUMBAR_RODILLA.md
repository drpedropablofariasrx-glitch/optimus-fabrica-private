# AUDITORIA_CONTAMINACION_LUMBAR_RODILLA

**Proyecto:** OPTIMUS  
**Alcance:** presencia de parametros patelofemorales en lumbar y rodilla  
**Fecha:** 2026-07-18  
**Estado:** auditoria. No se han modificado archivos clinicos.

---

## Parametros revisados

- Insall-Salvati
- Caton-Deschamps
- TT-TG
- CDI

Estos parametros pertenecen al ambito de rodilla/patelofemoral, no a RM de columna lumbar.

### Confirmacion clinica

- **Insall-Salvati:** indice de altura rotuliana.
- **Caton-Deschamps / CDI:** indice de altura rotuliana.
- **TT-TG:** distancia tuberosidad tibial - surco troclear, usada en inestabilidad patelofemoral.

No son parametros propios de columna lumbar. Su presencia en lumbar es contaminacion regional.

---

## Busqueda realizada

Se revisaron:

- `02_lumbar/SYSTEM_PROMPT_lumbar.txt`
- `02_lumbar/validador_lumbar.py`
- `02_lumbar/REGLAS_LUMBAR_MAESTRAS.md`
- archivos de `05_rodilla`

Resultado: las menciones aparecen en lumbar y no aparecen actualmente en los archivos de rodilla.

---

## Hallazgos en lumbar

### 1. `SYSTEM_PROMPT_lumbar.txt`

Mencion contaminante:

```text
- Indices cuantitativos (Insall-Salvati, Caton-Deschamps, TT-TG, CDI): en el informe PACS
  redondear a 1 decimal; conservar el valor exacto solo en el dataset interno.
```

Debe retirarse de lumbar.

### 2. `validador_lumbar.py`

Mencion contaminante en `regla_D3`:

```python
def regla_D3(texto: str) -> List[Flag]:
    """
    Indices cuantitativos (Insall-Salvati, Caton-Deschamps, TT-TG, CDI) en el
    informe PACS deben ir redondeados a 1 decimal, no con mas precision.
    """
```

Y en la lista de indices:

```python
indices = ["insall-salvati", "insall salvati", "caton-deschamps", "caton deschamps", "tt-tg", "cdi"]
```

Debe retirarse de lumbar.

### 3. `REGLAS_LUMBAR_MAESTRAS.md`

Mencion contaminante:

```text
| D3 | Indices cuantitativos (Insall-Salvati, Caton-Deschamps, TT-TG, CDI...): conservar valor exacto en el dataset interno; redondear a 1 decimal en el informe PACS | "Conservar el valor exacto en el dataset interno (1,19). Redondear a una cifra decimal en el informe PACS (1,2)" | L19562 |
```

Debe retirarse o reclasificarse como nota de contaminacion historica, no como regla lumbar activa.

---

## Hallazgos en rodilla

En los archivos actuales de rodilla no hay menciones a:

- Insall-Salvati
- Caton-Deschamps
- TT-TG
- CDI

Archivos revisados:

- `05_rodilla/REGLAS_RODILLA_MAESTRAS.md`
- `05_rodilla/SYSTEM_PROMPT_rodilla.txt`
- `05_rodilla/validador_rodilla.py`

Esto significa que la regla esta en el sitio equivocado y ademas no esta formalizada en el sitio correcto.

---

## Que debe retirarse de lumbar

Retirar exactamente:

1. En `02_lumbar/SYSTEM_PROMPT_lumbar.txt`, la regla dura completa de indices cuantitativos patelofemorales:

```text
- Indices cuantitativos (Insall-Salvati, Caton-Deschamps, TT-TG, CDI): en el informe PACS
  redondear a 1 decimal; conservar el valor exacto solo en el dataset interno.
```

2. En `02_lumbar/validador_lumbar.py`, retirar `regla_D3` completa y quitarla de `TODAS_LAS_REGLAS`.

3. En `02_lumbar/REGLAS_LUMBAR_MAESTRAS.md`, retirar o mover fuera de reglas activas la fila D3. Recomendacion documental: dejar una nota breve en observaciones indicando que esa fila fue contaminacion de rodilla y no debe aplicarse a lumbar.

4. Renumeracion: no es obligatorio renumerar inmediatamente. Para trazabilidad, se puede dejar D4 como D4 y marcar D3 como retirada por contaminacion. Si se renumera, hacerlo una sola vez y actualizar pruebas.

---

## Donde debe mantenerse en rodilla

La idea general "valor exacto interno vs valor redondeado visible" es valida como regla de dataset, pero los nombres Insall-Salvati, Caton-Deschamps, TT-TG y CDI deben vivir en rodilla.

Propuesta:

1. En `05_rodilla/REGLAS_RODILLA_MAESTRAS.md`, anadir una regla dura o de formato cuantitativo:

```text
Indices patelofemorales (Insall-Salvati, Caton-Deschamps/CDI, TT-TG): conservar valor exacto en el dataset interno; en el informe PACS redondear a 1 decimal cuando se muestren.
```

2. En `05_rodilla/SYSTEM_PROMPT_rodilla.txt`, mantenerlo como regla dura/formato:

```text
- Indices patelofemorales (Insall-Salvati, Caton-Deschamps/CDI, TT-TG): redondear a 1 decimal en el informe visible; conservar el valor exacto solo en el dataset interno.
```

3. En `05_rodilla/validador_rodilla.py`, si se decide activarlo, crear una regla equivalente a la actual `regla_D3` lumbar, pero limitada a informes de rodilla y con nombres patelofemorales. No implementarla hasta tener casos de prueba.

---

## Riesgo de no corregir

Si se mantiene en lumbar:

- el prompt lumbar puede instruir al modelo con anatomia ajena;
- el validador lumbar puede disparar flags irrelevantes;
- el dataset lumbar puede quedar contaminado con metadatos de rodilla;
- la futura arquitectura multirregion heredaria una regla global falsa.

---

## Prioridad recomendada

1. Retirar la regla de indices patelofemorales de lumbar.
2. Documentar en lumbar que fue contaminacion regional.
3. Incorporar la regla en rodilla como pendiente de activacion.
4. Activar validador de rodilla solo despues de casos de prueba con esos indices.

