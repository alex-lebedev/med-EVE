#!/bin/bash
# Setup script for med-EVE (Evidence Vector Engine) Demo

set -euo pipefail

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
REQ_FILE="requirements.txt"
if [ "${USE_PINNED_REQUIREMENTS:-1}" = "1" ] && [ -f "requirements-pinned.txt" ]; then
    REQ_FILE="requirements-pinned.txt"
fi
echo "Using dependency file: ${REQ_FILE}"
pip install -r "${REQ_FILE}"

# bitsandbytes is not stable on macOS and can crash interpreter imports.
if [ "$(uname -s)" = "Darwin" ]; then
    pip uninstall -y bitsandbytes >/dev/null 2>&1 || true
fi

echo ""
echo "🧪 Verifying key commands..."
if ! python -m uvicorn --version >/dev/null 2>&1; then
    echo "❌ uvicorn unavailable after install"
    exit 1
fi
if ! python -m pytest --version >/dev/null 2>&1; then
    echo "❌ pytest unavailable after install"
    exit 1
fi
if ! python -c "import transformers, accelerate, huggingface_hub; print(transformers.__version__, accelerate.__version__, huggingface_hub.__version__)" >/dev/null 2>&1; then
    echo "❌ Model stack import check failed (transformers/accelerate/huggingface_hub)"
    echo "   Try: pip install --force-reinstall -r ${REQ_FILE}"
    exit 1
fi
echo "✅ Core runtime tools available"

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
