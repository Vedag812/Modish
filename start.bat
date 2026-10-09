@echo off
REM ============================================
REM Retail Sales Agent - Start Script (Batch)
REM Starts both Backend and Frontend servers
REM ============================================

echo.
echo ============================================
echo    RETAIL SALES AGENT - LAUNCHER
echo ============================================
echo.

set PROJECT_ROOT=%~dp0
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
set FRONTEND_PATH=%PROJECT_ROOT%\ey-frontend\E-Y

echo Starting Backend Server (FastAPI)...
start "Backend - FastAPI (Port 8000)" cmd /k "cd /d %PROJECT_ROOT% && echo. && echo ============================================ && echo    BACKEND SERVER - FastAPI && echo    http://localhost:8000 && echo ============================================ && echo. && python api_server.py"

echo Waiting for backend to start...
timeout /t 5 /nobreak > nul

echo Starting Frontend Server (Next.js)...
start "Frontend - Next.js (Port 9002)" cmd /k "cd /d %FRONTEND_PATH% && echo. && echo ============================================ && echo    FRONTEND SERVER - Next.js && echo    http://localhost:9002 && echo ============================================ && echo. && npm run dev"

echo.
echo ============================================
echo    SERVERS STARTED!
echo ============================================
echo.
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:9002
echo    API Docs: http://localhost:8000/docs
echo.
echo    Close the terminal windows to stop servers
echo.

REM Wait and open browser
timeout /t 8 /nobreak > nul
echo Opening browser...
start http://localhost:9002
