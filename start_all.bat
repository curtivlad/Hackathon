@echo off
echo ============================================
echo   Starting V2X Application (Full Stack)
echo ============================================
echo.

echo [0] Stopping old Python processes...
taskkill /F /IM python3.12.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul 2>&1

echo [1] Clearing Python cache...
if exist "%~dp0backend\__pycache__" rmdir /s /q "%~dp0backend\__pycache__"

echo [2] Starting Backend...
start "V2X Backend" cmd /k "cd /d %~dp0backend & rmdir /s /q __pycache__ 2>nul & python3.12 -u main.py"

echo [3] Waiting for backend...
ping -n 5 127.0.0.1 >nul 2>&1

echo [4] Starting Frontend...
start "V2X Frontend" cmd /k "cd /d %~dp0frontend & call npm install & call npm run dev"

echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
ping -n 6 127.0.0.1 >nul 2>&1
start http://localhost:3000
