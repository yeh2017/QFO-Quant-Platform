@echo off
setlocal
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title QFO Launcher

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV_PYTHON=%BACKEND%\.venv\Scripts\python.exe"

echo ==========================================
echo      QFO - Windows Launcher
echo ==========================================
echo   ROOT: %ROOT%
echo.

echo [1/5] Checking Python 3.12 or newer...
call :select_python
if not defined PYTHON_EXE (
    echo   [FAIL] Python 3.12 or newer was not found. Install Python and run again.
    goto fail
)
"%PYTHON_EXE%" --version
echo   [OK] Using: %PYTHON_EXE%

echo [2/5] Checking Node.js 22.12 or newer...
node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0]>22 || v[0]===22 && v[1]>=12 ? 0 : 1)" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Node.js 22.12 or newer is required. Install it and run again.
    goto fail
)
node --version

echo [3/5] Checking backend environment...
if not exist "%VENV_PYTHON%" goto create_venv
"%VENV_PYTHON%" -X utf8 -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 goto rebuild_venv
goto check_backend

:rebuild_venv
echo   [INFO] Keeping the incompatible environment as a backup...
ren "%BACKEND%\.venv" ".venv-backup-%RANDOM%"
if errorlevel 1 goto fail

:create_venv
"%PYTHON_EXE%" -X utf8 -m venv "%BACKEND%\.venv"
if errorlevel 1 goto fail

:check_backend
"%VENV_PYTHON%" -X utf8 -m pip --version >nul 2>&1
if not errorlevel 1 goto check_backend_imports
"%VENV_PYTHON%" -X utf8 -m ensurepip --upgrade
if errorlevel 1 goto fail

:check_backend_imports
call :backend_ready >nul 2>&1
if errorlevel 1 call :install_backend_deps
if errorlevel 1 goto fail
call :backend_ready
if errorlevel 1 (
    echo   [FAIL] Backend dependencies could not be imported. See the error above.
    goto fail
)
echo   [OK] Backend dependencies ready

echo [4/5] Checking frontend dependencies...
if not exist "%FRONTEND%\package.json" (
    echo   [FAIL] frontend\package.json is missing. Extract the complete package.
    goto fail
)
call :frontend_ready
if errorlevel 1 call :install_frontend_deps
if errorlevel 1 goto fail
call :frontend_ready
if errorlevel 1 (
    echo   [FAIL] Vite could not start. See the error above.
    goto fail
)
echo   [OK] Frontend dependencies ready

if exist "%BACKEND%\.env" goto env_ready
copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
if errorlevel 1 (
    echo   [FAIL] Could not create .env from .env.example.
    goto fail
)
echo   [INFO] Configure your Tushare Token in Settings after startup.
:env_ready
echo   [OK] .env exists
if /i "%~1"=="--prepare-only" exit /b 0

echo [5/5] Starting services...
if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
call :backend_http_ready
if not errorlevel 1 goto start_frontend
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Start-Process -FilePath $env:VENV_PYTHON -ArgumentList @('-X','utf8','-m','uvicorn','main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $env:BACKEND -WindowStyle Hidden -RedirectStandardOutput (Join-Path $env:BACKEND 'logs\backend.stdout.log') -RedirectStandardError (Join-Path $env:BACKEND 'logs\backend.stderr.log')"
if errorlevel 1 goto fail
set "TRIES=0"
:wait_backend
call :backend_http_ready
if not errorlevel 1 goto start_frontend
set /a TRIES+=1 >nul
if %TRIES% geq 30 (
    echo   [FAIL] Backend is not ready. Check backend\logs\backend.stderr.log.
    echo   Close any other QFO instance using port 8000 and try again.
    goto fail
)
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
goto wait_backend

:start_frontend
call :frontend_http_ready
if not errorlevel 1 goto services_ready
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','3000','--strictPort') -WorkingDirectory $env:FRONTEND -WindowStyle Hidden -RedirectStandardOutput (Join-Path $env:BACKEND 'logs\frontend.stdout.log') -RedirectStandardError (Join-Path $env:BACKEND 'logs\frontend.stderr.log')"
if errorlevel 1 goto fail
set "TRIES=0"
:wait_frontend
call :frontend_http_ready
if not errorlevel 1 goto services_ready
set /a TRIES+=1 >nul
if %TRIES% geq 20 (
    echo   [FAIL] Frontend is not ready. Check backend\logs\frontend.stderr.log.
    goto fail
)
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
goto wait_frontend

:services_ready
echo.
echo   [OK] Backend and frontend are responding.
echo   Open: http://127.0.0.1:3000
start "" http://127.0.0.1:3000
echo   Press any key to close this launcher...
pause >nul
exit /b 0

:fail
echo.
echo   STARTUP FAILED - see the actual error above.
if /i "%~1"=="--prepare-only" exit /b 1
pause
exit /b 1

:select_python
set "PYTHON_EXE="
call :try_python "%VENV_PYTHON%"
if defined PYTHON_EXE exit /b 0
for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%p"
if defined PYTHON_EXE exit /b 0
for /f "delims=" %%p in ('where python 2^>nul') do call :try_python "%%p"
exit /b 0

:try_python
if defined PYTHON_EXE exit /b 0
if not exist "%~1" exit /b 1
"%~1" -X utf8 -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_EXE=%~1"
exit /b 0

:backend_ready
"%VENV_PYTHON%" -X utf8 -c "import uvicorn, fastapi, pandas, numpy, sqlalchemy, jinja2, structlog, scipy, sklearn, akshare, tushare, baostock, dotenv"
exit /b %errorlevel%

:frontend_ready
pushd "%FRONTEND%"
node node_modules/vite/bin/vite.js --version >nul 2>&1
if errorlevel 1 (
    popd
    exit /b 1
)
popd
exit /b 0

:install_backend_deps
echo   [INFO] Installing backend dependencies with UTF-8...
"%VENV_PYTHON%" -X utf8 -m pip install -r "%BACKEND%\requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/
if not errorlevel 1 exit /b 0
echo   [INFO] Aliyun mirror failed; trying Tencent Cloud mirror...
"%VENV_PYTHON%" -X utf8 -m pip install -r "%BACKEND%\requirements.txt" -i https://mirrors.cloud.tencent.com/pypi/simple/
if not errorlevel 1 exit /b 0
echo   [INFO] Both mirrors failed; trying official PyPI...
"%VENV_PYTHON%" -X utf8 -m pip install -r "%BACKEND%\requirements.txt" -i https://pypi.org/simple/
if not errorlevel 1 exit /b 0
echo   [FAIL] Dependency installation failed on all three sources. See pip output above.
echo   If you see "Failed to resolve" or "getaddrinfo failed", check your network and DNS.
echo   Try another network and run this launcher again.
exit /b 1

:install_frontend_deps
pushd "%FRONTEND%"
call npm ci --no-fund
if not errorlevel 1 (
    popd
    exit /b 0
)
echo   [INFO] Retrying npm with npmmirror...
call npm ci --no-fund --registry=https://registry.npmmirror.com
if not errorlevel 1 (
    popd
    exit /b 0
)
popd
echo   [FAIL] Frontend installation failed. See npm output for the cause.
exit /b 1

:backend_http_ready
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2; $v=(Get-Content -Raw -LiteralPath (Join-Path $env:ROOT 'VERSION')).Trim(); if ($r.info.version -eq $v) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:frontend_http_ready
powershell -NoProfile -Command "try { $r=Invoke-WebRequest 'http://127.0.0.1:3000/' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%
