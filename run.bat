@echo off
title elSandoo2 el a5dar - Recode Developments
cd /d "%%~dp0"
call venv\Scripts\activate.bat
start http://localhost:8501
streamlit run webui/Main.py
pause
