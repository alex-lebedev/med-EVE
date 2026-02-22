# Architecture Documentation

## Overview

This document describes the current architecture of the med-EVE pipeline as implemented in `backend/app.py`.

## Pipeline Flow (`/run`, `/analyze`)

1. **LAB_NORMALIZE**
   - Module: `backend/core/lab_normalizer.py`
   - Normalizes marker names, units, and statuses.

2. **CONTEXT_SELECT**
   - Module: `backend/core/context_selector.py`
   - Builds `case_card` and KG subgraph from abnormal markers.
   - May add dynamic graph expansions via `backend/core/dynamic_graph.py`.
   - Symptom mapping via `backend/core/symptom_mapper.py`.

3. **EVIDENCE_SCORE**
   - Module: `backend/core/evidence_builder.py`
   - Produces supports/contradictions, candidate pattern scores, and top discriminators.

4. **REASON**
   - Module: `backend/core/reasoner_medgemma.py`
   - Lite mode: fully rule-based.
   - Model mode (default behavior): hybrid path (rule-grounded hypotheses + model ranking/reasoning prose).
   - Full JSON generation/actions/test recommendation/novel insight are **feature-flagged**.

5. **CRITIC**
   - Module: `backend/core/critic_medgemma.py`
   - MedGemma critic emits bounded patch operations (`remove_hypothesis`, `lower_confidence`, `remove_action`).

6. **GUARDRAILS**
   - Module: `backend/core/guardrails.py`
   - Rule checks from `backend/guardrails/guardrails.yml`:
     - `GR_001` iron supplementation block under inflammation
     - `GR_002` require antibody confirmation for Hashimoto mention
     - `GR_003` no dosing recommendations
     - `GR_004` enforce allowed action buckets
     - `GR_005` no invented markers
   - Produces patches and optional model-generated explanations.

7. **CASE_IMPRESSION**
   - Module: `backend/core/case_impression.py`
   - Generates concise summary for clinician-facing output.

## Response Shape

`/run` and `/analyze` return:

```python
{
    "normalized_labs": list,
    "case_card": dict,
    "evidence_bundle": dict,
    "reasoner_output": dict,
    "critic_result": dict,
    "guardrail_report": dict,
    "case_impression": str,
    "suggested_kg_additions": dict,
    "unlinked_markers": list,
    "unmappable_inputs": list,
    "events": list,
    "timings": dict,
    "model_usage": dict
}
```

## Agent Routing

Agent routing lives in `backend/core/agent_manager.py`.
Model usage is intentionally flag-gated to control latency and risk:

- Context selection, evidence weighting, full hypothesis generation, test recommendation, action generation, and guardrail explanation are opt-in via env flags.
- Hybrid ranking/reasoning in `REASON`, critic in `CRITIC`, and case impression may run in model mode based on runtime/config.

## Events and Observability

`backend/core/events.py` emits structured events consumed by the frontend timeline:

| Event type | Purpose |
|-----------|---------|
| `STEP_START` / `STEP_END` | Pipeline stage boundaries with timing |
| `MODEL_CALLED` | Every MedGemma invocation with latency, cache status, and error tracking |
| `AGENT_DECISION` | Every model-vs-rules routing decision with rationale |
| `GUARDRAIL_FAIL` | Safety rule violations detected |
| `GUARDRAIL_PATCH_APPLIED` | Before/after snapshots of patched output |
| `MODEL_REASONING_START` / `END` | UI indicators for model inference in progress |
| `MODEL_WEIGHT_ASSIGNED` | Model-assigned evidence weights with rationale |
| `HIGHLIGHT` / `CANDIDATES` | KG node/edge highlights for graph visualization |

In default model mode, a typical case emits ~4.7 `MODEL_CALLED` events and ~4.9 `AGENT_DECISION` events, providing full auditability of every model interaction and routing choice.

## Session Endpoints

- `POST /session/start`
- `POST /session/{id}/message`

Sessions support update turns and explanation turns while preserving in-memory context.
