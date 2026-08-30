@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo               SnipGlide Pro Launcher
echo ===================================================
echo.

if not exist .venv (
    echo [INFO] Virtual environment .venv not found. Running install.bat...
    call install.bat
    if errorlevel 1 (
        echo [ERROR] Installation failed.
        pause
        exit /b 1
    )
)

echo [INFO] Preparing Python environment...
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo [INFO] Starting SnipGlide...
"%PY_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application encountered an error and closed.
    pause
)
endlocal
