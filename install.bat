@echo off
setlocal
cd /d "%~dp0"
title SnipGlide Pro - Installer

echo ======================================================
echo    SnipGlide Pro - Installer and Setup Script
echo ======================================================
echo.

REM 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto NO_PYTHON

echo [1/4] Python detected:
python --version

REM 2. Create Virtual Environment if not exists
echo.
echo [2/4] Setting up Virtual Environment...
if exist ".venv\Scripts\python.exe" goto VENV_EXISTS
echo Creating virtual environment...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 goto VENV_FAIL
echo Virtual environment created successfully.
goto INSTALL_REQ

:VENV_EXISTS
echo Virtual environment already exists.

:INSTALL_REQ
REM 3. Install requirements
echo.
echo [3/4] Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 goto REQ_FAIL

REM 4. Create Shortcut
echo.
echo [4/4] Creating Desktop Shortcut...
powershell -ExecutionPolicy Bypass -File "make_shortcut.ps1"

echo.
echo ======================================================
echo    SUCCESS: Installation completed successfully!
echo    SnipGlide Pro is ready to use.
echo ======================================================
echo.

REM Launch in background
echo Launching SnipGlide Pro...
start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:NO_PYTHON
echo.
echo [ERROR] Python is not installed or not in PATH!
echo Please install Python 3.10+ from python.org and check Add to PATH.
echo.
pause
exit /b 1

:VENV_FAIL
echo.
echo [ERROR] Failed to create virtual environment.
echo.
pause
exit /b 1

:REQ_FAIL
echo.
echo [ERROR] Failed to install dependencies. Please check your internet connection.
echo.
pause
exit /b 1
