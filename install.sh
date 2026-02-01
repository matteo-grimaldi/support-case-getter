#!/bin/bash
# Red Hat Cases TUI - Installation Script

set -e

echo "=================================="
echo "Red Hat Cases TUI - Setup"
echo "=================================="
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Found Python $PYTHON_VERSION"

# Check pip
echo ""
echo "[2/5] Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is not installed"
    echo "Please install pip3"
    exit 1
fi
echo "✓ pip3 is installed"

# Install dependencies
echo ""
echo "[3/5] Installing Python dependencies..."
pip3 install -q rich requests PyYAML
echo "✓ Dependencies installed"

# Make script executable
echo ""
echo "[4/5] Making script executable..."
chmod +x redhat_cases_tui.py
echo "✓ Script is now executable"

# Create example config if it doesn't exist
echo ""
echo "[5/5] Setting up configuration..."
if [ ! -f "accounts.yaml" ]; then
    if [ -f "accounts.example.yaml" ]; then
        echo "📝 Creating accounts.yaml from example..."
        cp accounts.example.yaml accounts.yaml
        echo "✓ Please edit accounts.yaml with your account numbers"
    else
        echo "⚠ No example config found, you'll need to create accounts.yaml manually"
    fi
else
    echo "✓ accounts.yaml already exists"
fi

echo ""
echo "=================================="
echo "✅ Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit accounts.yaml with your Red Hat account numbers"
echo "2. Get your offline token from: https://access.redhat.com/management/api"
echo "3. Run: ./redhat_cases_tui.py accounts.yaml YOUR_TOKEN"
echo ""
echo "For security, consider storing your token in an environment variable:"
echo "  export REDHAT_OFFLINE_TOKEN='your-token-here'"
echo "  ./redhat_cases_tui.py accounts.yaml \"\$REDHAT_OFFLINE_TOKEN\""
echo ""