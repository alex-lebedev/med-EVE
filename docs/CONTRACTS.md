# Contract Definitions

This document defines the target contracts (data structures and protocols) for the Aletheia medical reasoning pipeline. These contracts represent the intended API surface and data flow between components.

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
    "marker_status": str,  # "LOW", "NORMAL", "HIGH"
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
- `GUARDRAILS`
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

### Event Payload Contracts

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
