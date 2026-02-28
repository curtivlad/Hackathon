@echo off
cd /d "%~dp0backend"

echo Stopping old Python processes...
taskkill /F /IM python3.12.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul 2>&1

echo Clearing cache...
if exist __pycache__ rmdir /s /q __pycache__

echo ============================================
echo   Starting V2X Backend (FastAPI + Uvicorn)
echo   Server: http://localhost:8000
echo ============================================
echo.
python3.12 -u main.py
echo.
echo Backend stopped with exit code: %ERRORLEVEL%
pause
