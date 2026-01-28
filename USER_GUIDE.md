# User Guide: Running Cases and Understanding Output

## Table of Contents
1. [Running New Cases](#running-new-cases)
2. [Understanding the Output](#understanding-the-output)
3. [Interpreting Model Recommendations](#interpreting-model-recommendations)
4. [API Usage](#api-usage)
5. [Creating Custom Cases](#creating-custom-cases)

---

## Running New Cases

### Method 1: Using the Web UI

1. **Start the demo:**
   ```bash
   source venv/bin/activate  # If not already activated
   make demo
   ```

2. **Open the browser:**
   - The demo should open automatically at `http://localhost:8080`
   - If not, manually navigate to that URL

3. **Select a case:**
   - Use the case selector dropdown at the top
   - Or add `?case=case_01_iron_deficiency_anemia` to the URL
   - Available cases:
     - `case_01_iron_deficiency_anemia`
     - `case_02_anemia_of_inflammation_gotcha`
     - `case_03_subclinical_hypothyroid_dyslipidemia`
     - `case_04_primary_hypothyroid`
     - `case_05_healthy_control`
     - `case_06_unit_mismatch_missing_units`
     - `case_07_borderline_values_trend`
     - `case_08_conflicting_markers_insufficient_data`

4. **Run the case:**
   - Click "Run Pipeline" button
   - Or add `&autoplay=true` to URL for auto-run

### Method 2: Using the API (Command Line)

```bash
# List available cases
curl http://localhost:8000/cases

# Get a specific case
curl http://localhost:8000/cases/case_01_iron_deficiency_anemia

# Run a case through the pipeline
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "case_01_iron_deficiency_anemia"}'

# Run with model mode (if model is loaded)
export MODE=model
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "case_01_iron_deficiency_anemia"}'
```

### Method 3: Using Python

```python
import requests
import json

# Run a case
response = requests.post(
    "http://localhost:8000/run",
    json={"case_id": "case_01_iron_deficiency_anemia"}
)

result = response.json()

# Print hypotheses
for hypo in result['reasoner_output']['hypotheses']:
    print(f"{hypo['name']}: {hypo['confidence']:.0%} confidence")
    print(f"  Evidence: {len(hypo['evidence'])} items")
    print(f"  Next tests: {[t['label'] for t in hypo.get('next_tests', [])]}")
    print()
```

---

## Understanding the Output

The pipeline returns a comprehensive JSON structure. Here's what each part means:

### 1. **normalized_labs**
Lab values that have been normalized (units converted, status determined).

```json
{
  "marker": "Ferritin",
  "value": 12,
  "unit": "ng/mL",
  "status": "LOW",  // HIGH, LOW, or NORMAL
  "ref_low": 15,
  "ref_high": 150
}
```

**What to look for:**
- `status`: Shows which markers are abnormal
- `value` vs `ref_low`/`ref_high`: Shows how far outside normal range

### 2. **case_card**
Summary of the case after context selection.

```json
{
  "abnormal_markers": ["Ferritin", "Iron", "TSAT", "Hb", "MCV"],
  "signals": ["p_iron_def", "p_inflam_iron_seq"],
  "patient_context": {
    "vegan": true,
    "fatigue": true
  }
}
```

**What to look for:**
- `abnormal_markers`: Which labs are out of range
- `signals`: Clinical patterns identified (pattern IDs)
- `patient_context`: Relevant patient information

### 3. **evidence_bundle**
Evidence supporting or contradicting each pattern.

```json
{
  "candidate_scores": {
    "p_iron_def": 0.85,
    "p_inflam_iron_seq": 0.15
  },
  "supports": [
    {
      "marker": "Ferritin",
      "marker_status": "LOW",
      "pattern_id": "p_iron_def",
      "edge_id": "e_ferritin_low_iron_def"
    }
  ],
  "contradictions": [],
  "top_discriminators": [
    {
      "marker": "Ferritin",
      "marker_status": "LOW",
      "pattern_id": "p_iron_def",
      "weight": 0.9
    }
  ]
}
```

**What to look for:**
- `candidate_scores`: Confidence for each pattern (0-1 scale)
- `supports`: Evidence that supports each pattern
- `contradictions`: Evidence that contradicts patterns
- `top_discriminators`: Most important evidence items

### 4. **reasoner_output** ⭐ **MOST IMPORTANT**

This is the main output with hypotheses and recommendations.

```json
{
  "hypotheses": [
    {
      "id": "H1",
      "name": "Iron deficiency anemia (likely)",
      "confidence": 0.85,  // 0-1 scale, 85% confidence
      "evidence": [
        {
          "marker": "Ferritin",
          "status": "LOW",
          "edge_id": "e_001"
        }
      ],
      "counter_evidence": [],
      "next_tests": [
        {
          "test_id": "t_ferritin",
          "label": "Ferritin measurement",
          "rationale": "To confirm iron deficiency"
        }
      ],
      "what_would_change_my_mind": [
        "If ferritin increases with iron supplementation",
        "If inflammation markers appear"
      ]
    }
  ],
  "patient_actions": [
    {
      "bucket": "tests",
      "task": "Order ferritin test to confirm iron deficiency",
      "why": "Low ferritin strongly suggests iron deficiency",
      "risk": "low"
    }
  ],
  "red_flags": []
}
```

**Key Fields Explained:**

#### **hypotheses** (Array of possible diagnoses)
- `name`: The condition name (e.g., "Iron deficiency anemia (likely)")
- `confidence`: 0-1 scale (0.85 = 85% confidence)
  - `>= 0.7`: "likely"
  - `0.4-0.7`: "possible"
  - `< 0.4`: "unlikely but considered"
- `evidence`: Lab markers that support this hypothesis
- `counter_evidence`: Lab markers that contradict this hypothesis
- `next_tests`: Recommended tests to confirm/rule out
- `what_would_change_my_mind`: What would make the system change its diagnosis

#### **patient_actions** (What to do next)
- `bucket`: Category ("tests", "questions for clinician", "monitoring")
- `task`: Specific action to take
- `why`: Reasoning for this action
- `risk`: Risk level ("low", "medium", "high")

#### **red_flags** (Urgent concerns)
- Array of urgent issues that need immediate attention
- Usually empty unless there's a critical finding

### 5. **guardrail_report**
Safety checks that were applied.

```json
{
  "status": "PASS",  // or "FAIL"
  "failed_rules": [],
  "patches": []
}
```

**What to look for:**
- `status`: "PASS" means all safety checks passed
- `failed_rules`: If status is "FAIL", shows which rules failed
- `patches`: Automatic fixes applied to unsafe recommendations

### 6. **model_usage**
Statistics about model usage.

```json
{
  "model_calls": 5,
  "agent_decisions": 6,
  "model_mode": true
}
```

**What to look for:**
- `model_calls`: How many times the model was called
- `agent_decisions`: How many agents made decisions
- `model_mode`: Whether model mode is active (vs. lite mode)

---

## Interpreting Model Recommendations

### Understanding Confidence Scores

- **0.85-1.0 (85-100%)**: Very likely diagnosis
  - Strong evidence, few contradictions
  - Action: Proceed with treatment plan

- **0.7-0.85 (70-85%)**: Likely diagnosis
  - Good evidence, some uncertainty
  - Action: Consider additional tests to confirm

- **0.4-0.7 (40-70%)**: Possible diagnosis
  - Moderate evidence, significant uncertainty
  - Action: Order recommended tests to differentiate

- **0.1-0.4 (10-40%)**: Unlikely but considered
  - Weak evidence, many contradictions
  - Action: Rule out with tests if clinically relevant

- **< 0.1 (< 10%)**: Not shown (filtered out)

### Reading Patient Actions

**Action Buckets:**
- `tests`: Laboratory tests to order
- `questions for clinician`: Questions to ask the patient/clinician
- `monitoring`: Things to watch over time
- `treatment`: Treatment recommendations (rare, usually blocked by guardrails)

**Risk Levels:**
- `low`: Safe to proceed
- `medium`: Proceed with caution
- `high`: Requires careful consideration

### Understanding "What Would Change My Mind"

This field shows the system's clinical reasoning:
- What evidence would strengthen the diagnosis
- What evidence would weaken it
- What alternative diagnoses are still possible

**Example:**
```json
"what_would_change_my_mind": [
  "If ferritin increases with iron supplementation",
  "If inflammation markers appear",
  "If sTfR is elevated (suggests true iron deficiency)"
]
```

This means:
- ✅ If ferritin responds to iron → confirms diagnosis
- ⚠️ If inflammation markers appear → might be anemia of inflammation instead
- ⚠️ If sTfR is high → suggests coexisting iron deficiency

---

## API Usage

### Full API Response Structure

```python
{
  "normalized_labs": [...],      # Step 1: Normalized lab values
  "case_card": {...},            # Step 2: Case summary
  "evidence_bundle": {...},      # Step 3: Evidence analysis
  "reasoner_output": {          # Step 4: Main output ⭐
    "hypotheses": [...],
    "patient_actions": [...],
    "red_flags": []
  },
  "guardrail_report": {...},     # Step 5: Safety checks
  "events": [...],               # Complete event log
  "model_usage": {...}           # Model statistics
}
```

### Extracting Key Information

```python
import requests

response = requests.post("http://localhost:8000/run", 
                        json={"case_id": "case_01_iron_deficiency_anemia"})
result = response.json()

# Get top hypothesis
top_hypo = result['reasoner_output']['hypotheses'][0]
print(f"Top Diagnosis: {top_hypo['name']}")
print(f"Confidence: {top_hypo['confidence']:.0%}")

# Get recommended tests
for test in top_hypo.get('next_tests', []):
    print(f"  - {test['label']}")

# Get patient actions
for action in result['reasoner_output']['patient_actions']:
    print(f"{action['bucket']}: {action['task']}")
    print(f"  Why: {action['why']}")
```

---

## Creating Custom Cases

### Case File Format

Create a JSON file in `backend/data_synth/cases/`:

```json
{
  "case_id": "my_custom_case",
  "patient": {
    "age": 45,
    "sex": "F",
    "context": {
      "vegan": false,
      "fatigue": true,
      "pregnant": false
    }
  },
  "labs": [
    {
      "marker": "Ferritin",
      "value": 12,
      "unit": "ng/mL",
      "ref_low": 15,
      "ref_high": 150,
      "timestamp": "2026-01-10"
    },
    {
      "marker": "Hb",
      "value": 10.5,
      "unit": "g/dL",
      "ref_low": 12,
      "ref_high": 16,
      "timestamp": "2026-01-10"
    }
  ],
  "meta": {
    "scenario": "custom_scenario"
  }
}
```

### Required Fields

- `case_id`: Unique identifier
- `patient.age`: Patient age
- `patient.sex`: "M" or "F"
- `patient.context`: Any relevant context (optional fields)
- `labs`: Array of lab results
  - `marker`: Lab marker name (must match knowledge graph)
  - `value`: Numeric value
  - `unit`: Unit of measurement
  - `ref_low`: Lower reference range
  - `ref_high`: Upper reference range
  - `timestamp`: Date (ISO format)

### Running Your Custom Case

```bash
# Restart the backend to load new case
make stop
make run

# Then use the case_id in API or UI
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "my_custom_case"}'
```

### Available Lab Markers

Check `backend/core/marker_to_node.yml` for supported markers. Common ones:
- Ferritin, Iron, TSAT, Hb, MCV, RDW
- hsCRP, WBC, Platelets
- TSH, FT4, FT3
- Glucose, Creatinine
- And many more...

---

## Tips for Interpreting Results

1. **Start with hypotheses**: These are the main diagnoses
2. **Check confidence**: Higher confidence = stronger evidence
3. **Review evidence**: See which labs support/contradict each hypothesis
4. **Look at next_tests**: These help differentiate between hypotheses
5. **Read patient_actions**: These tell you what to do next
6. **Check guardrails**: If status is "FAIL", unsafe recommendations were blocked
7. **Review model_usage**: See if model was used (model_mode: true) or rules (model_mode: false)

---

## Example: Complete Workflow

```python
import requests
import json

# 1. Run a case
response = requests.post(
    "http://localhost:8000/run",
    json={"case_id": "case_01_iron_deficiency_anemia"}
)
result = response.json()

# 2. Extract key information
print("=" * 60)
print("CASE ANALYSIS")
print("=" * 60)

# Abnormal labs
abnormal = [lab for lab in result['normalized_labs'] 
            if lab['status'] != 'NORMAL']
print(f"\nAbnormal Labs: {len(abnormal)}")
for lab in abnormal:
    print(f"  - {lab['marker']}: {lab['value']} {lab['unit']} ({lab['status']})")

# Top hypothesis
hypo = result['reasoner_output']['hypotheses'][0]
print(f"\nTop Diagnosis: {hypo['name']}")
print(f"Confidence: {hypo['confidence']:.0%}")

# Evidence
print(f"\nSupporting Evidence:")
for ev in hypo['evidence']:
    print(f"  ✅ {ev['marker']} ({ev['status']})")

if hypo['counter_evidence']:
    print(f"\nContradicting Evidence:")
    for ev in hypo['counter_evidence']:
        print(f"  ❌ {ev['marker']} ({ev['status']})")

# Recommended tests
if hypo.get('next_tests'):
    print(f"\nRecommended Tests:")
    for test in hypo['next_tests']:
        print(f"  - {test['label']}")

# Patient actions
if result['reasoner_output']['patient_actions']:
    print(f"\nRecommended Actions:")
    for action in result['reasoner_output']['patient_actions']:
        print(f"  [{action['bucket']}] {action['task']}")
        print(f"    Why: {action['why']}")

# Guardrails
if result['guardrail_report']['status'] == 'FAIL':
    print(f"\n⚠️  Guardrails Failed:")
    for rule in result['guardrail_report']['failed_rules']:
        print(f"  - {rule['rule_id']}: {rule['reason']}")

print("\n" + "=" * 60)
```

---

## Next Steps

- See `docs/ARCHITECTURE.md` for system design details
- See `docs/USE_CASE_WALKTHROUGH.md` for detailed case walkthrough
- See `README.md` for general information
- Check `backend/prompts/` to see what prompts the model uses
