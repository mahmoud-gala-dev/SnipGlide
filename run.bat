@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .venv (
    echo [INFO] Virtual environment not found. Running install.bat first...
    call install.bat
    exit /b 0
)

echo [INFO] Launching SnipGlide...
.venv\Scripts\python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)
