# Architecture Documentation

## Overview

This document describes the current architecture of the Aletheia medical reasoning pipeline, focusing on the `/run` endpoint pipeline flow, response schema, event system, and MedGemma integration.

## Pipeline Flow (`backend/app.py:/run`)

The `/run` endpoint implements a 5-stage medical reasoning pipeline:

### 1. LAB_NORMALIZE
- **Module**: `backend/core/lab_normalizer.py`
- **Input**: Raw lab results from case data (`case['labs']`)
- **Process**:
  - Normalizes marker names (e.g., "Thyrotropin" → "TSH")
  - Converts units to standard units (e.g., Ferritin: ug/L → ng/mL)
  - Determines status: `LOW`, `NORMAL`, or `HIGH` based on reference ranges
- **Output**: List of normalized lab objects with `marker`, `value`, `unit`, `ref_low`, `ref_high`, `status`, `timestamp`
- **Events**: `STEP_START`, `STEP_END`

### 2. CONTEXT_SELECT
- **Module**: `backend/core/context_selector.py`
- **Input**: Normalized labs, patient context
- **Process**:
  - Extracts abnormal markers (status != 'NORMAL')
  - Maps markers to knowledge graph node IDs via `marker_to_node.yml`
  - **Agentic Decision**: Uses **Context Selection Agent** (MedGemma) if:
    - >3 abnormal markers (complex case)
    - Unusual marker combinations
    - Patient has comorbidities
  - Rule-based fallback for simple cases
  - Identifies pattern signals (e.g., `p_iron_def`, `p_hypothyroid`, `p_inflam_iron_seq`)
  - Builds a `CaseCard` with abnormal markers, signals, and patient context
  - Retrieves subgraph from knowledge graph (2-hop neighbors, max 60 nodes)
- **Output**: `CaseCard` dict and `subgraph` dict (nodes + edges)
- **Events**: `STEP_START`, `AGENT_DECISION`, `MODEL_CALLED` (if model used), `HIGHLIGHT`, `STEP_END`

### 3. EVIDENCE_SCORE
- **Module**: `backend/core/evidence_builder.py`
- **Input**: CaseCard, subgraph, normalized labs
- **Process**:
  - Initializes candidate pattern scores (baseline 0.5)
  - For each abnormal marker, finds edges connecting to pattern nodes
  - **Agentic Decision**: Uses **Evidence Weighting Agent** (MedGemma) for:
    - Rare marker/status combinations
    - Conflicting evidence
    - High-stakes decisions
  - Rule-based weights used for standard cases
  - Applies weighted scoring:
    - `SUPPORTS` relation: adds weight to pattern score
    - `CONTRADICTS` relation: subtracts weight from pattern score
  - Normalizes scores to [0, 1] range
  - Identifies top 5 discriminators by weight
- **Output**: `EvidenceBundle` dict with `subgraph`, `supports`, `contradictions`, `candidate_scores`, `top_discriminators`
- **Events**: `STEP_START`, `CANDIDATES`, `EVIDENCE_APPLIED`, `MODEL_WEIGHT_ASSIGNED` (if model used), `SCORE_UPDATE`, `STEP_END`

### 4. REASON
- **Module**: `backend/core/reasoner_medgemma.py`
- **Input**: CaseCard, EvidenceBundle
- **Process**:
  - **Lite Mode (Default)**:
    - Rule-based hypothesis generation from candidate scores
    - Generates multiple hypotheses for differential diagnosis
    - Hardcoded patient actions
  - **Model Mode (Agentic)**:
    - **Hypothesis Generation Agent** (Always Used):
      - Uses MedGemma to generate multiple hypotheses with nuanced reasoning
      - Maps evidence to knowledge graph edge IDs
      - Recommends next tests with rationale
      - Explains "what would change my mind"
    - **Test Recommendation Agent** (When Ambiguity Exists):
      - Called when top 2 hypotheses within 0.15 confidence
      - Prioritizes tests by clinical utility and cost-benefit
      - Explains expected impact of each test
    - **Action Generation Agent** (Always Used):
      - Generates context-aware patient actions
      - Considers patient age, comorbidities, clinical guidelines
      - Categorizes into safe buckets
- **Output**: `ReasonerOutput` dict with `hypotheses`, `patient_actions`, `red_flags`
- **Events**: `STEP_START`, `AGENT_DECISION`, `MODEL_CALLED`, `STEP_END`

