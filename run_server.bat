@echo off
echo Starting SHL Assessment Recommender...

:: Move to project folder
cd /d "%~dp0"

:: Create virtual environment only if missing
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: creating virtual environment...
    python -m venv .venv
)

:: Install dependencies silently
".venv\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1

:: Start Backend API and Frontend static server
start cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: Open Frontend in browser
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"

echo Backend API is starting at http://127.0.0.1:8000
echo Frontend will be available at http://127.0.0.1:8000
echo.
echo Note: Frontend and backend run from the same FastAPI server in this project.
