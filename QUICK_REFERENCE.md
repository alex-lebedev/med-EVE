# Quick Reference: Understanding Aletheia Output

## 🎯 Main Output: `reasoner_output`

This is what you need to focus on. It contains:

### 1. Hypotheses (Possible Diagnoses)

```json
{
  "id": "H1",
  "name": "Iron deficiency anemia (likely)",
  "confidence": 0.85,  // 85% confidence
  "evidence": [...],     // Labs that support this
  "counter_evidence": [...],  // Labs that contradict this
  "next_tests": [...],   // Tests to confirm/rule out
  "what_would_change_my_mind": [...]  // Clinical reasoning
}
```

**Confidence Levels:**
- **0.85-1.0**: Very likely ✅
- **0.7-0.85**: Likely ✅
- **0.4-0.7**: Possible ⚠️
- **0.1-0.4**: Unlikely ❌

### 2. Patient Actions (What to Do)

```json
{
  "bucket": "tests",  // or "questions for clinician", "monitoring"
  "task": "Order ferritin test",
  "why": "Low ferritin suggests iron deficiency",
  "risk": "low"  // or "medium", "high"
}
```

**Action Buckets:**
- `tests`: Lab tests to order
- `questions for clinician`: Questions to ask
- `monitoring`: Things to watch
- `treatment`: Treatment (rare, usually blocked)

### 3. Red Flags (Urgent Issues)

Usually empty unless there's a critical finding.

---

## 📊 Other Important Outputs

### `evidence_bundle.candidate_scores`
Shows confidence for each pattern:
```json
{
  "p_iron_def": 0.85,
  "p_inflam_iron_seq": 0.15
}
```

### `guardrail_report.status`
- `"PASS"`: All safety checks passed ✅
- `"FAIL"`: Some recommendations were blocked ⚠️

### `model_usage.model_mode`
- `true`: Using actual MedGemma model 🤖
- `false`: Using rule-based fallback 📋

---

## 🔍 How to Read Results

1. **Look at hypotheses** → What are the possible diagnoses?
2. **Check confidence** → How certain is each diagnosis?
3. **Review evidence** → Which labs support/contradict?
4. **See next_tests** → What tests would help confirm?
5. **Read patient_actions** → What should you do next?
6. **Check guardrails** → Were any unsafe recommendations blocked?

---

## 📝 Example Interpretation

```json
{
  "hypotheses": [{
    "name": "Iron deficiency anemia (likely)",
    "confidence": 0.85,
    "evidence": [
      {"marker": "Ferritin", "status": "LOW"},
      {"marker": "Iron", "status": "LOW"}
    ],
    "next_tests": [
      {"label": "Ferritin measurement", "rationale": "To confirm"}
    ]
  }],
  "patient_actions": [{
    "task": "Order ferritin test",
    "why": "Low ferritin suggests iron deficiency",
    "risk": "low"
  }]
}
```

**Translation:**
- **Diagnosis**: Iron deficiency anemia (85% confident)
- **Evidence**: Low ferritin and iron support this
- **Action**: Order ferritin test (low risk)
- **Reasoning**: Low ferritin is a key indicator of iron deficiency

---

## 🚀 Quick Commands

```bash
# Run a case via API
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "case_01_iron_deficiency_anemia"}'

# List all cases
curl http://localhost:8000/cases

# Check health/model status
curl http://localhost:8000/health
```

---

## 📚 Full Documentation

- **USER_GUIDE.md**: Complete guide with examples
- **docs/USE_CASE_WALKTHROUGH.md**: Detailed case walkthrough
- **docs/ARCHITECTURE.md**: System design details
