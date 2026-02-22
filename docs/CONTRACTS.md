# Contract Definitions

This document defines the target contracts (data structures and protocols) for the med-EVE (Evidence Vector Engine) medical reasoning pipeline. These contracts represent the intended API surface and data flow between components.

## CaseCard Contract

**Purpose**: Represents a structured summary of the patient case with identified abnormal markers, signals, and context.

**Structure**:
```python
{
    "abnormal_markers": List[str],  # List of marker names with abnormal status
    "abnormal_marker_node_ids": List[str],  # Knowledge graph node IDs for abnormal markers
    "signals": List[str],  # Pattern IDs (e.g., "p_iron_def", "p_inflam_iron_seq")
    "patient_context": dict  # Patient metadata (age, gender, etc.)
}
```

**Contract Guarantees**:
- `abnormal_markers` must be non-empty if any labs are abnormal
- `signals` may be empty if no patterns match
- `patient_context` must be a dict (may be empty)

## EvidenceBundle Contract

**Purpose**: Contains evidence scoring results, subgraph, and claims that can be made.

**Structure**:
```python
{
    "subgraph": {
        "nodes": List[dict],  # Knowledge graph nodes
        "edges": List[dict]    # Knowledge graph edges
    },
    "supports": List[EvidenceItem],  # Evidence supporting hypotheses
    "contradictions": List[EvidenceItem],  # Evidence contradicting hypotheses
    "candidate_scores": dict,  # Pattern ID -> score mapping
    "top_discriminators": List[EvidenceItem]  # Top evidence items by weight
}
```

**EvidenceItem Structure**:
```python
{
    "pattern_id": str,
    "marker": str,
    "marker_status": str,  # "LOW", "NORMAL", "HIGH", or "REFERENCE_UNKNOWN" (unknown lab; UI shows "Reference unknown")
    "edge_id": str,
    "relation": str,  # "SUPPORTS" or "CONTRADICTS"
    "weight": float
}
```

## ReasonerOutput Contract

**Purpose**: The output from the reasoning engine (MedGemma or lite mode) containing hypotheses, actions, and red flags.

**Structure**:
```python
{
    "hypotheses": List[Hypothesis],
    "patient_actions": List[PatientAction],
    "red_flags": List[str]
}
```

**Hypothesis Structure**:
```python
{
    "id": str,
    "name": str,  # Condition/hypothesis name
    "confidence": float,  # Confidence score [0.0, 1.0]
    "evidence": List[Evidence],  # Supporting evidence
    "counter_evidence": List[Evidence],  # Contradicting evidence
    "next_tests": List[dict],  # Recommended next tests
    "what_would_change_my_mind": List[str]
}
```

**PatientAction Structure**:
```python
{
    "bucket": str,  # "tests", "scheduling", etc.
    "task": str,  # Action description
    "why": str,  # Reasoning for action
    "risk": str  # Risk level ("low", "medium", "high")
}
```

## Event Protocol Contract

**Purpose**: Defines the event-driven communication protocol for UI updates and pipeline observability.

### Event Base Structure

```python
{
    "ts": float,        # Unix timestamp (seconds since epoch)
    "step": str,        # Pipeline step (LAB_NORMALIZE, CONTEXT_SELECT, etc.)
    "type": str,        # Event type (STEP_START, HIGHLIGHT, etc.)
    "payload": dict     # Event-specific payload (may be empty)
}
```

### Step Values
- `LAB_NORMALIZE`
- `CONTEXT_SELECT`
- `EVIDENCE_SCORE`
- `REASON`
- `CRITIC`
- `GUARDRAILS`
- `CASE_IMPRESSION`
- `FINAL`

### EventType Values
- `STEP_START`
- `STEP_END`
- `HIGHLIGHT`
- `CANDIDATES`
- `EVIDENCE_APPLIED`
- `SCORE_UPDATE`
- `HYPOTHESIS_READY`
- `GUARDRAIL_FAIL`
- `GUARDRAIL_PATCH_APPLIED`
- `FINAL_READY`
- `MODEL_CALLED`
- `AGENT_DECISION`
- `MODEL_WEIGHT_ASSIGNED`
- `MODEL_REASONING_START`
- `MODEL_REASONING_END`

### Event Payload Contracts

#### MODEL_CALLED
```python
payload: {
    "agent_type": str,       # e.g. "ranking", "reasoning", "critic", "case_impression"
    "prompt_type": str,      # prompt category
    "response_time_ms": float,
    "status": str,           # "success" or "error"
    "cached": bool,          # whether response came from cache
    "error": str | None      # error message if status is "error"
}
```

