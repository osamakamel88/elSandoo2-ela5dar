@echo off
setlocal
title elSandoo2 el a5dar - Auto Updater
cd /d "%~dp0"

echo ========================================================
echo          elSandoo2 el a5dar - Update Check
echo              by Recode Developments
echo ========================================================
echo.
echo Connecting to GitHub repository to check for updates...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -UpdateOnly

pause
