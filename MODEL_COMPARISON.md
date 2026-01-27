# MedGemma Model Comparison

## Available Models

### 1. google/medgemma-4b-it (Default - Recommended)
- **Size**: ~8GB download, ~16GB RAM/VRAM needed
- **Parameters**: 4 billion
- **Type**: Multimodal (image + text)
- **Speed**: Fast inference (~1-3 seconds)
- **GPU**: Works on consumer GPUs (8GB+ VRAM)
- **Use Case**: Demo, development, most use cases
- **URL**: https://huggingface.co/google/medgemma-4b-it

### 2. google/medgemma-27b-text-it (Optional)
- **Size**: ~54GB download, ~60GB VRAM needed
- **Parameters**: 27 billion
- **Type**: Text-only, instruction-tuned
- **Speed**: Slower inference (~5-10 seconds)
- **GPU**: Requires high-end GPU (A100, H100, or multiple GPUs)
- **Use Case**: Production, research, highest quality needed
- **URL**: https://huggingface.co/google/medgemma-27b-text-it

## How to Switch Models

### Use 4B Model (Default)
```bash
export MODE=model
# No need to set MEDGEMMA_MODEL - 4B is default
make demo
```

### Use 27B Model (Better Quality)
```bash
export MODE=model
export MEDGEMMA_MODEL=google/medgemma-27b-text-it
make demo
```

## Recommendation

**For most users**: Use the **4B model** (default)
- ✅ Much faster download (~8GB vs ~54GB)
- ✅ Works on consumer hardware
- ✅ Still provides excellent reasoning
- ✅ Faster inference

**Only use 27B if**:
- You have high-end GPU (A100/H100)
- You need absolute best quality
- You're doing research/production
- You have time for large download
