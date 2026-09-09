@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build SnipGlide EXE

echo ======================================================
echo    SnipGlide - Building Executable (EXE)
echo    بناء وتجميع ملف التشغيل المستقل
echo ======================================================
echo.
taskkill /F /IM SnipGlide.exe >nul 2>&1

if not exist .venv (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
)

echo [1/3] Verifying and installing requirements...
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller

echo.
echo [2/3] Building standalone executable with PyInstaller...
.venv\Scripts\pyinstaller --noconfirm --clean SnipGlide.spec


if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ======================================================
echo [3/3] Build complete successfully!
echo Executable located at: dist\SnipGlide.exe
echo تم إنشاء ملف التشغيل بنجاح داخل مجلد dist
echo ======================================================
pause
