@echo off
setlocal
cd /d "%~dp0"
set "BACKEND=%~dp0backend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

netstat -ano | findstr /r /c:"127.0.0.1:8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo [error] Port 8000 is already in use - close the other backend first.
    pause & exit /b 1
)
netstat -ano | findstr /r /c:"127.0.0.1:5173 .*LISTENING" >nul
if not errorlevel 1 (
    echo [error] Port 5173 is already in use - close the other frontend first.
    pause & exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [error] npm not found. Install Node.js 18+ from https://nodejs.org
    pause & exit /b 1
)

"%PY%" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [setup] Backend virtual environment missing or broken - rebuilding it...
    if exist "%BACKEND%\.venv" rmdir /s /q "%BACKEND%\.venv"
    py -3 -m venv "%BACKEND%\.venv" 2>nul || python -m venv "%BACKEND%\.venv"
    if errorlevel 1 (
        echo [error] Could not create the venv. Is Python installed and on PATH?
        pause & exit /b 1
    )
    "%PY%" -m pip install -q -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo [error] pip install failed.
        pause & exit /b 1
    )
)

if not exist "%BACKEND%\.env" (
    echo [warn] No backend\.env found. Copy backend\.env.example to backend\.env and add your API key.
)

start "MARKET.EXE backend :8000" /d "%BACKEND%" cmd /k ""%PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

start "MARKET.EXE frontend :5173" /d "%~dp0frontend" cmd /k "(if not exist node_modules npm install) && npm run dev"

echo Starting... the browser opens in a few seconds.
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:5173
