# med-EVE Submission — MedGemma Impact Challenge

## Problem

Clinical LLM systems are difficult to trust in practice. Three core anxieties block deployment:

1. **Hallucination** — models invent findings or recommend tests for markers not in the input.
2. **Black-box reasoning** — clinicians cannot audit why a recommendation was made.
3. **Lack of safety controls** — no deterministic mechanism prevents dangerous outputs.

med-EVE addresses all three by combining knowledge-graph reasoning, agentic MedGemma augmentation, a MedGemma safety critic, and hard rule-based guardrails — with full event-level transparency at every step.

## Architecture

Seven-stage pipeline (`backend/app.py`):

| Stage | Role | MedGemma involvement |
|-------|------|---------------------|
| `LAB_NORMALIZE` | Standardize lab values, flag abnormals | None (deterministic) |
| `CONTEXT_SELECT` | Extract subgraph from KG, dynamic nodes | Optional agent (flag-gated) |
| `EVIDENCE_SCORE` | Score evidence edges, rank patterns | Optional agent (flag-gated) |
| `REASON` | Generate hypotheses, rank, explain | **Hybrid**: KG hypotheses + model ranking + model reasoning prose |
| `CRITIC` | Safety review of hypotheses and actions | **MedGemma critic** (always active in model mode) |
| `GUARDRAILS` | Hard rule-based safety patches | Deterministic rules from YAML |
| `CASE_IMPRESSION` | Patient overview summary | **MedGemma** (model mode) |

### Gating policy

Model agents are **flag-gated by design** for latency and risk control. Default model mode uses a hybrid path: rule-grounded hypotheses from the KG, then MedGemma ranks confidence and generates short reasoning prose for the top hypotheses. Full-agent behavior (context selection, evidence weighting, full hypothesis JSON, test recommendation, action generation, guardrail explanation, novel insight) is available via environment flags for ablation and research.

This is an intentional deployment trade-off — not an incomplete implementation. Each agent routing decision is emitted as a structured `AGENT_DECISION` event, making the gating policy fully auditable.

## MedGemma integration points

In default model mode, **every case** invokes MedGemma at multiple decision points:

- **Hypothesis ranking** — MedGemma re-ranks KG-derived hypotheses with calibrated confidence (1 call)
- **Clinical reasoning** — MedGemma generates one-sentence reasoning prose for top hypotheses (2 calls)
- **Safety critic** — MedGemma reviews all hypotheses and actions for clinical safety, producing patch commands (1 call)
- **Case impression** — MedGemma writes a 2–4 sentence patient overview (1 call)

**Measured: 4.7 model calls and 4.9 agent routing decisions per case** (50-case verification suite, `MODE=model`, seed 42).

## Safety approach

Guardrails are defined in `backend/guardrails/guardrails.yml` and enforced deterministically in `backend/core/guardrails.py`:

| Rule | Behavior |
|------|----------|
| `GR_001` | Block iron supplementation under inflammation pattern |
| `GR_002` | Require antibody confirmation for Hashimoto mention |
| `GR_003` | Remove all dosing recommendations |
| `GR_004` | Enforce action bucket constraints |
| `GR_005` | Remove invented marker evidence (not in input) |

When guardrails trigger, JSON patches are emitted and applied before final output. All guardrail events are visible in the UI timeline as "trust moments."

## Evaluation methodology

### Verification, not validation

In clinical AI, the cost of a wrong recommendation is not a bad metric — it's a harmed patient. Before diagnostic accuracy can be validated on real-world data, the system's safety architecture must first be **verified**: every deterministic component must behave correctly, every safety layer must function as designed, and the system must be robust to input variation. Our evaluation suite serves this purpose.

This is a deliberate engineering choice. In safety-critical systems (medical devices, avionics), verification precedes validation. We verify the pipeline works correctly across all tested scenarios so that prospective clinical evaluation — the next step — can focus on efficacy rather than debugging infrastructure failures.

### What the evaluation proves

Our 50-case verification suite (8 base clinical scenarios with bounded numeric jitter producing 50 deterministic variants) demonstrates:

| Metric | Model mode | Lite mode | What it proves |
|--------|-----------|-----------|---------------|
| Signal detection rate | 100% | 100% | KG backbone is deterministically correct and robust to input noise |
| Critic intervention rate | 100% | 0% | MedGemma critic reviews every case in model mode |
| Guardrail false-positive rate | 0% | 0% | Safety layer never blocks valid clinical reasoning |
| Schema valid rate | 100% | 100% | Pipeline always produces well-formed output |
| Avg model calls per case | 4.7 | 0 | Multi-point MedGemma integration, not a wrapper |
| Avg agent decisions per case | 4.9 | 3 | Explicit, auditable routing at every decision point |

