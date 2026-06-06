@echo off
REM Zenith-OS MSI Builder
REM Requires: WiX Toolset 3.11+ (https://wixtoolset.org/)

echo.
echo  Zenith-OS MSI Builder
echo  =====================
echo.

REM ===== Check Prerequisites =====

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.9+
    goto :error
)

REM Check PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller --quiet
)

REM Check WiX
where candle >nul 2>&1
if errorlevel 1 (
    echo [ERROR] WiX Toolset not found.
    echo.
    echo  Install WiX Toolset:
    echo  1. Download from https://wixtoolset.org/
    echo  2. Or run: winget install Microsoft.WiXToolset
    echo.
    echo  After install, add to PATH:
    echo  C:\Program Files (x86)\WiX Toolset v3.11\bin
    echo.
    goto :error
)

REM ===== Step 1: Install Dependencies =====
echo [1/4] Installing Python dependencies...
pip install -r app\requirements.txt --quiet
pip install pyinstaller --quiet

REM ===== Step 2: Build with PyInstaller =====
echo.
echo [2/4] Building executable with PyInstaller...
pyinstaller installer\zenith.spec --clean --noconfirm --distpath dist --workpath build

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    goto :error
)

REM Copy additional files to dist
echo Copying additional files...
if not exist dist\Zenith-OS\config mkdir dist\Zenith-OS\config
if not exist dist\Zenith-OS\skills mkdir dist\Zenith-OS\skills
if not exist dist\Zenith-OS\core mkdir dist\Zenith-OS\core
if not exist dist\Zenith-OS\memory mkdir dist\Zenith-OS\memory
if not exist dist\Zenith-OS\tools mkdir dist\Zenith-OS\tools
if not exist dist\Zenith-OS\research mkdir dist\Zenith-OS\research
if not exist dist\Zenith-OS\filters mkdir dist\Zenith-OS\filters
if not exist dist\Zenith-OS\sandbox mkdir dist\Zenith-OS\sandbox
if not exist dist\Zenith-OS\tts mkdir dist\Zenith-OS\tts

xcopy /E /Y /Q config\* dist\Zenith-OS\config\ >nul 2>&1
xcopy /E /Y /Q skills\* dist\Zenith-OS\skills\ >nul 2>&1
xcopy /E /Y /Q core\* dist\Zenith-OS\core\ >nul 2>&1
xcopy /E /Y /Q memory\* dist\Zenith-OS\memory\ >nul 2>&1
xcopy /E /Y /Q tools\* dist\Zenith-OS\tools\ >nul 2>&1
xcopy /E /Y /Q research\* dist\Zenith-OS\research\ >nul 2>&1
xcopy /E /Y /Q filters\* dist\Zenith-OS\filters\ >nul 2>&1
xcopy /E /Y /Q sandbox\* dist\Zenith-OS\sandbox\ >nul 2>&1
xcopy /E /Y /Q tts\* dist\Zenith-OS\tts\ >nul 2>&1
copy /Y zenith.md dist\Zenith-OS\ >nul 2>&1
copy /Y LICENSE dist\Zenith-OS\ >nul 2>&1
copy /Y requirements.txt dist\Zenith-OS\ >nul 2>&1

REM ===== Step 3: Compile WiX =====
echo.
echo [3/4] Compiling WiX source...
candle.exe installer\Product.wxs -out build\Zenith-OS.wixobj -dSourceDir=dist\Zenith-OS

if errorlevel 1 (
    echo [ERROR] WiX compilation failed
    goto :error
)

REM ===== Step 4: Link MSI =====
echo.
echo [4/4] Linking MSI installer...
light.exe build\Zenith-OS.wixobj -out dist\Zenith-OS-Setup.msi -ext WixUIExtension

if errorlevel 1 (
    echo [ERROR] WiX linking failed
    goto :error
)

REM ===== Done =====
echo.
echo ========================================
echo  BUILD SUCCESSFUL
echo ========================================
echo.
echo  Output: dist\Zenith-OS-Setup.msi
echo  Size:
for %%A in (dist\Zenith-OS-Setup.msi) do echo   %%~zA bytes
echo.
echo  Install: double-click the MSI file
echo  Silent:  msiexec /i Zenith-OS-Setup.msi /quiet
echo.
goto :end

:error
echo.
echo BUILD FAILED
exit /b 1

:end
pause
