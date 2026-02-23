# med-EVE (Evidence Vector Engine): Agentic Medical AI Reasoning with Knowledge Graphs and Guardrails

A safe, transparent, and auditable medical AI system that combines knowledge graph reasoning with **agentic MedGemma** for clinical decision support.

## Overview

med-EVE is a **hybrid medical reasoning pipeline** (Evidence Vector Engine) that combines deterministic KG reasoning with flag-gated MedGemma agents:

1. `LAB_NORMALIZE`
2. `CONTEXT_SELECT`
3. `EVIDENCE_SCORE`
4. `REASON`
5. `CRITIC`
6. `GUARDRAILS`
7. `CASE_IMPRESSION`

By default, model mode uses a hybrid path (rule-grounded hypotheses with model-assisted ranking and short reasoning). Additional agent calls are feature-flagged for latency/safety control.

## Key Features

- **Agentic Architecture**: MedGemma integration at multiple flag-gated decision points with explicit routing
- **Knowledge Graph-Based Reasoning**: Explicit representation of medical relationships
- **Evidence Scoring**: Transparent scoring with model-assisted dynamic weighting
- **Multi-Layer Guardrails**: Automatic safety checks with model-generated explanations
- **Event-Driven Transparency**: Complete audit trail showing all model calls and decisions
- **Deterministic Behavior**: Consistent outputs with rule-based fallback
- **Hybrid Architecture**: KG-grounded reasoning with model-augmented ranking and explanations (hypotheses from rules; MedGemma ranks and explains top hypotheses)

### Functional medicine framework

med-EVE uses a **single knowledge graph** and **anchor-based context**: any case maps into the same decision system. Signals (pattern/condition nodes) are derived from the subgraph reachable from case markers, with rule-based fallback. Markers not in the KG get **dynamic nodes** and optional link suggestions; these are returned as **suggested_kg_additions** for review. A short **case impression** (patient overview) is generated after guardrails and shown in the UI and saved output. Prompts and reasoning follow a holistic / functional medicine view (multi-system: thyroid, iron, immune, lipids). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/CONTRACTS.md](docs/CONTRACTS.md) for output schema.

### No OpenAI — local MedGemma only

This app does **not** use the OpenAI API or any other external LLM API. All model reasoning uses **MedGemma** only: either the local medical model in `models/medgemma-4b-it` (when present) or MedGemma from HuggingFace. The backend prefers the local folder when it exists so you can run fully offline.

**Recommended setup for the actual medical model in the repo:** run `python scripts/download_model.py`, then `export MODE=model` and `make demo`. The app will use the model from `models/medgemma-4b-it` and will not call any external API.

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/alex-lebedev/med-EVE
cd med-EVE

# Install dependencies
pip install -r requirements.txt
```

### Run Demo

**One-command runner (recommended):**
```bash
./run_demo.sh
```

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

1. **Repo `models/` folder** – If you have placed a model in the repo under `models/<model-id>/` (e.g. `models/medgemma-4b-it/` or `models/medgemma-27b-text-it/`) with `config.json` and weight files, the backend **prefers** this and loads from there (no HuggingFace API call; works offline).
2. **HuggingFace cache** – Otherwise the app downloads from HuggingFace on first use and caches under `~/.cache/huggingface` (or `$HF_CACHE_DIR`). It does **not** copy downloads into `models/`; the cache is the single copy.

See [models/README.md](models/README.md) if you want to put a model in the repo for a self-contained setup.

### Minimum steps from scratch (model mode)

1. **Clone and install**
   ```bash
   git clone https://github.com/alex-lebedev/med-EVE
   cd med-EVE
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

5. **When ready** – The backend logs “Model loaded successfully from repo…” or “Model loaded successfully from HuggingFace.” You can call `GET /health` and check `model_loaded`, `lite_mode`, and `model_source` (e.g. `"local"` when using `models/medgemma-4b-it`).

### Device (Apple Silicon / laptop reliability)

On Apple Silicon (M1/M2/M3), the app uses **CPU by default** for the model to avoid MPS-related errors (e.g. "Placeholder storage has not been allocated on MPS device"). To try MPS, set `export USE_MPS=1` before `make demo`. To force CPU on any platform, set `export MEDGEMMA_DEVICE=cpu`.

### Testing model text generation

To verify the model loads and produces text (e.g. to compare CPU vs MPS), run the minimal generation test from the repo root:

- **CPU (default on Apple Silicon):** `MEDGEMMA_DEVICE=cpu make model-test` or `MODE=model python scripts/test_model_generate.py --device cpu`
- **MPS (Apple Silicon only):** `USE_MPS=1 make model-test` or `MODE=model python scripts/test_model_generate.py --device mps`

First run loads the model (30–60+ s); then a short answer is generated. You should see the device and "OK: Model generated text." If it hangs in generation or prints "FAIL: No text generated.", the issue is device/runtime (e.g. MPS) or model output.

