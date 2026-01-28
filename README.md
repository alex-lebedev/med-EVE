# Aletheia: Agentic Medical AI Reasoning with Knowledge Graphs and Guardrails

A safe, transparent, and auditable medical AI system that combines knowledge graph reasoning with **agentic MedGemma** for clinical decision support.

## Overview

Aletheia is an **agentic medical reasoning pipeline** where MedGemma is used at **6 key decision points**, with the model deciding when to engage for complex reasoning:

1. Normalizes lab results
2. **Context Selection Agent**: Identifies patterns (uses model for complex cases)
3. **Evidence Weighting Agent**: Scores evidence (uses model for rare/conflicting cases)
4. **Hypothesis Generation Agent**: Generates differential diagnosis (always uses model)
5. **Test Recommendation Agent**: Prioritizes tests (uses model when ambiguity exists)
6. **Action Generation Agent**: Generates patient actions (always uses model)
7. **Guardrail Explanation Agent**: Explains safety concerns (uses model when guardrails fail)
8. Applies guardrails to block unsafe recommendations
9. Provides complete transparency through event-driven traceability

## Key Features

- **Agentic Architecture**: MedGemma used at 6 decision points with intelligent routing
- **Knowledge Graph-Based Reasoning**: Explicit representation of medical relationships
- **Evidence Scoring**: Transparent scoring with model-assisted dynamic weighting
- **Multi-Layer Guardrails**: Automatic safety checks with model-generated explanations
- **Event-Driven Transparency**: Complete audit trail showing all model calls and decisions
- **Deterministic Behavior**: Consistent outputs with rule-based fallback
- **Hybrid Approach**: Combines structured knowledge graphs with flexible LLM reasoning

## Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd aletheia-demo

# Install dependencies
pip install -r requirements.txt
```

### Run Demo

**Lite Mode (Default - Rule-Based):**
```bash
make demo
```

**Model Mode (Agentic - Requires GPU):**
```bash
# Set mode to use MedGemma
export MODE=model
# Optional: Use 27B model instead of 4B
export MEDGEMMA_MODEL=google/medgemma-27b-text-it

# Login to HuggingFace and accept terms
huggingface-cli login

