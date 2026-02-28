@echo off
cd /d "%~dp0frontend"
echo ============================================
echo   Installing frontend dependencies...
echo ============================================
call npm install
echo.
echo ============================================
echo   Starting Frontend (Vite + React)
echo   Open: http://localhost:3000
echo ============================================
echo.
call npm run dev
pause