### Why does the first case take so long?

In model mode, each case can run several model calls depending on enabled flags. The default hybrid path uses model ranking/reasoning plus critic/case-impression (and optional symptom mapper), while full-agent mode can add context selection, evidence weighting, full hypothesis JSON, test recommendation, action generation, and guardrail explanation. Pipeline agents use **max_tokens=384** by default (configurable via `MEDGEMMA_MAX_TOKENS`) so runs complete reliably on laptop/MPS. Expect **2–5+ minutes per case** on a laptop (CPU or MPS), especially the first case. The simple `make model-test` runs only one short generation (64 tokens), so it finishes quickly after load.

To reduce model calls further while keeping graph updates and hypotheses: set `USE_SYMPTOM_MAPPER_MODEL=0` (rule-based symptom mapping) and/or `USE_CASE_IMPRESSION_MODEL=0` (rule-based case impression). By default, context selection, evidence weighting, test recommendation, and guardrail explanation are **disabled**; enable with:
- `USE_CONTEXT_SELECTION_MODEL=1`
- `USE_EVIDENCE_WEIGHTING_MODEL=1`
- `USE_TEST_RECOMMENDATION_MODEL=1`
- `USE_GUARDRAIL_EXPLANATION_MODEL=1`

Novel insights are generated only when `USE_NOVEL_INSIGHT_MODEL=1` (or `force`), and will be labeled "Outside KG" in the UI.

Response fields added for novelty:
- `reasoner_output.novel_insights`
- `reasoner_output.novel_actions`
- `reasoner_output.provenance`

### Switching between modes

- **Lite → model:** `export MODE=model`, then `make demo`.
- **Model → lite:** `unset MODE` or `export MODE=lite`, then `make demo`.

## Agentic Architecture

MedGemma-enabled agents available in this repo:

1. `context_selection` (flag-gated)
2. `evidence_weighting` (flag-gated)
3. `hypothesis_generation` (flag-gated full JSON path)
4. `test_recommendation` (flag-gated)
5. `action_generation` (flag-gated)
6. `guardrail_explanation` (flag-gated)
7. `novel_insight` (flag-gated)
8. Hybrid ranking/reasoning path in `REASON` (default in model mode)
9. MedGemma critic in `CRITIC`
10. Case impression generator in `CASE_IMPRESSION`

This flag-gated design is intentional: it supports controlled latency/safety trade-offs and clean ablation.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed pipeline flow and agent descriptions.

## Submission Documentation

See [docs/SUBMISSION.md](docs/SUBMISSION.md) for the full technical submission with detailed methodology, evaluation results, and prize positioning.

Additional docs:
- [docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)
- [docs/REPRODUCIBILITY_CHECKLIST.md](docs/REPRODUCIBILITY_CHECKLIST.md)
- [docs/ABLATIONS.md](docs/ABLATIONS.md)

## API Endpoints

- `GET /cases` - List available test cases
- `GET /cases/{id}` - Get specific case
- `POST /run` - Run pipeline on a case
- `GET /health` - Health check

## Evaluation

### Safety verification suite (model mode, 50 cases, seed 42)

The evaluation suite verifies internal consistency and safety architecture across 50 deterministic test variants (8 base clinical scenarios with bounded numeric jitter). This is safety verification — not clinical validation. See [docs/SUBMISSION.md](docs/SUBMISSION.md) for full methodology.

| Metric | Model mode | Lite mode | Purpose |
|--------|-----------|-----------|---------|
| Signal detection rate | 100% | 100% | KG backbone correctness |
| Critic intervention rate | 100% | n/a | MedGemma safety review |
| Guardrail false-positive rate | **0%** | 0% | Safety precision |
| Schema valid rate | 100% | 100% | Contract compliance |
| Avg model calls / case | 4.7 | 0 | Multi-point integration |
| Avg agent decisions / case | 4.9 | 3 | Agentic routing |

MedGemma adds value through confidence re-calibration, clinical reasoning prose, autonomous critic review, and contextual case impressions — not through pattern detection (which is deterministic by design).

Full results: `backend/evals/results/golden_*.md`

### Commands

```bash
# Full model-mode verification (50 cases, ~3h on CPU)
MODE=model REPRODUCIBILITY_SEED=42 make evals

# Quick smoke test (1 case, ~5 min)
make evals-model-smoke

# Lite-mode verification (instant, no model)
make evals

# Internal ablations
make ablations
```

Evaluation/ablation outputs are generated under `backend/evals/results/` as JSON/CSV/Markdown artifacts.

## License

This work is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).
See [LICENSE](LICENSE) for details.

## Citation

If you use this code, please cite:

**Alexander Lebedev MD PhD and Luigi Espasiano MD** (Function Health)

*med-EVE (Evidence Vector Engine): Medical AI Reasoning with Knowledge Graphs and Guardrails* — MedGemma Impact Challenge Submission.
