@echo off
title JobSeeker
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primo avvio: preparazione dell'ambiente in corso...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo  Python non e' stato trovato. Installalo da https://www.python.org/downloads/
        echo  ricordandoti di spuntare "Add Python to PATH".
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo File .env creato dal modello: aprilo per configurare email e chiavi API.
    )
)

".venv\Scripts\python.exe" run.py
pause
