#!/bin/bash
set -e

# =============================================================================
# Price Tracker — macOS Build Script
# Produces: release/Price Tracker-*.dmg
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "================================================"
echo "  Price Tracker — macOS Build"
echo "================================================"

# 1. Create a temporary Python venv and install deps + PyInstaller
echo ""
echo "[1/5] Setting up Python build environment..."
python3 -m venv .build-venv
source .build-venv/bin/activate
pip install -r requirements-secure.txt pyinstaller --quiet

# 2. Bundle the Python backend with PyInstaller
echo ""
echo "[2/5] Bundling Python backend with PyInstaller..."
pyinstaller backend.spec --distpath electron-resources/backend --noconfirm

# 3. Copy Playwright's Chromium into electron-resources
echo ""
echo "[3/5] Copying Playwright Chromium..."
mkdir -p electron-resources/chromium

# Playwright stores browsers in ~/Library/Caches/ms-playwright/ on macOS
PLAYWRIGHT_CACHE="$HOME/Library/Caches/ms-playwright"
if [ ! -d "$PLAYWRIGHT_CACHE" ]; then
    echo "  Playwright browsers not found. Installing Chromium..."
    playwright install chromium
fi
cp -r "$PLAYWRIGHT_CACHE"/* electron-resources/chromium/
echo "  Chromium copied to electron-resources/chromium/"

# 4. Build the React frontend
echo ""
echo "[4/5] Building frontend..."
npm run build

# 5. Package with electron-builder
echo ""
echo "[5/5] Packaging with electron-builder..."
npx electron-builder --mac

# Cleanup
deactivate
echo ""
echo "================================================"
echo "  Build complete!"
echo "  Output: release/"
echo "================================================"
ls -lh release/*.dmg 2>/dev/null || echo "  (check release/ for output files)"
