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
".venv\Scripts\python.exe" main.py
pause
