@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Installing/verifying requirements...
.venv\Scripts\python -m pip install -r requirements.txt
echo Running app...
.venv\Scripts\python app.py
pause
