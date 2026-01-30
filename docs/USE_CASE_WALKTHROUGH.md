# Use Case Walkthrough: Agentic MedGemma in Action

## Overview

This document provides a detailed, step-by-step walkthrough of how the agentic med-EVE system processes a new case, demonstrating MedGemma usage at each decision point.

---

## Case: Complex Anemia Presentation

**Patient**: 45-year-old female  
**Chief Complaint**: Fatigue, weakness  
**Labs**:
- hsCRP: 15.2 mg/L (HIGH, ref: <3.0)
- Ferritin: 180 ng/mL (HIGH, ref: 15-150)
- Iron: 45 ug/dL (LOW, ref: 60-170)
- TSAT: 12% (LOW, ref: 20-50)
- Hemoglobin: 10.2 g/dL (LOW, ref: 12.0-15.5)
- RDW: 13.5% (NORMAL, ref: 11.5-14.5)
- MCV: 78 fL (LOW, ref: 80-100)

---

## Step-by-Step Processing

### Step 1: LAB_NORMALIZE
**Agent Used**: None (deterministic)

**Process**:
- Normalizes marker names
- Converts units
- Determines status (HIGH/LOW/NORMAL)

**Output**: 6 abnormal markers identified

**UI Display**: Abnormal labs panel shows 6 markers

---

### Step 2: CONTEXT_SELECT
**Agent Used**: ✅ **Context Selection Agent (MedGemma)**

**Decision Logic**: 
- 6 abnormal markers → Complex case (>3 threshold)
- **Decision**: Use MedGemma

**MedGemma Call**:
```
Prompt: "Given these abnormal labs: hsCRP HIGH (15.2), Ferritin HIGH (180), 
Iron LOW (45), TSAT LOW (12%), Hb LOW (10.2), RDW NORMAL (13.5), MCV LOW (78),
what clinical patterns should we consider?"

Model Response:
{
  "patterns": [
    {
      "pattern_id": "p_inflam_iron_seq",
      "confidence": 0.9,
      "rationale": "Elevated CRP with high ferritin but low iron/TSAT is classic 
      for inflammation-mediated iron sequestration. High ferritin acts as acute 
      phase reactant."
    },
    {
      "pattern_id": "p_iron_def",
      "confidence": 0.4,
      "rationale": "Low iron, TSAT, and MCV suggest iron deficiency, but high 
      ferritin argues against. Could be mixed picture requiring sTfR to differentiate."
    }
  ],
  "missing_tests": ["sTfR", "TIBC"],
  "reasoning": "Mixed inflammatory and iron deficiency picture. sTfR needed to 
  differentiate true deficiency from inflammation-mediated sequestration."
}
```

**Value Added**:
- ✅ Identifies both patterns (rule-based might miss iron deficiency)
- ✅ Recognizes ambiguity
- ✅ Suggests missing tests upfront
- ✅ Provides clinical reasoning

**Event Emitted**: `AGENT_DECISION` (use_model), `MODEL_CALLED` (success, ~800ms)

**Output**: CaseCard with both patterns identified

**UI Display**: 
- Graph shows both pattern nodes highlighted
- Agent Activity panel shows "Context Selection: 🤖 Using Model"

---

### Step 3: EVIDENCE_SCORE
**Agent Used**: ✅ **Evidence Weighting Agent (MedGemma)** - Selective

**Process**:
1. Initialize candidate scores: `p_inflam_iron_seq: 0.5`, `p_iron_def: 0.5`
2. For each evidence item:
   - **Standard items** (hsCRP HIGH → inflammation): Use rule-based weight (0.8)
   - **Complex item** (Ferritin HIGH → inflammation): **Call MedGemma**

**MedGemma Call for Ferritin**:
```
Prompt: "Evaluate this evidence: Ferritin HIGH (180 ng/mL) SUPPORTS 
p_inflam_iron_seq. Context: hsCRP 15.2 (HIGH), Iron 45 (LOW), TSAT 12% (LOW).
What weight should this have?"

Model Response:
{
  "weight": 0.85,
  "rationale": "High ferritin in context of inflammation with low iron/TSAT 
  strongly supports inflammation-mediated sequestration. This is a classic pattern. 
  Weight increased from baseline 0.7 to 0.85 due to perfect alignment with 
  expected findings.",
  "confidence": 0.95
}
```

**Value Added**:
- ✅ Context-aware weighting (0.85 vs. rule-based 0.7)
- ✅ Explains why weight is higher
- ✅ Handles complex marker interactions

**Event Emitted**: `MODEL_WEIGHT_ASSIGNED` (Ferritin, HIGH, SUPPORTS, p_inflam_iron_seq, 0.85)

