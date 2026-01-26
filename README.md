# Aletheia Fancy Local Demo

A local demo showcasing MedGemma reasoning with knowledge graphs, guardrails, and interactive UI for synthetic patient cases.

## Overview

This demo simulates a medical reasoning pipeline:

1. Lab normalization
2. Knowledge graph evidence retrieval
3. MedGemma JSON reasoning
4. Guardrails for safety
5. Event-driven UI animation

## Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: Next.js (placeholder)
- **KG**: JSON-based graph
- **Model**: MedGemma (lite mode for demo)

## Setup

1. Install Python 3.8+
2. Install dependencies: `pip install fastapi uvicorn pydantic pyyaml`
3. (Optional) For frontend: `cd frontend && npm install`

## Run

```bash
./run_local.sh
```

Or manually:

```bash
cd backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for API docs.

## API Endpoints

- `GET /cases` - List cases
- `GET /cases/{id}` - Get case
- `POST /run` - Run pipeline
- `GET /health` - Health check

## Tests

```bash
cd backend
python -m pytest tests/
python evals/run_evals.py
```

## Demo

See DEMO_SCRIPT.md for step-by-step demo.