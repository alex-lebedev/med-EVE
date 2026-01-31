"""Tests for case_impression: generate_case_impression returns non-empty string in lite mode."""
from core.case_impression import generate_case_impression


def test_generate_case_impression_lite_non_empty():
    """Lite mode: minimal case_card and reasoner_output yield non-empty impression."""
    case_card = {
        "abnormal_markers": ["Ferritin", "Iron"],
        "patient_context": {},
    }
    reasoner_output = {
        "hypotheses": [
            {"id": "H1", "name": "Iron deficiency anemia (likely)", "confidence": 0.8},
        ],
        "patient_actions": [],
        "red_flags": [],
    }
    guardrail_report = {"status": "PASS", "failed_rules": []}
    impression = generate_case_impression(case_card, reasoner_output, guardrail_report)
    assert isinstance(impression, str)
    assert len(impression) > 0


def test_generate_case_impression_guardrail_fail_mentions_safety():
    """When guardrails fail, impression should mention safety adjustment in lite mode."""
    case_card = {"abnormal_markers": ["TSH"], "patient_context": {}}
    reasoner_output = {"hypotheses": [], "patient_actions": [], "red_flags": []}
    guardrail_report = {"status": "FAIL", "failed_rules": [{"id": "GR_001", "message": "Unsafe"}]}
    impression = generate_case_impression(case_card, reasoner_output, guardrail_report)
    assert "adjusted" in impression.lower() or "safety" in impression.lower()
