# Zenith-OS Build Script (PowerShell)
# Builds executable and MSI installer

param(
    [switch]$SkipExe,
    [switch]$SkipMsi,
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$build = Join-Path $root "build"

Write-Host ""
Write-Host "  Zenith-OS Builder v$Version" -ForegroundColor Cyan
Write-Host "  ============================" -ForegroundColor Cyan
Write-Host ""

# ===== Functions =====

function Find-WixToolset {
    # Check common WiX installation paths
    $paths = @(
        "${env:ProgramFiles(x86)}\WiX Toolset v3.11\bin",
        "${env:ProgramFiles(x86)}\WiX Toolset v3.14\bin",
        "$env:ProgramFiles\WiX Toolset v3.11\bin",
        "$env:ProgramFiles\WiX Toolset v3.14\bin"
    )

    foreach ($path in $paths) {
        if (Test-Path "$path\candle.exe") {
            return $path
        }
    }

    # Try PATH
    $candle = Get-Command candle.exe -ErrorAction SilentlyContinue
    if ($candle) {
        return Split-Path $candle.Source
    }

    return $null
}

function Test-Prerequisites {
    # Check Python
    try {
        $pyVersion = python --version 2>&1
        Write-Host "  [OK] Python: $pyVersion" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] Python not found" -ForegroundColor Red
        Write-Host "         Install Python 3.9+ from python.org" -ForegroundColor Yellow
        return $false
    }

    # Check pip
    try {
        $pipVersion = pip --version 2>&1
        Write-Host "  [OK] pip available" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] pip not found" -ForegroundColor Red
        return $false
    }

    return $true
}

function Install-Dependencies {
    Write-Host ""
    Write-Host "  Installing dependencies..." -ForegroundColor Yellow

    Push-Location $root
    try {
        pip install -r app\requirements.txt --quiet 2>&1 | Out-Null
        pip install pyinstaller --quiet 2>&1 | Out-Null
        Write-Host "  [OK] Dependencies installed" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

function Build-Executable {
    Write-Host ""
    Write-Host "  Building executable..." -ForegroundColor Yellow

    Push-Location $root
    try {
        # Clean previous build
        if (Test-Path $build) { Remove-Item $build -Recurse -Force }
        if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }

        # Build with PyInstaller
        pyinstaller installer\zenith.spec --clean --noconfirm --distpath $dist --workpath $build 2>&1 | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller build failed"
        }

        # Copy additional files
        $dirs = @("config", "skills", "core", "memory", "tools", "research", "filters", "sandbox", "tts")
        foreach ($dir in $dirs) {
            $src = Join-Path $root $dir
            $dst = Join-Path $dist "Zenith-OS\$dir"
            if (Test-Path $src) {
                Copy-Item $src $dst -Recurse -Force -ErrorAction SilentlyContinue
            }
        }

        # Copy root files
        Copy-Item (Join-Path $root "zenith.md") (Join-Path $dist "Zenith-OS\") -Force -ErrorAction SilentlyContinue
        Copy-Item (Join-Path $root "LICENSE") (Join-Path $dist "Zenith-OS\") -Force -ErrorAction SilentlyContinue
        Copy-Item (Join-Path $root "requirements.txt") (Join-Path $dist "Zenith-OS\") -Force -ErrorAction SilentlyContinue

        Write-Host "  [OK] Executable built: dist\Zenith-OS\" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "  [FAIL] Build failed: $_" -ForegroundColor Red
        return $false
    } finally {
        Pop-Location
    }
}

function Build-MSI {
    Write-Host ""
    Write-Host "  Building MSI installer..." -ForegroundColor Yellow

    $wixPath = Find-WixToolset
    if (-not $wixPath) {
        Write-Host "  [SKIP] WiX Toolset not found" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  To build MSI, install WiX Toolset:" -ForegroundColor Yellow
        Write-Host "    1. Download: https://wixtoolset.org/" -ForegroundColor White
        Write-Host "    2. Or run: winget install Microsoft.WiXToolset" -ForegroundColor White
        Write-Host "    3. Add to PATH: ${env:ProgramFiles(x86)}\WiX Toolset v3.11\bin" -ForegroundColor White
        Write-Host ""
        return $false
    }

    Write-Host "  [OK] WiX found at: $wixPath" -ForegroundColor Green

    $candle = Join-Path $wixPath "candle.exe"
    $light = Join-Path $wixPath "light.exe"

    Push-Location $root
    try {
        # Compile
        $wxs = Join-Path $root "installer\Product.wxs"
        $wixobj = Join-Path $build "Zenith-OS.wixobj"

        & $candle $wxs -out $wixobj "-dSourceDir=$dist\Zenith-OS" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "WiX compilation failed" }

        # Link
        $msi = Join-Path $dist "Zenith-OS-Setup.msi"
        & $light $wixobj -out $msi -ext WixUIExtension 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "WiX linking failed" }

        $size = (Get-Item $msi).Length / 1MB
        Write-Host "  [OK] MSI built: dist\Zenith-OS-Setup.msi ($([math]::Round($size, 1)) MB)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "  [FAIL] MSI build failed: $_" -ForegroundColor Red
        return $false
    } finally {
        Pop-Location
    }
}

# ===== Main =====

Write-Host "  Checking prerequisites..." -ForegroundColor Yellow
if (-not (Test-Prerequisites)) {
    Write-Host ""
    Write-Host "  BUILD FAILED: Missing prerequisites" -ForegroundColor Red
    exit 1
}

Install-Dependencies

$exeOk = $true
$msiOk = $true

if (-not $SkipExe) {
    $exeOk = Build-Executable
}

if (-not $SkipMsi -and $exeOk) {
    $msiOk = Build-MSI
}

# ===== Summary =====
Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
if ($exeOk -and $msiOk) {
    Write-Host "  BUILD SUCCESSFUL" -ForegroundColor Green
} elseif ($exeOk) {
    Write-Host "  PARTIAL BUILD (MSI skipped)" -ForegroundColor Yellow
} else {
    Write-Host "  BUILD FAILED" -ForegroundColor Red
    exit 1
}
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""

if ($exeOk) {
    Write-Host "  Executable: dist\Zenith-OS\Zenith-OS.exe" -ForegroundColor White
}
if ($msiOk) {
    Write-Host "  Installer:  dist\Zenith-OS-Setup.msi" -ForegroundColor White
}
Write-Host ""
Write-Host "  Run:" -ForegroundColor Gray
Write-Host "    dist\Zenith-OS\Zenith-OS.exe" -ForegroundColor White
Write-Host ""
Write-Host "  Silent install:" -ForegroundColor Gray
Write-Host "    msiexec /i Zenith-OS-Setup.msi /quiet" -ForegroundColor White
Write-Host ""
