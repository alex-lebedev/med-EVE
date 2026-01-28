#!/usr/bin/env python3
"""
Download MedGemma 4B model locally to models/ directory
"""
import os
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("❌ huggingface_hub not installed. Run: pip install huggingface_hub")
    sys.exit(1)

def main():
    # Get repository root (parent of scripts directory)
    repo_root = Path(__file__).parent.parent
    models_dir = repo_root / "models" / "medgemma-4b-it"
    
    print(f"📦 Downloading MedGemma 4B model...")
    print(f"   Repository: google/medgemma-4b-it")
    print(f"   Destination: {models_dir}")
    print(f"   Size: ~8GB (this will take 10-30 minutes)")
    print()
    
    # Create directory
    models_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        snapshot_download(
            repo_id="google/medgemma-4b-it",
            local_dir=str(models_dir),
            local_dir_use_symlinks=False
        )
        print()
        print(f"✅ Model downloaded successfully!")
        print(f"   Location: {models_dir}")
        print()
        print("Next steps:")
        print("  1. Make sure you've updated model_manager.py to use local models")
        print("  2. Run: export MODE=model")
        print("  3. Run: make demo")
    except Exception as e:
        print()
        print(f"❌ Error downloading model: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Make sure you're logged in: huggingface-cli login")
        print("  2. Accept model terms at: https://huggingface.co/google/medgemma-4b-it")
        print("  3. Check your internet connection")
        sys.exit(1)

if __name__ == "__main__":
    main()
