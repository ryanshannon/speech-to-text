@echo off
REM Speech-to-Text Push-to-Talk Client Startup Script
REM
REM This batch file starts the Python client for push-to-talk
REM speech recognition. Make sure the Docker server is running first!
REM
REM Usage: Double-click this file or run from command prompt

title Speech-to-Text Client

echo ================================================
echo   Speech-to-Text Push-to-Talk Client
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Change to the script directory
cd /d "%~dp0"

REM Check if required packages are installed
echo Checking dependencies...
python -c "import pyaudio, keyboard, requests, pyperclip" 2>nul
if errorlevel 1 (
    echo.
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        echo Try running: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo.
echo Starting client...
echo (Press Ctrl+C to exit)
echo.

REM Run the client
python client.py

REM If Python exits with error, pause to show the message
if errorlevel 1 (
    echo.
    echo Client exited with an error.
    pause
)
