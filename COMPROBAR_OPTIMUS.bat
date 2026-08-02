@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: No se encontro .venv.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
if "%OPTIMUS_DATA_DIR%"=="" set OPTIMUS_DATA_DIR=data
if "%OPTIMUS_LOG_DIR%"=="" set OPTIMUS_LOG_DIR=logs
echo Ejecutando pruebas completas...
python -m unittest discover -s tests -p "test_*.py"
set TEST_RESULT=%ERRORLEVEL%
echo Ejecutando smoke test aislado...
python scripts\smoke_test.py
set SMOKE_RESULT=%ERRORLEVEL%
echo.
findstr /s /i /r "skip Skip @unittest.skip" tests\*.py >nul
if errorlevel 1 (set SKIPPED=0) else (set SKIPPED=posibles)
echo Resumen: pruebas=%TEST_RESULT% smoke=%SMOKE_RESULT% omitidas=%SKIPPED%
echo Directorio de datos configurado: %OPTIMUS_DATA_DIR%
echo Directorio de logs configurado: %OPTIMUS_LOG_DIR%
echo El smoke test informa regiones, escritura temporal y proveedor mock.
if not "%TEST_RESULT%"=="0" exit /b %TEST_RESULT%
exit /b %SMOKE_RESULT%
