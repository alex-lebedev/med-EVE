"""Tests for model_manager._extract_json_from_text: markdown-wrapped JSON, trailing junk, raw JSON."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.model_manager import model_manager


def test_extract_markdown_wrapped_json():
    s = '```json\n{"hypotheses": [{"id": "H1", "name": "Anemia (likely)", "confidence": 0.8}], "patient_actions": [], "red_flags": []}\n```0\n0\n0\n'
    result = model_manager._extract_json_from_text(s)
    assert result is not None
    assert isinstance(result, dict)
    assert "hypotheses" in result
    assert isinstance(result["hypotheses"], list)
    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["name"] == "Anemia (likely)"
    assert result["patient_actions"] == []
    assert result["red_flags"] == []


def test_extract_trailing_junk_after_closing_fence():
    s = '```json\n{"hypotheses": [{"id": "H1", "name": "Anemia (likely)", "confidence": 0.8}], "patient_actions": [], "red_flags": []}\n```0\n0\n0\n0\n0\n0\n'
    result = model_manager._extract_json_from_text(s)
    assert result is not None
    assert isinstance(result["hypotheses"], list)
    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["name"] == "Anemia (likely)"


def test_extract_raw_json_without_fences():
    s = '{"hypotheses": [], "patient_actions": [], "red_flags": []}'
    result = model_manager._extract_json_from_text(s)
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("hypotheses") == []
    assert result.get("patient_actions") == []
    assert result.get("red_flags") == []


def test_extract_golden_raw_file_if_present():
    """If backend/tests/fixtures/hypothesis_raw_golden.txt exists, assert extraction returns hypotheses list."""
    fixture_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures", "hypothesis_raw_golden.txt"
    )
    if not os.path.isfile(fixture_path):
        import pytest
        pytest.skip("Golden fixture not present: %s" % fixture_path)
    with open(fixture_path, "r", encoding="utf-8") as f:
        contents = f.read()
    result = model_manager._extract_json_from_text(contents)
    assert result is not None
    assert isinstance(result.get("hypotheses"), list)
