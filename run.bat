@echo off
cd /d "%~dp0"

if not exist .venv (
    call install.bat
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    start "" pythonw app.py
)
exit
