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

See [submissionSteps.md](submissionSteps.md) for implementation steps and progress.

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
```
Aletheia: Medical AI Reasoning with Knowledge Graphs and Guardrails
MedGemma Impact Challenge Submission
```
