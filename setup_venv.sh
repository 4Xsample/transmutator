#!/bin/bash
# Setup script for Transmutator V2 virtual environment

set -e

echo "🚀 Setting up Transmutator V2 development environment..."
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To test the setup, run:"
echo "  python -m src.main"
echo ""
echo "To run environment diagnostics, run:"
echo "  python -m src.main doctor"
echo ""
echo "To launch the Web UI with the project venv, run:"
echo "  ./run_web.sh"
echo ""
