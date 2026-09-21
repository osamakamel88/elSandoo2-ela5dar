@echo off
setlocal
title elSandoo2 el a5dar - Prerequisites Checker
cd /d "%~dp0"

echo ========================================================
echo       elSandoo2 el a5dar - Prerequisites Diagnostic
echo              by Recode Developments
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -CheckOnly

pause
