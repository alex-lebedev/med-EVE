# Demo Script for Aletheia

## Preparation

1. Ensure Python 3.8+ and dependencies installed
2. Run `./run_local.sh` or `cd backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000`
3. Backend API available at http://localhost:8000

## Demo Steps

### 1. Health Check
- Visit http://localhost:8000/health
- Confirms lite mode, device detection

### 2. Explore Cases
- GET /cases → List of 8 synthetic cases
- GET /cases/case_02_anemia_of_inflammation_gotcha → View gotcha case details

### 3. Run Gotcha Case
- POST /run {"case_id": "case_02_anemia_of_inflammation_gotcha"}
- Pipeline: normalize labs, select context, retrieve evidence, reason, guardrails
- Events show step timings and graph highlights
- Output: Inflammation pattern detected, TSAT recommended, no iron supplementation

### 4. Run Iron Deficiency Case
- POST /run {"case_id": "case_01_iron_deficiency_anemia"}
- Output: Deficiency pattern, iron supplementation considered

### 5. Guardrails in Action
- Simulate unsafe action in inflammation case → Guardrail FAIL
- Shows blocked recommendation with explanation

### 6. Run Tests
- `cd backend && python -m pytest tests/`
- `python evals/run_evals.py` → Eval summary

## Key Takeaways
- Safe, auditable reasoning pipeline
- Knowledge graph drives evidence
- Guardrails prevent unsafe recommendations
- Event protocol for UI animation
- Works offline in lite mode
