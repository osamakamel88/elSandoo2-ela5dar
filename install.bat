@echo off
setlocal
title elSandoo2 el a5dar - One-Click Installer
echo ========================================================
echo          elSandoo2 el a5dar - Installer
echo              by Recode Developments
echo ========================================================
echo.
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
    pause
    exit /b
)
if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
)
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat
echo [3/3] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist "config.toml" if exist "config.example.toml" copy config.example.toml config.toml >nul
echo ========================================================
echo   Setup complete! Double-click 'run.bat' to start.
echo ========================================================
pause
