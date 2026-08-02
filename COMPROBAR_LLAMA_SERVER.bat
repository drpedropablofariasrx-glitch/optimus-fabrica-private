@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0COMPROBAR_LLAMA_SERVER.ps1" %*
exit /b %ERRORLEVEL%
