# Model Mode Usage

## Overview

The system supports two modes:
- **Lite mode** (default): Rule-based reasoning without model
- **Model mode**: Uses actual MedGemma model from HuggingFace

## Setup

1. Install dependencies:
```bash
pip install torch transformers huggingface_hub
```

2. Login to HuggingFace and accept terms:
```bash
huggingface-cli login
# Accept terms for google/medgemma-7b
```

3. Set environment variable:
```bash
export MODE=model
```

## Running

### Lite Mode (Default)
```bash
# No special setup needed
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### Model Mode
```bash
export MODE=model
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## API Usage

### Basic Request
```bash
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "case_02_anemia_of_inflammation_gotcha"}'
```

### With Debug (includes raw_model_output)
```bash
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "case_02_anemia_of_inflammation_gotcha", "debug": true}'
```

## Testing

Test model mode on multiple cases:
```bash
cd backend
MODE=model python test_model_mode.py
```

## Features

- **Strict prompts**: System and user prompts loaded from `backend/prompts/`
- **JSON-only output**: Model is forced to return JSON
- **Pydantic validation**: Output validated against ReasonerOutput schema
- **Repair pass**: If validation fails, one repair attempt is made
- **Debug mode**: Include `raw_model_output` in response when `debug=true`

## Model Details

- **Model**: `google/medgemma-7b`
- **Device**: Auto-detected (CUDA, MPS, or CPU)
- **Generation params**: 
  - max_new_tokens: 1024
  - temperature: 0.3 (for deterministic JSON)
  - top_p: 0.9