**Score Updates** (with model weighting):
- `p_inflam_iron_seq`: 0.5 + 0.8 (hsCRP) + 0.85 (Ferritin) = 2.15 → normalized to 0.95
- `p_iron_def`: 0.5 - 0.6 (Ferritin contradicts) = -0.1 → normalized to 0.35

**UI Display**: 
- Pattern scores update in real-time
- Evidence items show model-assigned weights
- Reasoning trace shows model rationale

---

### Step 4: REASON - Hypothesis Generation
**Agent Used**: ✅ **Hypothesis Generation Agent (MedGemma)** - Always Used

**MedGemma Call**:
```
Prompt: "Generate differential diagnosis hypotheses from:
- Candidate patterns: p_inflam_iron_seq (0.95), p_iron_def (0.35)
- Evidence: [detailed evidence bundle]
- Patient: 45-year-old female, fatigue

Return structured hypotheses with confidence, evidence, next tests, 
and what would change your mind."

Model Response:
{
  "hypotheses": [
    {
      "id": "H1",
      "name": "Anemia of inflammation (likely)",
      "confidence": 0.85,
      "evidence": [
        {"marker": "hsCRP", "status": "HIGH", "edge_id": "e_001"},
        {"marker": "Ferritin", "status": "HIGH", "edge_id": "e_002"}
      ],
      "counter_evidence": [
        {"marker": "Iron", "status": "LOW", "edge_id": "e_003"}
      ],
      "next_tests": [
        {
          "test_id": "t_stfr",
          "label": "Soluble transferrin receptor (sTfR)",
          "rationale": "sTfR will help confirm this is inflammation-mediated 
          rather than true iron deficiency. If normal, confirms inflammation."
        }
      ],
      "what_would_change_my_mind": [
        "If sTfR is elevated (>2.5 mg/L), suggests true iron deficiency 
        coexisting with inflammation",
        "If CRP normalizes but iron remains low, shifts toward iron deficiency"
      ],
      "reasoning": "The pattern of elevated CRP, high ferritin (acute phase 
      reactant), and low iron/TSAT is classic for anemia of chronic disease. 
      However, the low MCV and very low TSAT raise possibility of coexisting 
      iron deficiency. sTfR is the key differentiator."
    },
    {
      "id": "H2",
      "name": "Iron deficiency anemia (possible)",
      "confidence": 0.35,
      ...
    }
  ],
  "patient_actions": [...],
  "red_flags": []
}
```

**Value Added**:
- ✅ **Multiple hypotheses** with nuanced reasoning
- ✅ **Confidence scores** reflect clinical uncertainty
- ✅ **Evidence mapping** to knowledge graph edges
- ✅ **Next tests** with clear rationale
- ✅ **"What would change my mind"** shows clinical thinking

**Event Emitted**: `MODEL_CALLED` (hypothesis_generation, success, ~1200ms)

**UI Display**:
- Two hypothesis cards, sorted by confidence
- Color-coded confidence badges
- Evidence counts shown
- Next tests listed with rationale

---

### Step 5: REASON - Test Recommendation (Ambiguity Detected)
**Agent Used**: ✅ **Test Recommendation Agent (MedGemma)**

**Decision Logic**: 
- Top 2 hypotheses: 0.85 vs 0.35 (difference = 0.5)
- Ambiguity threshold: 0.15
- **Decision**: Ambiguity exists → Call MedGemma

**MedGemma Call**:
```
Prompt: "Given these hypotheses with ambiguity:
1. Anemia of inflammation (85% confidence)
2. Iron deficiency anemia (35% confidence)

What tests would help differentiate? Prioritize by clinical utility."

Model Response:
{
  "recommended_tests": [
    {
      "test_id": "t_stfr",
      "label": "Soluble transferrin receptor",
      "priority": "high",
      "rationale": "sTfR is the gold standard for differentiating iron 
      deficiency from anemia of inflammation. Elevated in deficiency, normal 
      in inflammation. Cost-effective and readily available.",
      "expected_impact": "If elevated (>2.5 mg/L): Increases iron deficiency 
      confidence to 80%, suggests coexisting deficiency. If normal: Confirms 
      inflammation-mediated anemia, decreases iron deficiency confidence to 10%.",
      "cost_benefit": "Low cost, high diagnostic value"
    }
  ]
}
```

**Value Added**:
- ✅ **Prioritized recommendations** (high/medium/low)
- ✅ **Expected impact** of each test
- ✅ **Cost-benefit analysis**
- ✅ **Clinical utility reasoning**

**Event Emitted**: `MODEL_CALLED` (test_recommendation, success, ~600ms)

