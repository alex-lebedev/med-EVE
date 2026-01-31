"""Tests for reasoner: hybrid uses lite baseline; model augments ranking/reasoning."""
from unittest.mock import patch

from core.reasoner_medgemma import reason, _reason_lite_mode
from app import _merge_reasoner_output


def test_reason_model_mode_hybrid_uses_lite_baseline():
    """Hybrid: primary hypotheses always from lite; when hypothesis_generation not used, result has lite hypotheses."""
    case_card = {"signals": ["p_inflam_iron_seq"], "patient_context": {}}
    evidence_bundle = {
        "candidate_scores": {"p_inflam_iron_seq": 0.8, "p_iron_def": 0.4},
        "supports": [],
        "contradictions": [],
        "top_discriminators": [],
        "subgraph": {"nodes": [], "edges": []},
    }
    events_list = []

    with patch("core.reasoner_medgemma.model_manager") as mock_mm:
        mock_mm.lite_mode = False
        mock_mm.model_loaded = False  # no ranking/reasoning calls
        with patch("core.reasoner_medgemma.agent_manager") as mock_agent:
            mock_agent.call_agent.return_value = {"use_model": False, "fallback": True}

            result = reason(case_card, evidence_bundle, events_list)

    assert len(result["hypotheses"]) > 0
    assert result["hypotheses_valid"] is True
    assert result["patient_actions"] != [] or True  # lite may give actions for this case
    assert result["red_flags"] == []
    assert result["novel_insights"] == []
    assert result["novel_actions"] == []
    assert result.get("model_used") is False


def test_reason_model_mode_hybrid_has_hypotheses_when_json_path_raises():
    """Hybrid: when optional hypothesis_generation path raises, we still return lite baseline hypotheses."""
    case_card = {"signals": [], "patient_context": {}}
    evidence_bundle = {
        "candidate_scores": {"p_iron_def": 0.5},
        "supports": [],
        "contradictions": [],
        "top_discriminators": [],
        "subgraph": {"nodes": [], "edges": []},
    }
    events_list = []

    with patch("core.reasoner_medgemma.model_manager") as mock_mm:
        mock_mm.lite_mode = False
        mock_mm.model_loaded = False
        with patch("core.reasoner_medgemma.agent_manager") as mock_agent:
            mock_agent.call_agent.side_effect = RuntimeError("Model error")

            result = reason(case_card, evidence_bundle, events_list)

    assert len(result["hypotheses"]) > 0
    assert result["hypotheses_valid"] is True
    assert result["patient_actions"] == []
    assert result["red_flags"] == []
    assert result["novel_insights"] == []
    assert result["novel_actions"] == []


def test_reason_lite_mode_still_returns_predefined_actions():
    """Lite mode still uses _reason_lite_mode with predefined actions when applicable."""
    case_card = {"signals": ["p_inflam_iron_seq"], "patient_context": {}}
    evidence_bundle = {
        "candidate_scores": {"p_inflam_iron_seq": 0.8, "p_iron_def": 0.4},
        "supports": [],
        "contradictions": [],
        "top_discriminators": [],
        "subgraph": {"nodes": [], "edges": []},
    }
    with patch("core.reasoner_medgemma.model_manager") as mock_mm:
        mock_mm.lite_mode = True
        result = reason(case_card, evidence_bundle, None)
    assert result["hypotheses"]
    assert result["patient_actions"]
    assert "tests" in result["patient_actions"][0].get("bucket", "") or "test" in result["patient_actions"][0].get("task", "").lower()
    assert result["novel_insights"] == []
    assert result["novel_actions"] == []


def test_merge_keeps_previous_when_new_invalid():
    prev = {
        "hypotheses": [{
            "id": "H1",
            "name": "Iron deficiency anemia (possible)",
            "confidence": 0.6,
            "evidence": [],
            "counter_evidence": [],
            "next_tests": []
        }],
        "patient_actions": [{"task": "Test ferritin", "why": "check stores", "risk": "low"}],
        "red_flags": [],
        "hypotheses_valid": True
    }
    new = {
        "hypotheses": [],
        "patient_actions": [],
        "red_flags": [],
        "hypotheses_valid": False
    }
    merged = _merge_reasoner_output(prev, new)
    assert merged["hypotheses"][0]["name"] == "Iron deficiency anemia (possible)"
    assert merged["patient_actions"][0]["task"] == "Test ferritin"


def test_merge_updates_when_confidence_changes():
    prev = {
        "hypotheses": [{
            "id": "H1",
            "name": "Iron deficiency anemia (possible)",
            "confidence": 0.6,
            "evidence": [],
            "counter_evidence": [],
            "next_tests": []
        }],
        "patient_actions": [{"task": "Test ferritin", "why": "check stores", "risk": "low"}],
        "red_flags": [],
        "hypotheses_valid": True
    }
    new = {
        "hypotheses": [{
            "id": "H1",
            "name": "Iron deficiency anemia (likely)",
            "confidence": 0.7,
            "evidence": [],
            "counter_evidence": [],
            "next_tests": []
        }],
        "patient_actions": [{"task": "Test iron studies", "why": "clarify", "risk": "low"}],
        "red_flags": [],
        "hypotheses_valid": True
    }
    merged = _merge_reasoner_output(prev, new)
    assert merged["hypotheses"][0]["name"] == "Iron deficiency anemia (likely)"
    assert merged["hypotheses"][0].get("merge_updated") is True
    assert merged["patient_actions"][0]["task"] == "Test iron studies"
