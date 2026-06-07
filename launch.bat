@echo off
echo.
echo  Zenith-OS
echo  =========
echo.

cd /d "%~dp0"

REM Check if venv exists, create if not
if not exist "venv\Scripts\python.exe" (
    echo  Creating virtual environment...
    python -m venv venv
)

REM Install/upgrade dependencies
echo  Installing dependencies...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
venv\Scripts\python.exe -m pip install --quiet -r app\requirements.txt

:MENU
echo.
echo  Choose launch mode:
echo  [1] Desktop App (default)
echo  [2] Telegram Bot
echo  [3] Both
echo.
set /p choice="  Enter choice (1-3): "

if "%choice%"=="2" goto TELEGRAM
if "%choice%"=="3" goto BOTH

:DESKTOP
echo  Starting Zenith-OS Desktop...
echo.
venv\Scripts\python.exe -m app.main
goto END

:TELEGRAM
echo  Starting Zenith-OS Telegram Bot...
echo.
venv\Scripts\python.exe -m app.telegram_bot
goto END

:BOTH
echo  Starting Zenith-OS Desktop + Telegram Bot...
echo.
start "Zenith Desktop" venv\Scripts\python.exe -m app.main
venv\Scripts\python.exe -m app.telegram_bot
goto END

:END
pause
