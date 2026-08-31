@echo off
setlocal
title JobSeeker
cd /d "%~dp0"

rem ---------------------------------------------------------------- ambiente
rem Il primo avvio prepara un ambiente Python isolato dentro la cartella, cosi'
rem le librerie non finiscono in mezzo a quelle di sistema.

if not exist ".venv\Scripts\python.exe" (
    echo Primo avvio: preparazione dell'ambiente in corso, un minuto...
    python -m venv .venv

    rem Non basta guardare l'errorlevel: il segnaposto di Python del Microsoft
    rem Store esce senza errore, apre il negozio e non crea proprio niente.
    rem L'unica prova che serva e' che l'eseguibile esista.
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo   Python non e' utilizzabile.
        echo.
        echo   Se si e' aperto il Microsoft Store, chiudilo: quello e' un
        echo   segnaposto, non Python. Installalo da python.org/downloads
        echo   ricordandoti di spuntare "Add Python to PATH", poi riprova.
        echo.
        pause
        exit /b 1
    )
)

rem ------------------------------------------------------------- dipendenze
rem Le librerie si reinstallano quando `requirements.txt` cambia, non solo al
rem primo avvio. Prima bastava che la cartella `.venv` esistesse perche' pip
rem non girasse mai piu': dopo un aggiornamento dell'applicazione mancavano le
rem librerie nuove, e l'unico segno era una funzione che non andava.

set "IMPRONTA="
for /f "skip=1 delims=" %%r in ('certutil -hashfile requirements.txt MD5') do (
    if not defined IMPRONTA set "IMPRONTA=%%r"
)
set "PRECEDENTE="
if exist ".venv\requisiti.md5" set /p PRECEDENTE=<".venv\requisiti.md5"

if not "%IMPRONTA%"=="%PRECEDENTE%" (
    echo Installazione delle librerie in corso...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo.
        echo   Installazione delle librerie non riuscita.
        echo.
        echo   Di solito e' la connessione. Se il problema resta, cancella la
        echo   cartella .venv e riavvia questo file: viene rifatta da capo.
        echo.
        pause
        exit /b 1
    )
    >".venv\requisiti.md5" echo %IMPRONTA%
    echo Librerie pronte.
)

rem ------------------------------------------------------------------ avvio
rem Il file .env non serve piu' per configurare: utente, password e chiavi si
rem impostano dal browser alla prima apertura. Si copia comunque, perche' chi
rem preferisce metterle li' puo' continuare a farlo.
if not exist ".env" (
    if exist ".env.example" copy ".env.example" ".env" >nul
)

".venv\Scripts\python.exe" run.py
if errorlevel 1 (
    echo.
    echo   JobSeeker si e' chiuso con un errore. Il messaggio qui sopra dice
    echo   cosa e' successo.
    echo.
)
pause
