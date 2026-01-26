from core.guardrails import check_guardrails

def test_guardrails_on_gotcha():
    # Simulate inflammation pattern with iron supplementation
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [{"task": "Take iron supplements", "why": "Low ferritin", "risk": "low"}],
        "red_flags": []
    }
    case_card = {"signals": ["Inflammation-mediated iron sequestration"]}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'FAIL'
    assert any(r['id'] == 'GR_001' for r in report['failed_rules'])

def test_guardrails_pass():
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [{"task": "Schedule TSAT test", "why": "Differentiate", "risk": "low"}],
        "red_flags": []
    }
    case_card = {"signals": []}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'PASS'