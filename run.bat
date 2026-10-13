@echo off
title Python Interview Prep App
cd /d "%~dp0"

echo ===================================================
echo Starting Flask App...
echo Opening in default browser at http://127.0.0.1:5000
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    start "" "http://127.0.0.1:5000"
    ".venv\Scripts\python.exe" run_app.py
) else (
    start "" "http://127.0.0.1:5000"
    python run_app.py
)
pause
