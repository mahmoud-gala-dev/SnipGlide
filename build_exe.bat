@echo off
cd /d "%~dp0"
title Build SnipGlide EXE
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Upgrading pip...
.venv\Scripts\python -m pip install --upgrade pip
echo Installing requirements...
.venv\Scripts\python -m pip install -r requirements.txt
echo Installing pyinstaller...
.venv\Scripts\python -m pip install pyinstaller
echo Building executable...
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name SnipGlide app.py
echo.
echo Build complete: dist\SnipGlide.exe
pause
