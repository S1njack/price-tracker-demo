# =============================================================================
# Price Tracker — Windows Build Script
# Produces: release/Price Tracker Setup *.exe
# =============================================================================

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

Write-Host "================================================"
Write-Host "  Price Tracker — Windows Build"
Write-Host "================================================"

# 1. Create a temporary Python venv and install deps + PyInstaller
Write-Host ""
Write-Host "[1/5] Setting up Python build environment..."
python -m venv .build-venv
& .\.build-venv\Scripts\Activate.ps1
pip install -r requirements-secure.txt pyinstaller --quiet

# 2. Bundle the Python backend with PyInstaller
Write-Host ""
Write-Host "[2/5] Bundling Python backend with PyInstaller..."
pyinstaller backend.spec --distpath electron-resources/backend --noconfirm

# 3. Copy Playwright's Chromium into electron-resources
Write-Host ""
Write-Host "[3/5] Copying Playwright Chromium..."
New-Item -ItemType Directory -Force -Path electron-resources\chromium | Out-Null

# Playwright stores browsers in %LOCALAPPDATA%\ms-playwright\ on Windows
$PlaywrightCache = "$env:LOCALAPPDATA\ms-playwright"
if (-not (Test-Path $PlaywrightCache)) {
    Write-Host "  Playwright browsers not found. Installing Chromium..."
    playwright install chromium
}
Copy-Item -Recurse -Force "$PlaywrightCache\*" electron-resources\chromium\
Write-Host "  Chromium copied to electron-resources\chromium\"

# 4. Build the React frontend
Write-Host ""
Write-Host "[4/5] Building frontend..."
npm run build

# 5. Package with electron-builder
Write-Host ""
Write-Host "[5/5] Packaging with electron-builder..."
npx electron-builder --win

# Cleanup
deactivate
Write-Host ""
Write-Host "================================================"
Write-Host "  Build complete!"
Write-Host "  Output: release\"
Write-Host "================================================"
Get-ChildItem release\*.exe -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" }
