@echo off
setlocal

echo ============================================
echo  Building Speech-to-Text Client Executable
echo ============================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and try again
    exit /b 1
)

:: Create build environment
echo [1/4] Creating virtual environment...
if exist build-env rmdir /s /q build-env
python -m venv build-env
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    exit /b 1
)

:: Activate and install dependencies
echo [2/4] Installing dependencies...
call build-env\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    exit /b 1
)

:: Install PyInstaller
echo [3/4] Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    exit /b 1
)

:: Build executable
echo [4/4] Building executable...
pyinstaller --onefile --name speech-to-text-client --icon=speech2textV3.ico client.py
if errorlevel 1 (
    echo ERROR: Build failed
    exit /b 1
)

:: Copy config file to dist folder
echo.
echo Copying config file...
copy config.json dist\ >nul 2>&1

:: Cleanup
echo Cleaning up build artifacts...
rmdir /s /q build 2>nul
rmdir /s /q build-env 2>nul
del /q *.spec 2>nul

echo.
echo ============================================
echo  Build complete!
echo ============================================
echo.
echo Executable: dist\speech-to-text-client.exe
echo Config:     dist\config.json
echo.
echo To run: cd dist ^& speech-to-text-client.exe
echo.

endlocal
