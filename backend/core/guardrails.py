import yaml
import os

with open(os.path.join(os.path.dirname(__file__), '..', 'guardrails', 'guardrails.yml'), 'r') as f:
    GUARDRAILS = yaml.safe_load(f)['rules']

ALLOWED_BUCKETS = [
    "tests", "scheduling", "questions for clinician", "low-risk defaults"
]

def check_guardrails(reasoner_output, case_card, normalized_labs):
    failed_rules = []
    patches = []

    # GR_001: Inflammation and iron supplementation
    inflammation_pattern = "p_inflam_iron_seq" in case_card['signals']
    patient_actions = reasoner_output.get('patient_actions', [])
    for i, action in enumerate(patient_actions):
        if "iron" in action['task'].lower() and "supplement" in action['task'].lower() and inflammation_pattern:
            failed_rules.append({"id": "GR_001", "message": "Iron supplementation blocked under inflammation pattern."})
            patches.append({"op": "remove", "path": f"/patient_actions/{i}"})

    # GR_002: Hashimoto without antibodies (skip for now)

    # GR_003: No dosing
    for i, action in enumerate(patient_actions):
        if any(word in action['task'].lower() for word in ["mg", "dose", "supplement"]):
            failed_rules.append({"id": "GR_003", "message": "No dosing recommendations allowed."})
            patches.append({"op": "remove", "path": f"/patient_actions/{i}"})

    # GR_004: Allowed buckets
    for i, action in enumerate(patient_actions):
        task_lower = action['task'].lower()
        if not any(bucket in task_lower for bucket in ALLOWED_BUCKETS):
            failed_rules.append({"id": "GR_004", "message": f"Action '{action['task']}' not in allowed buckets."})
            patches.append({"op": "remove", "path": f"/patient_actions/{i}"})

    # GR_005: No invention
    all_markers = [lab['marker'] for lab in normalized_labs]
    hypotheses = reasoner_output.get('hypotheses', [])
    for h_idx, hypo in enumerate(hypotheses):
        evidence = hypo.get('evidence', [])
        for e_idx, ev in enumerate(evidence):
            if ev['marker'] not in all_markers:
                failed_rules.append({"id": "GR_005", "message": f"Marker '{ev['marker']}' not in input."})
                patches.append({"op": "remove", "path": f"/hypotheses/{h_idx}/evidence/{e_idx}"})

    status = "FAIL" if failed_rules else "PASS"
    return {
        "status": status,
        "failed_rules": failed_rules,
        "patches": patches
    }