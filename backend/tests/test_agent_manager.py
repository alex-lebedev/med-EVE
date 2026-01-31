"""Tests for agent_manager: prompt build with overlapping context and data (no duplicate keyword)."""
from unittest.mock import patch

from core.agent_manager import AgentManager
from core.model_manager import model_manager


def test_build_prompt_evidence_weighting_overlapping_keys():
    """Context and data both have marker/status; format should succeed with merged kwargs."""
    agent = AgentManager()
    context = {
        "marker": "Ferritin",
        "status": "HIGH",
        "evidence_bundle": {},
    }
    data = {
        "marker": "Ferritin",
        "status": "HIGH",
        "relation": "SUPPORTS",
        "pattern_id": "p_inflam_iron_seq",
        "context_markers": "Ferritin, hsCRP",
        "patient_context_json": "{}",
    }
    system_prompt, user_prompt = agent._build_prompt("evidence_weighting", context, data)
    assert "Ferritin" in user_prompt
    assert "HIGH" in user_prompt
    assert "SUPPORTS" in user_prompt
    assert "p_inflam_iron_seq" in user_prompt
    assert "evidence_weighting" in system_prompt or "evidence" in system_prompt.lower()


def test_build_prompt_missing_key_falls_back_to_json():
    """Template placeholder not in format_kwargs -> KeyError -> fallback to JSON."""
    agent = AgentManager()
    context = {}
    data = {"marker": "Hb", "status": "LOW"}
    # evidence_weighting template also needs relation, pattern_id, context_markers, patient_context_json
    # So we might get KeyError; fallback should produce JSON with marker/status
    system_prompt, user_prompt = agent._build_prompt("evidence_weighting", context, data)
    assert "marker" in user_prompt or "Hb" in user_prompt
    assert "LOW" in user_prompt or "status" in user_prompt


def test_should_use_agent_context_selection_respects_env_0():
    """When USE_CONTEXT_SELECTION_MODEL=0, context_selection should not use model."""
    agent = AgentManager()
    context = {"abnormal_markers": ["Ferritin", "hsCRP", "TSH"], "patient_context": {}}
    with patch.dict("os.environ", {"USE_CONTEXT_SELECTION_MODEL": "0"}, clear=False):
        with patch.object(model_manager, "lite_mode", False):
            with patch.object(model_manager, "model_loaded", True):
                use = agent.should_use_agent("context_selection", context)
    assert use is False


def test_should_use_agent_action_generation_respects_env_0():
    """When USE_ACTION_GENERATION_MODEL=0, action_generation should not use model."""
    agent = AgentManager()
    context = {"hypotheses": [], "case_card": {}}
    with patch.dict("os.environ", {"USE_ACTION_GENERATION_MODEL": "0"}, clear=False):
        with patch.object(model_manager, "lite_mode", False):
            with patch.object(model_manager, "model_loaded", True):
                use = agent.should_use_agent("action_generation", context)
    assert use is False
