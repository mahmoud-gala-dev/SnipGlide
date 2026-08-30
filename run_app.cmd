@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo               SnipGlide Pro Launcher
echo ===================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo [INFO] Starting SnipGlide Qt6...
"%PY_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application closed with an error.
    pause
)
endlocal
