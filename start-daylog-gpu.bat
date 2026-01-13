@echo off
echo ================================================
echo Starting Daylog with GPU acceleration
echo Using Python 3.12 + faster-whisper + CUDA
echo ================================================
echo.

cd /d "%~dp0"

echo Checking if venv312 exists...
if not exist "venv312\Scripts\python.exe" (
    echo ERROR: venv312 not found!
    echo Please make sure you're in the correct directory.
    pause
    exit /b 1
)

echo Starting GUI...
echo.
venv312\Scripts\python.exe -m daylog.gui

if errorlevel 1 (
    echo.
    echo ================================================
    echo ERROR: GUI failed to start or crashed
    echo Check the error message above
    echo ================================================
    pause
)
