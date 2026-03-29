@echo off
title QuickFlix4U Launcher
color 0A

echo.
echo  =====================================
echo    QuickFlix4U - Global Movie Intel
echo  =====================================
echo.

:: Kill any existing instances
echo [1/4] Cleaning up old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM uvicorn.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: Set paths
set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend

:: Start Backend
echo [2/4] Starting Backend (port 8558)...
start "QuickFlix Backend" cmd /k "cd /d %BACKEND% && .\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8558"

:: Wait for backend to be ready
echo [3/4] Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

:: Start Frontend
echo [4/4] Starting Frontend (port 3000)...
start "QuickFlix Frontend" cmd /k "cd /d %FRONTEND% && npm run dev"

:: Wait a few seconds then open browser
echo.
echo  Waiting for frontend to compile...
timeout /t 10 /nobreak >nul

echo  Opening QuickFlix4U in your browser...
start "" "http://localhost:3000"

echo.
echo  =====================================
echo   QuickFlix4U is running!
echo   Backend:  http://127.0.0.1:8558
echo   Frontend: http://localhost:3000
echo.
echo   Close the Backend and Frontend
echo   windows to stop the app.
echo  =====================================
echo.
pause
