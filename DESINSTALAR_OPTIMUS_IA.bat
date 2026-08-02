@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DESINSTALAR_OPTIMUS_IA.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
