@echo off
cls
title Smart Medical System
color 0A
echo.
echo ========================================
echo    SMART MEDICAL SYSTEM
echo ========================================
echo.
echo Starting server...
echo.

cd /d "%~dp0"

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not installed!
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)
echo OK - Python found

echo.
echo [2/3] Checking dependencies...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo WARNING: Could not install all dependencies
    echo Attempting to continue anyway...
) else (
    echo OK - Dependencies installed
)

echo.
echo [3/3] Starting server...
echo.
echo ========================================
echo    SERVER STARTED!
echo ========================================
echo.
timeout /t 2 /nobreak >nul

echo Starting Flask server...
python app.py

echo.
echo Server stopped.
pause

