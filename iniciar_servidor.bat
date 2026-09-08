@echo off
cd /d "%~dp0"

if not defined SISTEMA_MUSEO_SECRET_KEY (
    echo ERROR: Falta configurar SISTEMA_MUSEO_SECRET_KEY.
    pause
    exit /b 1
)

venv\Scripts\python.exe servidor.py

pause