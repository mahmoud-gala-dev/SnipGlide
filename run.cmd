@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo Starting SnipGlide Qt6...
"%PY_EXE%" app.py

if errorlevel 1 (
    echo.
    echo Application closed with an error.
    pause
)
endlocal
