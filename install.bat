@echo off
setlocal
title elSandoo2 el a5dar - Installer & Updater
cd /d "%~dp0"

echo ========================================================
echo          elSandoo2 el a5dar - Installer
echo              by Recode Developments
echo ========================================================
echo.
echo Connecting to GitHub source and verifying prerequisites...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Setup encountered an issue (Exit code: %errorlevel%).
    echo Please check the output above.
    pause
)