#### AGENT_DECISION
```python
payload: {
    "agent_type": str,       # e.g. "hybrid_routing", "critic", "case_impression", "action_generation", "novel_insight"
    "decision": str,         # "use_model" or "use_rules"
    "rationale": str         # human-readable reason for the decision
}
```

#### HIGHLIGHT
```python
payload: {
    "node_ids": List[str],  # Knowledge graph node IDs to highlight
    "edge_ids": List[str],  # Knowledge graph edge IDs to highlight
    "label": str            # Optional label for the highlight
}
```

#### GUARDRAIL_FAIL
```python
payload: {
    "failed_rules": List[{
        "id": str,        # Rule ID (e.g., "GR_001")
        "message": str    # Human-readable failure message
    }]
}
```

#### GUARDRAIL_PATCH_APPLIED
```python
payload: {
    "before": dict,  # ReasonerOutput before patch
    "after": dict   # ReasonerOutput after patch
}
```

## Pipeline Response Contract

**Purpose**: The full pipeline result returned by `/run` and `/analyze`, and written to `output/final_output_{case_id}_{timestamp}.json`.

**Structure** (additive to previous contracts):
```python
{
    "normalized_labs": List[dict],
    "case_card": CaseCard,
    "evidence_bundle": EvidenceBundle,
    "reasoner_output": ReasonerOutput,
    "critic_result": dict,
    "guardrail_report": dict,
    "case_impression": str,       # Short patient/case overview (2–4 sentences)
    "suggested_kg_additions": {   # When dynamic nodes/edges were added
        "nodes": List[dict],      # Suggested nodes for KG (id, type, label, description, dynamic)
        "edges": List[dict]       # Suggested edges (from, to, relation, rationale)
    },
    "unlinked_markers": List[str], # Dynamic markers with no edges (see dynamic-only rule above)
    "unmappable_inputs": List[str], # Symptom/free-text tokens that could not be mapped to the graph
    "events": List[dict],
    "timings": dict,
    "model_usage": dict
}
```

- **normalized_labs**: Each lab has `marker`, `value`, `unit`, `ref_low`, `ref_high`, `status`, `timestamp`, and optionally `from_fallback`. **status** is `"LOW"`, `"HIGH"`, or `"NORMAL"` when the marker is known and reference range is certain; it is `"REFERENCE_UNKNOWN"` when the lab was parsed from free text without a known reference (e.g. fallback "name + number" or ref_low/ref_high both 0). UI should display "Reference unknown" for REFERENCE_UNKNOWN and only show HIGH/LOW/NORMAL when certain; when ref range is available (ref_low, ref_high not both 0), the biomarker window should show it (e.g. "value unit (status; ref ref_low–ref_high unit)").
- **case_impression**: Generated after guardrails; holistic summary for UI and saved JSON. Always present.
- **suggested_kg_additions**: Present when the pipeline created dynamic nodes or edges (markers not in the KG). Empty lists when no dynamic additions. Used for human review and KG integration.
- **unlinked_markers**: Markers that were added to the subgraph (e.g. from "Analyze from text") but have no edges to patterns. **Restricted to dynamic-only**: only nodes with `dynamic: true` in the subgraph are considered; KG markers are never listed as unlinked. Labels are derived from a stable `nid_to_label` map built from `abnormal_markers` (node ID per marker: `MARKER_TO_NODE.get(marker)` or `m_{marker.lower().replace(' ', '_')}`). Shown on the graph; UI displays "not yet linked to patterns" for these. Empty list when all dynamic markers have at least one edge.
- **unmappable_inputs**: List of symptom/free-text tokens that could not be mapped to the graph after rule-based suggestion and MedGemma judgment. Shown in the case overview/comment block when non-empty; message: "The following could not be mapped to the graph: [list]. Consider adding labs or standard terms."
- **Dynamic nodes**: Nodes not in the static knowledge graph (e.g. user-provided labs like sTfR) are created by the pipeline with `dynamic: true` and are visually distinguished on the graph (e.g. double border, distinct color).

## CaseCard ordering and label resolution

- **abnormal_marker_node_ids** is kept in the **same order** as **abnormal_markers** (case order) so that downstream code can pair by index. Do not sort `abnormal_marker_node_ids`; context_selector and app use a single source of truth for nid-to-label (built from `abnormal_markers` and the same ID formula).
