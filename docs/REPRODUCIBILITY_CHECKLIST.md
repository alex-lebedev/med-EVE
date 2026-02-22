# Reproducibility Checklist

## 1) Environment bootstrap

From repo root:

```bash
bash setup.sh
```

This creates `venv/`, installs dependencies (pinned by default from `requirements-pinned.txt`), and verifies the model stack imports.

## 2) Determinism controls

Set reproducibility seed (default is already `42`):

```bash
export REPRODUCIBILITY_SEED=42
```

To disable explicit seed control:

```bash
export REPRODUCIBILITY_SEED=off
```

## 3) One-command demo

Lite mode:

```bash
./run_demo.sh
```

Model mode:

```bash
export MODE=model
./run_demo.sh
```

## 4) Evaluation

**Model-mode smoke test (recommended first step, ~5 min):**

```bash
make evals-model-smoke
```

Confirms model loading and end-to-end model execution on a single case.

**Full model-mode evaluation (50 cases, ~3h on CPU):**

```bash
MODE=model REPRODUCIBILITY_SEED=42 make evals
```

**Lite-mode evaluation (instant):**

```bash
make evals
```

Or explicitly:

```bash
cd backend
PYTHONPATH=. MODE=model python evals/run_evals.py --dataset golden --seed 42
```

### Expected results (model mode, seed 42)

| Metric | Expected | What it verifies |
|--------|----------|-----------------|
| Signal detection rate | 100% | KG backbone correctness |
| Critic intervention rate | 100% | MedGemma safety review active |
| Guardrail false-positive rate | 0% | Safety layer precision |
| Schema valid rate | 100% | Contract compliance |
| Avg model calls per case | ~4.7 | Multi-point MedGemma integration |
| Avg agent decisions per case | ~4.9 | Agentic routing at each decision point |

> Signal detection measures deterministic KG correctness (marker → pattern mapping), not model-based diagnostic accuracy. MedGemma adds value through confidence re-calibration, reasoning prose, critic review, and case impressions.

### Artifacts

Written under `backend/evals/results/`:
- `*.json` — full metrics + per-case records
- `*.csv` — per-case tabular export
- `*.md` — summary table with per-case breakdown

## 5) Internal ablations

Run lite vs hybrid-default vs full-agent:

```bash
make ablations
```

Artifacts are written under `backend/evals/results/ablations/`.

## 6) Sanity checks before submission

- `make verify` completes in your environment.
- Doc claims match generated metrics.
- `README.md` commands work from a clean clone.
- No stale generated output files are tracked in git.

