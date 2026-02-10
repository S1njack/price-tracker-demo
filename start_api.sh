#!/bin/bash
# Start the secure price tracker API

cd "$(dirname "$0")"

echo "🔒 Starting Price Tracker API (Secure Mode)"
echo "=========================================="
echo ""

# Kill any existing API processes
pkill -f "python.*api" 2>/dev/null

# Start the secure API
python3 api_secure.py
