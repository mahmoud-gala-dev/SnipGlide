@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================
echo    SnipGlide Pro - Installer ^& Setup Script
echo    تثبيت وإعداد سكريبت وبيئة SnipGlide
echo ======================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo [خطأ] بايثون غير مثبت أو غير مضاف إلى متغيرات النظام PATH.
    echo Please install Python 3.10+ from python.org and check "Add to PATH".
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Setting up Virtual Environment (.venv)...
if not exist .venv (
    echo Creating new virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)

echo.
echo [3/4] Upgrading PIP and installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install some dependencies. Please check your internet connection.
    pause
    exit /b 1
)

echo.
echo [4/4] Verifying installation and Creating Desktop Shortcut...
.venv\Scripts\python.exe -c "import PySide6, pynput, PIL, openpyxl, pygments, cryptography, yaml, sounddevice, soundfile, numpy; print('All core packages imported successfully!')"
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some packages failed verification.
) else (
    echo [INFO] Creating Desktop Shortcut...
    powershell -ExecutionPolicy Bypass -File .\make_shortcut.ps1
    echo.
    echo ======================================================
    echo    SUCCESS! تم التثبيت بنجاح وجاهز للتشغيل
    echo    يمكنك تشغيل البرنامج الآن عبر اختصار سطح المكتب مباشرة
    echo    أو الضغط على Ctrl + PrintScreen من أي مكان لفتحه
    echo ======================================================
)

echo.
echo Launching SnipGlide in background...
start "" .venv\Scripts\pythonw.exe app.py
exit /b 0
