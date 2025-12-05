@echo off
chcp 1251 >nul

call "%~dp0.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo venv fail.
    pause
    exit /b 1
)
echo venv activated.

"%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
