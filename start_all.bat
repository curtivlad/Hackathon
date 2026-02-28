@echo off
echo ============================================
echo   Starting V2X Application (Full Stack)
echo ============================================
echo.

echo [1/2] Starting Backend (FastAPI) in a new window...
start "V2X Backend" cmd /c "cd /d "%~dp0backend" && echo Starting backend on http://localhost:8000 ... && echo. && python3.12 -u main.py && echo. && echo Backend stopped. && pause"

echo [2/2] Waiting 3 seconds for backend to start...
timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend (Vite + React) in a new window...
start "V2X Frontend" cmd /c "cd /d "%~dp0frontend" && echo Installing dependencies... && call npm install && echo. && echo Starting frontend on http://localhost:3000 ... && echo. && call npm run dev && echo. && echo Frontend stopped. && pause"

echo.
echo ============================================
echo   Both servers are starting!
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
echo   Open http://localhost:3000 in your browser.
echo   Close this window anytime - servers will
echo   keep running in their own windows.
echo ============================================
echo.
timeout /t 5 /nobreak >nul
start http://localhost:3000

