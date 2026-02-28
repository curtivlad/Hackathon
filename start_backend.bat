@echo off
cd /d "%~dp0backend"
echo ============================================
echo   Starting V2X Backend (FastAPI + Uvicorn)
echo   Server: http://localhost:8000
echo ============================================
echo.
python3.12 -u main.py
echo.
echo Backend stopped with exit code: %ERRORLEVEL%
pause
