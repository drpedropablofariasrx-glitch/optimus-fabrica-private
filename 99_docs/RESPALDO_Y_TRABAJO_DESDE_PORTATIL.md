# Respaldo y trabajo desde otro equipo

## Qué guarda GitHub

El repositorio privado guarda el código de Fábrica/OPTIMUS, prompts, reglas, documentación, scripts y pruebas. No contiene credenciales, modelos, entornos Python, registros locales ni datasets privados.

## Qué debe quedarse fuera de Git

- `config/local/provider_runtime.env`: claves de proveedores.
- `data/` y `datasets/private/`: casos y resultados de trabajo.
- `models/`, `runtime/` y `.venv/`: modelos y dependencias instaladas.

Estos elementos están excluidos mediante `.gitignore`.

## Preparar el portátil

1. Instala Git y Python 3.11 o superior.
2. Clona el repositorio privado:

   ```powershell
   git clone <URL-DEL-REPOSITORIO> FABRICA_MSK
   cd FABRICA_MSK
   ```

3. Crea el entorno e instala dependencias:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   ```

4. Copia `config/local/provider_runtime.example.env` a `config/local/provider_runtime.env` y añade en ese equipo tus propias claves, sin espacios después de `=`.
5. Ejecuta `ARRANCAR_OPTIMUS.bat`.

## Rutina de trabajo segura

Al empezar en cualquiera de los dos equipos:

```powershell
git pull --rebase
```

Después de hacer cambios verificados:

```powershell
git add <archivos-cambiados>
git commit -m "Describe el cambio"
git push
```

No edites el mismo archivo en ambos equipos sin hacer primero `git pull --rebase`.

## Datos y casos

Para el buzón de casos y material de trabajo, usa una carpeta independiente en Google Drive u OneDrive, por ejemplo `OPTIMUS_DATOS`. No sincronices la carpeta completa del proyecto con Drive: Git ya sincroniza el código y usar ambos sobre los mismos archivos puede crear conflictos.

## Si una clave se expone

Revócala en el proveedor y genera otra. Después actualiza únicamente el archivo local `config/local/provider_runtime.env`; el repositorio no la enviará a GitHub.
