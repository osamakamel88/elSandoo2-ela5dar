@echo off
title elSandoo2 el a5dar - Recode Developments
cd /d "%~dp0"

rem Add portable FFmpeg to PATH if present
if exist "%~dp0bin\ffmpeg\ffmpeg.exe" (
    set "PATH=%~dp0bin\ffmpeg;%PATH%"
)

rem Suppress Streamlit email prompt
if not exist ".streamlit" mkdir ".streamlit"
if not exist ".streamlit\credentials.toml" (
    echo [general] > ".streamlit\credentials.toml"
    echo email = "" >> ".streamlit\credentials.toml"
)

rem Locate Python in virtual environment
set "PY_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo ========================================================
    echo [ERROR] Virtual environment not found!
    echo Please run 'install.bat' first to set up prerequisites.
    echo ========================================================
    pause
    exit /b 1
)

start http://localhost:8501

"%PY_EXE%" -m streamlit run webui/Main.py --browser.gatherUsageStats false --server.port 8501

pause
