@echo off
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo venv fail.
    pause
    exit /b 1
)
echo venv activated.
python main.py
pause