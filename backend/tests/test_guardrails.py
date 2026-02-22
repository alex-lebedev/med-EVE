from core.guardrails import check_guardrails

def test_guardrails_on_gotcha():
    # Simulate inflammation pattern with iron supplementation
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [{"task": "Take iron supplements", "why": "Low ferritin", "risk": "low"}],
        "red_flags": []
    }
    case_card = {"signals": ["p_inflam_iron_seq"]}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'FAIL'
    assert any(r['id'] == 'GR_001' for r in report['failed_rules'])

def test_guardrails_pass():
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [{"task": "Consider TSAT test (tests)", "why": "Differentiate", "risk": "low"}],
        "red_flags": [],
        "novel_actions": []
    }
    case_card = {"signals": []}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'PASS'


def test_guardrails_gr004_accepts_singular_test():
    """Task with 'test' (singular) not 'tests' should pass GR_004."""
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [{
            "task": "Consider sTfR test to differentiate between inflammation and iron deficiency",
            "why": "Both patterns possible",
            "risk": "low"
        }],
        "red_flags": [],
        "novel_actions": []
    }
    case_card = {"signals": []}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'PASS'
    assert not any(r['id'] == 'GR_004' for r in report['failed_rules'])

def test_guardrails_apply_to_novel_actions():
    reasoner_output = {
        "hypotheses": [],
        "patient_actions": [],
        "novel_actions": [{"task": "Take iron supplements", "why": "Low ferritin", "risk": "low"}],
        "red_flags": []
    }
    case_card = {"signals": ["p_inflam_iron_seq"]}
    normalized_labs = []
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report['status'] == 'FAIL'
    assert any(r['id'] == 'GR_001' and r.get("scope") == "novel_actions" for r in report['failed_rules'])
    assert any(p["path"].startswith("/novel_actions/") for p in report["patches"])


def test_guardrails_gr002_adds_antibody_test_for_hashimoto():
    reasoner_output = {
        "hypotheses": [{
            "id": "H1",
            "name": "Hashimoto thyroiditis (likely)",
            "confidence": 0.8,
            "evidence": [],
            "counter_evidence": [],
            "next_tests": [],
            "what_would_change_my_mind": []
        }],
        "patient_actions": [],
        "novel_actions": [],
        "red_flags": []
    }
    case_card = {"signals": ["p_hypothyroid"]}
    normalized_labs = [{"marker": "TSH", "value": 7.1, "status": "HIGH"}]
    report = check_guardrails(reasoner_output, case_card, normalized_labs)
    assert report["status"] == "FAIL"
    assert any(r["id"] == "GR_002" for r in report["failed_rules"])
    assert any(
        p["op"] == "add"
        and p["path"] == "/hypotheses/0/next_tests/-"
        and p.get("value", {}).get("test_id") == "t_tpo_ab"
        for p in report["patches"]
    )