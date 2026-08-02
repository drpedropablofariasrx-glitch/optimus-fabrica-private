# Como arrancar OPTIMUS

## Comando recomendado

Desde la carpeta del proyecto:

```text
python 00_APP/optimus_app.py
```

Abre luego:

```text
http://localhost:5000
```

## Comando antiguo compatible

Temporalmente sigue funcionando:

```text
python 00_APP/fabrica_abdomen.py
```

Ese archivo es solo un wrapper de compatibilidad y mostrara un aviso no bloqueante. El punto de entrada principal es `optimus_app.py`.

## Regiones disponibles

El selector regional permite trabajar con:

- Abdomen
- Columna lumbar
- Columna cervical
- Rodilla
- Mano y muñeca
- Codo
- Tobillo y pie
- Tórax

Abdomen sigue siendo la region por defecto al iniciar.

## Datos locales

Los casos se guardan en carpetas y datasets separados por region:

- `00_APP/casos_abdomen` y `00_APP/abdomen_dataset.jsonl`
- `00_APP/casos_lumbar` y `00_APP/lumbar_dataset.jsonl`
- `00_APP/casos_cervical` y `00_APP/cervical_dataset.jsonl`
- `00_APP/casos_rodilla` y `00_APP/rodilla_dataset.jsonl`
- `00_APP/casos_mano_muneca` y `00_APP/mano_muneca_dataset.jsonl`
- `00_APP/casos_codo` y `00_APP/codo_dataset.jsonl`
- `00_APP/casos_tobillo_pie` y `00_APP/tobillo_pie_dataset.jsonl`
- `00_APP/casos_torax` y `00_APP/torax_dataset.jsonl`

La configuracion de proveedores LLM sigue siendo comun.

## Para parar

En PowerShell, pulsa `Ctrl + C`.
