# Ablation Protocol

## Goal
Quantify trade-offs between safety, quality signals, and latency across internal execution modes.

## Configurations
- `lite`: rule-based/no-model path
- `hybrid_default`: model mode with default flag-gated agent usage
- `full_agent`: model mode with all major agent flags enabled

## Runner
Use:

```bash
python scripts/run_ablations.py --dataset golden --seed 42
```

or:

```bash
make ablations
```

## Dataset
- Source: `backend/data_synth/golden_cases/golden_manifest.json`
- Deterministically expanded to 50 evaluation vignettes.
- Includes profiles designed to test safety/guardrail behavior and input noise robustness.

## Metrics captured
- Signal detection rate (deterministic KG correctness)
- Critic intervention rate
- Guardrail catch rate / false-positive rate
- Schema valid rate
- Average and P95 latency (all cases)
- First-invocation average and P95 latency (excludes cache hits)
- Avg model calls per case
- Avg agent decisions per case

## Output artifacts
`scripts/run_ablations.py` produces:
- JSON summary
- CSV summary
- Markdown summary table

under:

`backend/evals/results/ablations/`

## Notes
- If `MODE=model` cannot be loaded in a given environment, model-dependent configs may degrade toward lite behavior; report this explicitly in submission notes.
- All values included in submission docs should be copied from generated artifacts, not manually edited.