### 5. GUARDRAILS
- **Module**: `backend/core/guardrails.py`
- **Input**: ReasonerOutput, CaseCard, normalized labs
- **Process**:
  - Checks rules defined in `backend/guardrails/guardrails.yml`:
    - **GR_001**: Blocks iron supplementation under inflammation pattern
    - **GR_003**: Removes dosing recommendations
    - **GR_004**: Validates action buckets (tests, scheduling, questions for clinician, low-risk defaults)
    - **GR_005**: Prevents invention of markers not in input
  - **Guardrail Explanation Agent** (When Guardrails Fail):
    - Uses MedGemma to generate educational explanations
    - Explains why guardrail triggered and what the risk would be
    - Suggests alternative safe actions
    - Provides clinical background
  - Generates patches (JSON Patch format) for failed rules
  - Applies patches to `reasoner_output` (supports 'remove' operations)
- **Output**: `GuardrailReport` dict with `status`, `failed_rules`, `patches`, `explanations` (model-generated)
- **Events**: `STEP_START`, `GUARDRAIL_FAIL`, `MODEL_CALLED` (if explanations generated), `GUARDRAIL_PATCH_APPLIED`, `STEP_END`

### Final Event
- **Event**: `FINAL_READY` emitted at end of pipeline

## Response Schema for `/run`

The `/run` endpoint returns a JSON object with the following structure:

```python
{
    "normalized_labs": List[Lab],  # Normalized lab results
    "case_card": CaseCard,         # Case summary with abnormal markers, signals
    "evidence_bundle": EvidenceBundle,  # Evidence scoring results
    "reasoner_output": ReasonerOutput,   # MedGemma reasoning output
    "guardrail_report": GuardrailReport, # Guardrail validation results
    "events": List[Event],         # Event stream for UI animation
    "timings": dict                # Currently empty, reserved for timing data
}
```

## Agentic Architecture

Aletheia uses MedGemma at **6 key decision points** throughout the pipeline, with agents deciding when to use the model vs. rule-based fallback:

### 1. Context Selection Agent
- **When**: Complex cases (>3 markers, unusual combinations, comorbidities)
- **Decision Logic**: `agent_manager.should_use_agent('context_selection', context)`
- **Value**: Identifies patterns rule-based system might miss

### 2. Evidence Weighting Agent
- **When**: Rare marker/status combinations, conflicting evidence
- **Decision Logic**: `agent_manager.should_use_agent('evidence_weighting', context)`
- **Value**: Context-aware dynamic weighting

### 3. Hypothesis Generation Agent
- **When**: Always (core reasoning step)
- **Decision Logic**: Always uses model in model mode
- **Value**: Multiple nuanced hypotheses with clinical reasoning

### 4. Test Recommendation Agent
- **When**: Ambiguity exists (top 2 hypotheses within 0.15 confidence) or no tests recommended
- **Decision Logic**: `agent_manager.should_use_agent('test_recommendation', context)`
- **Value**: Prioritized, evidence-based test recommendations

### 5. Action Generation Agent
- **When**: Always for action generation
- **Decision Logic**: Always uses model in model mode
- **Value**: Context-aware, patient-specific actions

### 6. Guardrail Explanation Agent
- **When**: When guardrail fails
- **Decision Logic**: `agent_manager.should_use_agent('guardrail_explanation', context)`
- **Value**: Educational explanations for clinicians

### Agent Manager (`backend/core/agent_manager.py`)

Unified interface for all agents:
- `should_use_agent(agent_type, context)` - Decision logic
- `call_agent(agent_type, context, data, events_list, step)` - Model calling wrapper
- Automatic fallback to rule-based when model unavailable
- Event emission for all agent decisions and model calls

## Knowledge Graph

- **Storage**: JSON file at `backend/kg/graph.json`
- **Access**: Via `KGStore` class in `backend/core/kg_store.py`
- **Structure**: Nodes (markers, patterns, conditions, tests) and edges (relations: SUPPORTS, CONTRADICTS, CAUSES, RECOMMENDS_TEST, etc.)
- **Subgraph Extraction**: 2-hop neighbors from abnormal marker nodes, max 60 nodes
- **Determinism**: Nodes and edges sorted for consistent ordering

## Dependencies

- **FastAPI**: Web framework
- **Pydantic**: Schema validation
- **PyYAML**: Configuration files
- **torch**: For MedGemma model loading
- **transformers**: For MedGemma model
- **huggingface_hub**: For model access
- **bitsandbytes**: Optional, for quantization
