@echo off
REM Zenith-OS Build Script
REM Builds executable and MSI installer

echo.
echo  Zenith-OS Build
echo  ===============
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Install dependencies
echo [1/3] Installing dependencies...
pip install -r app\requirements.txt --quiet
pip install pyinstaller --quiet

REM Build executable
echo.
echo [2/3] Building executable...
pyinstaller installer\zenith.spec --clean --noconfirm

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

REM Copy additional files
echo Copying additional files...
xcopy /E /Y /Q config dist\Zenith-OS\config >nul 2>&1
xcopy /E /Y /Q skills dist\Zenith-OS\skills >nul 2>&1
xcopy /E /Y /Q core dist\Zenith-OS\core >nul 2>&1
xcopy /E /Y /Q memory dist\Zenith-OS\memory >nul 2>&1
xcopy /E /Y /Q tools dist\Zenith-OS\tools >nul 2>&1
xcopy /E /Y /Q research dist\Zenith-OS\research >nul 2>&1
xcopy /E /Y /Q filters dist\Zenith-OS\filters >nul 2>&1
xcopy /E /Y /Q sandbox dist\Zenith-OS\sandbox >nul 2>&1
xcopy /E /Y /Q tts dist\Zenith-OS\tts >nul 2>&1
copy /Y zenith.md dist\Zenith-OS >nul 2>&1
copy /Y LICENSE dist\Zenith-OS >nul 2>&1

REM Build MSI if WiX available
echo.
echo [3/3] Checking for WiX Toolset...
where candle >nul 2>&1
if errorlevel 1 (
    echo [SKIP] WiX not found. Skipping MSI build.
    echo        Install WiX: https://wixtoolset.org/
    goto :done
)

echo Building MSI installer...
candle.exe installer\Product.wxs -out build\Zenith-OS.wixobj
light.exe build\Zenith-OS.wixobj -out dist\Zenith-OS-Setup.msi -ext WixUIExtension

if errorlevel 1 (
    echo [WARN] MSI build failed, but executable is ready
) else (
    echo [OK] MSI built: dist\Zenith-OS-Setup.msi
)

:done
echo.
echo ========================================
echo  BUILD COMPLETE
echo ========================================
echo.
echo  Executable: dist\Zenith-OS\Zenith-OS.exe
if exist dist\Zenith-OS-Setup.msi echo  Installer:  dist\Zenith-OS-Setup.msi
echo.
echo  Run: dist\Zenith-OS\Zenith-OS.exe
echo.
pause
