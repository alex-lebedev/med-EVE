#!/usr/bin/env python3
"""
Minimal test: load MedGemma and generate a short answer.
Verifies the model loads and produces text (e.g. for CPU vs MPS device checks).

Run from repo root:
  MODE=model python scripts/test_model_generate.py
  MODE=model python scripts/test_model_generate.py --device cpu
  USE_MPS=1 MODE=model python scripts/test_model_generate.py --device mps

Custom Q&A (more complex or medical):
  MODE=model python scripts/test_model_generate.py --prompt "What lab markers support iron deficiency anemia?"
  USE_MPS=1 MODE=model python scripts/test_model_generate.py --device mps --prompt "..." --max-tokens 256

Or: make model-test  (with optional MEDGEMMA_DEVICE=cpu or USE_MPS=1)
"""
import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Test MedGemma model load and text generation.")
    parser.add_argument(
        "--device",
        choices=("cpu", "mps"),
        default=None,
        help="Force device (cpu or mps). If not set, use current env (defaults to CPU on Apple Silicon).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Custom question for the model (default: simple 2+2 math). Use for more complex or medical Q&A.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=64,
        help="Max new tokens to generate (default 64). Use 256+ for longer answers.",
    )
    args = parser.parse_args()

    if args.device is not None:
        os.environ["MEDGEMMA_DEVICE"] = args.device
        if args.device == "mps":
            os.environ["USE_MPS"] = "1"
    os.environ.setdefault("MODE", "model")

    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from core.model_manager import model_manager

    print("Loading model...")
    model_manager.load_model()
    if not model_manager.model_loaded:
        print("FAIL: Model did not load.")
        sys.exit(1)
    print(f"Model loaded. Device: {model_manager.device}")
    user_prompt = args.prompt if args.prompt else "What is 2 + 2? Reply in one short sentence."
    max_tokens = max(16, min(args.max_tokens, 1024))
    print("Generating...")
    if args.prompt:
        print("Prompt:", repr(user_prompt[:120] + ("..." if len(user_prompt) > 120 else "")))
    result = model_manager.generate(
        system_prompt="You are a helpful assistant. Answer briefly and accurately.",
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    text = result.get("text") or result.get("raw_output") or ""
    snippet = (text[:500] + "...") if len(text) > 500 else text
    print("Generated:", repr(snippet))
    if not text.strip():
        print("FAIL: No text generated.")
        sys.exit(1)
    print("OK: Model generated text.")
    sys.exit(0)


if __name__ == "__main__":
    main()