# Run demo
make demo
```

For detailed setup (from scratch, different models, where files go, switching modes), see **Running modes and models** below.

This will:
- Start backend on http://localhost:8000
- Start frontend on http://localhost:8080
- Open browser with gotcha case auto-playing
- Show agentic workflow with model reasoning

### Manual Run

**Backend only:**
```bash
make run
```

**Run tests:**
```bash
make verify
```

## Running modes and models

### Modes

- **Lite (default)** – No model; rule-based only. No download, works offline.  
  Run: `make demo` (no env vars).
- **Model** – Uses MedGemma for agentic reasoning. Needs GPU (or patience on CPU).  
  Run: `export MODE=model` then `make demo`.  
  First time the app will download the model; later runs reuse the cache.

### Supported models

Set before `make demo` (only applies when `MODE=model`):

| Model | Env / default | Notes |
|-------|----------------|------|
| **4B** | `google/medgemma-4b-it` (default) | Smaller, faster. No env needed, or `export MEDGEMMA_MODEL=google/medgemma-4b-it` |
| **27B** | `export MEDGEMMA_MODEL=google/medgemma-27b-text-it` | Larger, more capable; longer download and load |

### Where the model comes from

1. **Repo `models/` folder** – If you have placed a model in the repo under `models/<model-id>/` (e.g. `models/medgemma-4b-it/` or `models/medgemma-27b-text-it/`) with `config.json` and weight files, Aletheia loads from there.
2. **HuggingFace cache** – Otherwise the app downloads from HuggingFace on first use and caches under `~/.cache/huggingface` (or `$HF_CACHE_DIR`). It does **not** copy downloads into `models/`; the cache is the single copy.

See [models/README.md](models/README.md) if you want to put a model in the repo for a self-contained setup.

### Minimum steps from scratch (model mode)

1. **Clone and install**
   ```bash
   git clone <repo-url>
   cd aletheia-demo
   pip install -r requirements.txt
   ```

2. **HuggingFace access (required for gated models)**  
   Log in and accept the model terms:
   ```bash
   huggingface-cli login
   ```
   Then open the model page on the Hub and accept the terms (e.g. [medgemma-4b-it](https://huggingface.co/google/medgemma-4b-it), [medgemma-27b-text-it](https://huggingface.co/google/medgemma-27b-text-it)).

3. **Choose model and run**
   - **4B:** `export MODE=model && make demo`
   - **27B:** `export MODE=model && export MEDGEMMA_MODEL=google/medgemma-27b-text-it && make demo`

4. **First run** – The backend will log “Loading model from HuggingFace…” and download (can take 30+ minutes for 27B). The progress bar may stay at 0% for a while; you can confirm activity with `huggingface-cli scan-cache` or by watching `~/.cache/huggingface`.

5. **When ready** – The backend logs “Model loaded successfully!” and the UI shows model status. You can also call `GET /health` and check `model_loaded` and `lite_mode`.

### Switching between lite and model / between models

- **Lite → model:** `export MODE=model` (and optionally `MEDGEMMA_MODEL=...`), then `make demo`.
- **Model A → model B:** Set `MEDGEMMA_MODEL` to the other model, restart (`make stop` then `make demo`). If that model wasn’t used before, it will download on first load.
- **Model → lite:** `unset MODE` or `export MODE=lite`, then `make demo`.

### Inspecting the cache (what’s using space)

Downloaded models live in the HuggingFace cache, not in the repo. To see what’s there and how much space it uses:

```bash
hf cache scan
```

(This replaces the deprecated `huggingface-cli scan-cache`.)

This lists each cached repo (e.g. `models--google--medgemma-4b-it`, `models--google--medgemma-27b-text-it`) and their size. You can then remove specific cached models via the Hub CLI if you need to free space; see [HuggingFace cache docs](https://huggingface.co/docs/huggingface_hub/guides/manage-cache).

**If the scan shows 0 repos:** The app uses `HF_CACHE_DIR` (default `~/.cache/huggingface`). The Hub CLI uses `HF_HOME` for its default. To scan the same location the app uses, run:

```bash
HF_HOME=~/.cache/huggingface hf cache scan
```

or, if you set a custom cache when running the app: `HF_HOME=/path/you/used hf cache scan`. Also, if a download was interrupted or never completed, the cache may be empty or partial; run the app again with `MODE=model` and let the download finish, then scan again.

## Agentic Architecture

Aletheia uses MedGemma at **6 key decision points**:

1. **Context Selection Agent**: Identifies patterns for complex cases (>3 markers)
2. **Evidence Weighting Agent**: Dynamic weighting for rare/conflicting evidence
3. **Hypothesis Generation Agent**: Core reasoning (always uses model)
4. **Test Recommendation Agent**: Prioritized recommendations when ambiguity exists
5. **Action Generation Agent**: Context-aware patient actions (always uses model)
6. **Guardrail Explanation Agent**: Educational explanations when guardrails fail

Each agent decides when to use the model vs. rule-based fallback, creating a truly agentic system.

**Model Usage**: 4-6 model calls per complex case, each adding unique clinical insight.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed pipeline flow and agent descriptions.

## Submission Documentation

See [docs/SUBMISSION.md](docs/SUBMISSION.md) for:
- Problem statement
- Agentic model architecture (6 integration points)
- Safety approach (guardrails with explanations)
- Reproducibility instructions
- Evaluation summary with metrics

## API Endpoints

- `GET /cases` - List available test cases
- `GET /cases/{id}` - Get specific case
- `POST /run` - Run pipeline on a case
- `GET /health` - Health check

## Evaluation

Run evaluation on all test cases:
```bash
cd backend
PYTHONPATH=. python evals/run_evals.py
```

**Results**: 8/8 cases pass guardrail checks (gotcha case correctly triggers and patches unsafe actions).

## License

This work is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).
See [LICENSE](LICENSE) for details.

## Citation

If you use this code, please cite:

**Alexander Lebedev MD PhD and Luigi Espasiano MD** (Function Health)

*Aletheia: Medical AI Reasoning with Knowledge Graphs and Guardrails* — MedGemma Impact Challenge Submission.
