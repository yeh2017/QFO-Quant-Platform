@echo off
setlocal
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title QFO - Quick Start

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo ==========================================
echo      QFO - Quick Start
echo ==========================================
echo   ROOT: "%ROOT%"
echo.

rem Quick start never installs dependencies or changes configuration.
if not exist "%BACKEND%\.venv\Scripts\python.exe" goto needs_setup
if not exist "%FRONTEND%\node_modules\vite\bin\vite.js" goto needs_setup
if not exist "%BACKEND%\.env" goto needs_setup
where node.exe >nul 2>&1
if errorlevel 1 goto needs_setup

echo [1/2] Starting backend (port 8000)...
call :backend_http_ready
if not errorlevel 1 (
    echo   [INFO] Reusing the backend already running on port 8000; no new window.
    goto start_frontend
)
rem START can preserve the failed readiness probe's errorlevel on success.
ver >nul
start "QFO Backend" /D "%BACKEND%" "%ComSpec%" /d /k .venv\Scripts\python.exe -X utf8 -m uvicorn main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto fail
set "TRIES=0"
:wait_backend
call :backend_http_ready
if not errorlevel 1 goto start_frontend
set /a TRIES+=1 >nul
echo   [WAIT] Backend [%TRIES%/30] not ready yet...
if %TRIES% geq 30 (
    echo   [FAIL] Backend is not ready after 30 checks. Check the QFO Backend window for errors.
    echo   Close any other QFO instance using port 8000 and try again.
    goto fail
)
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
goto wait_backend

:start_frontend
echo   [OK] Backend is ready.
echo [2/2] Starting frontend (port 3000)...
call :frontend_http_ready
if not errorlevel 1 (
    echo   [INFO] Reusing the frontend already running on port 3000; no new window.
    goto services_ready
)
ver >nul
start "QFO Frontend" /D "%FRONTEND%" "%ComSpec%" /d /k node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3000 --strictPort
if errorlevel 1 goto fail
set "TRIES=0"
:wait_frontend
call :frontend_http_ready
if not errorlevel 1 goto services_ready
set /a TRIES+=1 >nul
echo   [WAIT] Frontend [%TRIES%/20] not ready yet...
if %TRIES% geq 20 (
    echo   [FAIL] Frontend is not ready after 20 checks. Check the QFO Frontend window for errors.
    goto fail
)
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
goto wait_frontend

:services_ready
echo   [OK] Frontend is ready.
echo.
echo   [OK] Backend and frontend are responding.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   Keep the QFO Backend and QFO Frontend windows open while using QFO.
start "" http://localhost:3000
echo   Press any key to close this launcher...
pause >nul
exit /b 0

:needs_setup
echo   [FAIL] Environment is not ready. Run run_first_time.bat first.
pause >nul
exit /b 1

:fail
echo.
echo   [FAIL] STARTUP FAILED - see the actual error above.
echo   If dependencies are missing or broken, run run_first_time.bat.
pause >nul
exit /b 1

:backend_http_ready
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2; $v=(Get-Content -Raw -LiteralPath (Join-Path $env:ROOT 'VERSION')).Trim(); if ($r.info.version -eq $v) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:frontend_http_ready
powershell -NoProfile -Command "try { $r=Invoke-WebRequest 'http://127.0.0.1:3000/' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%
