@echo off
setlocal
cd /d "%~dp0"
if exist "config\local\llama_runtime.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("config\local\llama_runtime.env") do if not "%%A"=="" set "%%A=%%B"
)
if exist "config\local\provider_runtime.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("config\local\provider_runtime.env") do if not "%%A"=="" set "%%A=%%B"
)
if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: No se encontro .venv. Cree el entorno virtual antes de arrancar.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Faltan dependencias minimas. Ejecute: pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"
if "%OPTIMUS_DATA_DIR%"=="" set OPTIMUS_DATA_DIR=data
if "%OPTIMUS_LOG_DIR%"=="" set OPTIMUS_LOG_DIR=logs
if "%OPTIMUS_HOST%"=="" set OPTIMUS_HOST=127.0.0.1
if "%OPTIMUS_PORT%"=="" set OPTIMUS_PORT=5000
if "%OPENAI_MODEL%"=="" set OPENAI_MODEL=gpt-4.1-mini
if "%DEEPSEEK_MODEL%"=="" set DEEPSEEK_MODEL=deepseek-chat
rem Evita que una clave pegada por error en el campo de modelo se use como nombre de modelo.
if /I "%DEEPSEEK_MODEL:~0,3%"=="sk-" set DEEPSEEK_MODEL=deepseek-chat
echo OPTIMUS disponible en http://%OPTIMUS_HOST%:%OPTIMUS_PORT%
echo Datos: %OPTIMUS_DATA_DIR%  Logs: %OPTIMUS_LOG_DIR%
echo llama-server no se inicia automaticamente.
python 00_APP\optimus_app.py
pause
