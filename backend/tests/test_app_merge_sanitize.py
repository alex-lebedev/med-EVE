"""Tests for app._merge_reasoner_output and app._sanitize_reasoner_output."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _merge_reasoner_output, _sanitize_reasoner_output


def test_merge_reasoner_output_new_none_returns_prev():
    prev = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}], "patient_actions": []}
    result = _merge_reasoner_output(prev, None)
    assert result is not prev
    assert result.get("hypotheses") == prev["hypotheses"]


def test_merge_reasoner_output_new_invalid_returns_prev():
    prev = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}], "patient_actions": []}
    new = {"hypotheses_valid": False, "hypotheses": []}
    result = _merge_reasoner_output(prev, new)
    assert result is not prev
    assert len(result.get("hypotheses", [])) == 1
    assert result["hypotheses"][0]["name"] == "Anemia"


def test_merge_reasoner_output_prev_none_returns_new():
    new = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}], "patient_actions": []}
    result = _merge_reasoner_output(None, new)
    assert result == new


def test_merge_reasoner_output_same_key_confidence_changed():
    prev = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.5, "evidence": []}], "patient_actions": []}
    new = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.9, "evidence": []}], "patient_actions": []}
    result = _merge_reasoner_output(prev, new)
    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["confidence"] == 0.9


def test_merge_reasoner_output_new_hypothesis_appended():
    prev = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}], "patient_actions": []}
    new = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}, {"id": "H2", "name": "Hypothyroid", "confidence": 0.3}], "patient_actions": []}
    result = _merge_reasoner_output(prev, new)
    assert len(result["hypotheses"]) == 2
    names = [h["name"] for h in result["hypotheses"]]
    assert "Anemia" in names and "Hypothyroid" in names


def test_merge_reasoner_output_previous_only_preserved():
    prev = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.8}, {"id": "H2", "name": "Other", "confidence": 0.2}], "patient_actions": []}
    new = {"hypotheses": [{"id": "H1", "name": "Anemia", "confidence": 0.85}], "patient_actions": []}
    result = _merge_reasoner_output(prev, new)
    assert len(result["hypotheses"]) == 2
    names = [h["name"] for h in result["hypotheses"]]
    assert "Anemia" in names and "Other" in names


def test_sanitize_reasoner_output_drops_action_without_task():
    out = {"hypotheses": [], "patient_actions": [{"task": "Do X", "why": "Y", "risk": "low"}, {"why": "Z", "risk": "low"}, {"task": "", "why": "W", "risk": "low"}]}
    result = _sanitize_reasoner_output(out)
    assert len(result["patient_actions"]) == 1
    assert result["patient_actions"][0]["task"] == "Do X"


def test_sanitize_reasoner_output_drops_action_null_task():
    out = {"hypotheses": [], "patient_actions": [{"task": None, "why": "Y", "risk": "low"}]}
    result = _sanitize_reasoner_output(out)
    assert len(result["patient_actions"]) == 0


def test_sanitize_reasoner_output_filters_next_tests():
    out = {
        "hypotheses": [{
            "id": "H1", "name": "A", "confidence": 0.8,
            "next_tests": [None, "", "TSAT", {"test_id": "t_ferritin", "label": "Ferritin"}]
        }],
        "patient_actions": []
    }
    result = _sanitize_reasoner_output(out)
    tests = result["hypotheses"][0]["next_tests"]
    assert len(tests) == 2
    labels = [t.get("label") for t in tests if isinstance(t, dict)]
    assert "Ferritin" in labels
    assert "TSAT" in labels


def test_sanitize_reasoner_output_empty_returns_empty():
    result = _sanitize_reasoner_output(None)
    assert result == {}
    result = _sanitize_reasoner_output({})
    assert result == {}
