@echo off
REM Zenith-OS Launcher

echo.
echo  Zenith-OS
echo  =========
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

REM Check dependencies
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r app\requirements.txt --quiet
)

REM Launch app
echo Starting Zenith-OS...
echo.
python -m app.main

pause
