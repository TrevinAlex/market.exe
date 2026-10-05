@echo off
rem Start the whole MARKET.EXE app: backend (FastAPI :8000) + frontend (Vite :5173).
rem Double-click this file. Each server opens in its own window; close a window
rem (or press Ctrl+C in it) to stop that server.
setlocal
cd /d "%~dp0"
set "BACKEND=%~dp0backend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

rem The frontend's Vite proxy is fixed to :8000, so the backend must use 8000.
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

rem Backend venv: rebuild it if it is missing or broken (e.g. after a folder move).
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

rem Backend: call python -m uvicorn directly - no activation, no launcher paths to break.
start "MARKET.EXE backend :8000" /d "%BACKEND%" cmd /k ""%PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

rem Frontend: install deps on first run, then start Vite.
start "MARKET.EXE frontend :5173" /d "%~dp0frontend" cmd /k "(if not exist node_modules npm install) && npm run dev"

rem Give both servers a moment, then open the app.
echo Starting... the browser opens in a few seconds.
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:5173
