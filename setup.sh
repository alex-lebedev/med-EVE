#!/bin/bash
# Quick setup script for med-EVE (Evidence Vector Engine) Demo

set -e  # Exit on error

echo "🚀 Setting up med-EVE (Evidence Vector Engine) Demo..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Login to HuggingFace: huggingface-cli login"
echo "  3. Accept model terms: https://huggingface.co/google/medgemma-4b-it"
echo "  4. Download model: python scripts/download_model.py"
echo "  5. Run demo: export MODE=model && make demo"
echo ""
echo "Or run in lite mode (no model needed):"
echo "  make demo"