**UI Display**: Tests shown with priority badges and detailed rationale

---

### Step 6: REASON - Action Generation
**Agent Used**: ✅ **Action Generation Agent (MedGemma)** - Always Used

**MedGemma Call**:
```
Prompt: "Generate patient-specific actions based on:
- Hypotheses: [H1, H2]
- Evidence: [evidence bundle]
- Patient: 45-year-old female, fatigue"

Model Response:
{
  "patient_actions": [
    {
      "bucket": "tests",
      "task": "Order sTfR test to differentiate between inflammation and 
      iron deficiency",
      "why": "Current labs are ambiguous. sTfR will definitively distinguish 
      between anemia of inflammation (normal sTfR) and iron deficiency 
      (elevated sTfR), even in the presence of inflammation.",
      "risk": "low"
    },
    {
      "bucket": "questions for clinician",
      "task": "Consider underlying cause of inflammation if sTfR confirms 
      inflammation-mediated anemia",
      "why": "Anemia of inflammation is a symptom, not a diagnosis. Need to 
      identify and treat underlying inflammatory condition.",
      "risk": "low"
    }
  ]
}
```

**Value Added**:
- ✅ Context-aware actions
- ✅ Patient-specific recommendations
- ✅ Clear reasoning for each action

**Event Emitted**: `MODEL_CALLED` (action_generation, success, ~700ms)

---

### Step 7: GUARDRAILS
**Agent Used**: Rule-based (no failure) or ✅ **Guardrail Explanation Agent** (if failure)

**Process**:
- Check rules
- In this case: No guardrail failures
- If failure occurred → Call MedGemma for explanation

**Example (If Failure)**:
```
Guardrail GR_001 triggered: Iron supplementation blocked

MedGemma Call:
"Explain why iron supplementation is blocked in this case with inflammation."

Model Response:
{
  "explanation": "Iron supplementation during active inflammation (hsCRP 15.2) 
  is contraindicated because: (1) Inflammation sequesters iron in macrophages, 
  making oral iron ineffective and potentially harmful, (2) Excess iron promotes 
  oxidative stress and can worsen inflammation, (3) Iron can feed bacterial 
  growth in chronic infections. The correct approach is to treat the underlying 
  inflammation first, then reassess iron status.",
  "risk_level": "high",
  "alternative_actions": [
    "Treat underlying inflammatory condition",
    "Monitor iron levels after inflammation resolves",
    "Consider IV iron only if severe deficiency persists after inflammation treatment"
  ]
}
```

**Value Added**:
- ✅ Educational explanations for clinicians
- ✅ Risk assessment
- ✅ Alternative recommendations

---

## Summary: Model Usage in This Case

| Step | Agent | Model Called? | Value Added |
|------|-------|--------------|-------------|
| LAB_NORMALIZE | None | No | Deterministic |
| CONTEXT_SELECT | Context Selection | ✅ Yes | Identified both patterns, suggested tests |
| EVIDENCE_SCORE | Evidence Weighting | ✅ Yes (selective) | Context-aware weighting for Ferritin |
| REASON | Hypothesis Generation | ✅ Yes | Multiple hypotheses, nuanced reasoning |
| REASON | Test Recommendation | ✅ Yes | Prioritized, evidence-based tests |
| REASON | Action Generation | ✅ Yes | Context-aware patient actions |
| GUARDRAILS | Explanation | No (no failure) | Would explain if triggered |

**Total Model Calls**: 5  
**Total Value**: Each call adds unique clinical insight and reasoning

---

## Key Benefits Demonstrated

1. **Transparency**: Every model call is visible with reasoning
2. **Nuance**: Model handles complex cases rule-based system would miss
3. **Education**: Explanations help clinicians understand reasoning
4. **Flexibility**: Model adapts to case complexity
5. **Safety**: Guardrails + explanations ensure safe recommendations
6. **Agentic**: Model decides when to use itself based on case complexity

---

## UI Features

- **Agent Activity Panel**: Shows which agents were called, model vs. rules
- **Reasoning Trace**: Displays model reasoning, agent decisions, timing
- **Model Usage Stats**: Shows total model calls and agent decisions
- **Visual Indicators**: Color-coded badges for model vs. rule-based decisions

---

## Performance

- **Model Calls**: 5 calls for this complex case
- **Total Inference Time**: ~3.5 seconds (with caching)
- **Response Time per Call**: 600-1200ms
- **Caching**: Repeated prompts cached for faster response

---

## Next Steps

1. Test on all 8 test cases
2. Validate performance targets
3. Create video walkthrough
4. Final submission preparation
