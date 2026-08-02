# ARRANQUE_OPTIMUS_WINDOWS

1. Abra PowerShell en la raiz de `FABRICA_MSK`.
2. Si no existe `.venv`, cree el entorno: `python -m venv .venv`.
3. Activelo: `.venv\Scripts\Activate.ps1`.
4. Instale dependencias de forma explicita: `pip install -r requirements.txt`.
5. Ejecute `COMPROBAR_OPTIMUS.bat` para pruebas y smoke test aislado.
6. Ejecute `ARRANCAR_OPTIMUS.bat` para iniciar Flask.
7. Abra `http://127.0.0.1:5000` salvo que configure otro host o puerto.
8. Cierre Flask con `Ctrl+C` en la consola visible.

Datos: el comportamiento historico conserva `00_APP/casos_<region>` y datasets regionales. Al definir `OPTIMUS_DATA_DIR`, los nuevos datos se escriben en esa carpeta. Logs: `logs/optimus.log` o `OPTIMUS_LOG_DIR`.

Si el puerto esta ocupado, defina temporalmente `OPTIMUS_PORT=5001` antes de ejecutar el arranque. Los scripts no instalan paquetes, no descargan modelos y no arrancan llama-server.
