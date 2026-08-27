@echo off
title elSandoo2 el a5dar - Recode Developments
cd /d "%~dp0"

if not exist ".streamlit" mkdir ".streamlit"
echo [general] > ".streamlit\credentials.toml"
echo email = "" >> ".streamlit\credentials.toml"

start http://localhost:8501

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m streamlit run webui/Main.py --browser.gatherUsageStats false
) else (
    python -m streamlit run webui/Main.py --browser.gatherUsageStats false
)
pause
