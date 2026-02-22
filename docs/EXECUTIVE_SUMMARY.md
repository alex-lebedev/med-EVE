# med-EVE Executive Summary

## What med-EVE is

`med-EVE` (Evidence Vector Engine) is a safety-first medical reasoning system that combines:
- deterministic knowledge-graph (KG) reasoning,
- agentic MedGemma augmentation at multiple decision points,
- a MedGemma safety critic pass,
- hard rule-based guardrails with JSON patching,
- event-level observability for full reasoning playback.

## Why this is different

- **Not a black-box wrapper:** hypotheses are grounded in explicit KG signals and evidence edges — the model augments, it does not replace, deterministic reasoning.
- **Safety by construction:** every case passes through a MedGemma critic and hard guardrails before final output. Verified: 0% guardrail false-positive rate across 50 test cases.
- **Genuinely agentic:** 4.9 explicit agent routing decisions per case, each emitted as a structured event with rationale. 4.7 MedGemma calls per case across ranking, reasoning, critique, and impression.
- **Auditable outputs:** each stage emits events that can be replayed in the UI timeline — every model call, every decision, every patch.
- **Edge-ready mode:** lite mode runs the full pipeline without model inference for constrained environments.

## Verification results (model mode, 50 cases, seed 42)

| Metric | Model | Lite | What it proves |
|--------|-------|------|---------------|
| Signal detection rate | 100% | 100% | KG backbone correctness |
| Guardrail false-positive rate | 0% | 0% | Safety layer precision |
| Avg model calls / case | 4.7 | 0 | Multi-point integration |
| Avg agent decisions / case | 4.9 | 3 | Agentic routing |

Signal detection is 100% in both modes because it measures deterministic KG correctness, not model quality. MedGemma adds value through confidence re-calibration, clinical reasoning prose, critic safety review, and contextual case impressions.

> Our evaluation verifies internal consistency and safety architecture — a prerequisite for the prospective clinical validation required before deployment.

## Competition relevance

- **Main Track:** clinically oriented reasoning with transparent, reproducible, script-generated evaluation.
- **Agentic Workflow:** explicit agent routing decisions, multi-point MedGemma integration, critic-as-agent with structured patch commands, full event transparency.
- **Edge AI prize:** local model support, no-model lite fallback, deterministic seeds, flag-gated agent control for resource-constrained deployment.

## Architecture (submission version)

Pipeline stages: `LAB_NORMALIZE` → `CONTEXT_SELECT` → `EVIDENCE_SCORE` → `REASON` → `CRITIC` → `GUARDRAILS` → `CASE_IMPRESSION`

MedGemma usage is intentionally **flag-gated** for latency and safety control. Default model mode uses a hybrid strategy (rule-grounded hypotheses with model-assisted ranking/explanations), while full-agent mode can be enabled for ablation and research.

## Reproducibility

- Canonical run: `bash setup.sh` then `./run_demo.sh`
- Deterministic control: `REPRODUCIBILITY_SEED=42`
- Evaluation: `MODE=model make evals` (generates JSON/CSV/Markdown artifacts)
- All evaluation artifacts are script-generated, not hand-curated.
