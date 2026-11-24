@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" (
  echo Falta el archivo .env. Revisa .env.example y crea tu configuracion privada.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno .venv. Sigue primero las instrucciones de README.md.
  pause
  exit /b 1
)
choice /c SN /n /m "Permitir que Aiko escuche el microfono localmente al iniciar [S/N]? "
if errorlevel 2 goto backend
set "AIKO_APPS="
set "AIKO_GMAIL="
choice /c SN /n /m "Permitir que Aiko abra aplicaciones y paginas por voz [S/N]? "
if not errorlevel 2 set "AIKO_APPS=--apps"
choice /c SN /n /m "Permitir que Aiko consulte tu bandeja de Gmail por voz [S/N]? "
if not errorlevel 2 set "AIKO_GMAIL=--gmail"
start "Aiko - escucha local" "%~dp0.venv\Scripts\python.exe" -m voice.desktop %AIKO_APPS% %AIKO_GMAIL%

:backend
".venv\Scripts\python.exe" main.py
pause