**Why signal detection is 100% in both modes — and why that's the right result:** Signal detection measures whether the KG correctly identifies the relevant clinical patterns from lab inputs. This is a deterministic operation (marker → KG node → subgraph → patterns) independent of MedGemma. 100% means the deterministic backbone is reliable — exactly the foundation needed before adding model-based reasoning on top. If this were less than 100%, it would indicate a KG design flaw, not a model limitation.

**Where MedGemma adds value** is not in pattern detection (which should be deterministic) but in:
- Re-ranking hypothesis confidence based on clinical reasoning
- Generating clinician-readable reasoning prose
- Catching unsafe inferences through the critic pass
- Producing contextual patient overviews

### Lite vs. model output: qualitative comparison

The same deterministic signals produce materially different outputs depending on whether MedGemma is engaged:

**Lite mode (rule-based):**
- Hypothesis confidence: fixed rule-based scores (e.g., 0.85 for strong pattern match)
- Reasoning: none (template labels only)
- Critic review: skipped entirely
- Case impression: `"Top consideration: Iron deficiency anemia (likely). Notable abnormal markers: Ferritin, Iron, TSAT, Hb."`

**Model mode (MedGemma hybrid):**
- Hypothesis confidence: re-calibrated by MedGemma based on lab context (e.g., adjusted to 0.78 when evidence is mixed)
- Reasoning: MedGemma-generated clinical prose (e.g., *"Low ferritin with low iron saturation and normocytic anemia in the setting of elevated inflammatory markers suggests functional iron deficiency driven by chronic inflammation."*)
- Critic review: MedGemma examines all hypotheses for safety, issuing structured patch commands when needed
- Case impression: MedGemma-generated 2–4 sentence patient overview with clinical context

The model transforms a pattern-matching report into a clinically reasoned analysis. The deterministic KG ensures the right patterns are identified; MedGemma ensures they are interpreted, explained, and safety-checked.

### What the evaluation does NOT claim

- Diagnostic superiority over existing clinical decision support tools
- Validation on real-world patient data or external clinical datasets
- Generalization beyond the pathways currently in the KG (iron, thyroid, inflammation)

These require prospective clinical evaluation, which is the natural next step for deployment. The evaluation verifies the engineering foundation that makes such validation meaningful.

### Commands

```bash
# Full model-mode verification (50 cases, ~3h on CPU)
MODE=model REPRODUCIBILITY_SEED=42 make evals

# Model-mode smoke test (1 case, fast validation)
make evals-model-smoke

# Lite-mode verification (instant, no model)
make evals

# Internal ablations (lite vs hybrid vs full-agent)
make ablations
```

Artifacts are generated under `backend/evals/results/` as JSON, CSV, and Markdown.

## Reproducibility

- **Setup**: `bash setup.sh` (creates venv, installs pinned dependencies, verifies model stack)
- **One-command demo**: `./run_demo.sh`
- **Determinism control**: `REPRODUCIBILITY_SEED` (default `42`)
- **Pinned dependencies**: `requirements-pinned.txt`
- **Detailed runbook**: [docs/REPRODUCIBILITY_CHECKLIST.md](REPRODUCIBILITY_CHECKLIST.md)

## Agentic Workflow prize positioning

med-EVE demonstrates genuine agentic behavior through:

1. **Explicit routing decisions** — `agent_manager.should_use_agent(...)` evaluates case complexity, marker patterns, and environment flags at each decision point. Every decision is emitted as a structured `AGENT_DECISION` event with rationale.
2. **Multi-step model engagement** — MedGemma is invoked for ranking, reasoning, critique, and impression generation — not a single monolithic call. 4.7 model calls per case, each tracked in the event stream.
3. **Critic-as-agent** — The MedGemma critic acts as an autonomous safety reviewer, producing structured patch commands (`REMOVE_HYPOTHESIS`, `LOWER_CONFIDENCE`, `REMOVE_ACTION`) that are applied to the pipeline output.
4. **Full event transparency** — Every model call, agent decision, guardrail intervention, and patch application is recorded in the event stream and visualized in the UI timeline.

## Edge AI prize positioning

- **Lite mode** supports no-model operation for constrained environments — identical pipeline, zero model dependencies.
- **Local model loading** from `models/` enables fully offline operation with no API calls.
- **Deterministic seeds** and script-based evaluation support reproducible edge testing.
- **Flag-gated agents** allow selective model engagement to trade latency for depth on resource-constrained devices.

## Known limitations and next steps

- **Synthetic benchmarks**: Current evaluation uses synthetic cases designed around the KG's coverage. This verifies internal consistency and safety architecture, but does not replace clinical validation on real-world data.
- **KG coverage**: Pattern coverage is bounded by the current graph scope (iron, thyroid, inflammation pathways). Expanding the KG to cover additional clinical domains is a primary extension path.
- **Latency**: CPU inference on the 4B model averages ~3 minutes per case. GPU deployment or quantization is recommended for production use.
- **Clinical validation**: Prospective evaluation on de-identified EHR lab panels is the planned next step. The verified safety architecture (guardrails, critic, event transparency) provides the foundation for safe clinical testing.
