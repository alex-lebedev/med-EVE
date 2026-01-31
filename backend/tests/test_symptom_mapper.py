"""Tests for symptom_mapper: rule suggestion, lite vs model mode, unmappable list."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from core.symptom_mapper import (
    map_symptoms_to_graph,
    _symptom_to_node_id,
    _get_rule_suggestion,
)


def test_symptom_to_node_id():
    assert _symptom_to_node_id("fatigue") == "s_fatigue"
    assert _symptom_to_node_id("Shortness of breath") == "s_shortness_of_breath"
    assert _symptom_to_node_id("  ") == "s_unknown"


def test_get_rule_suggestion():
    s = _get_rule_suggestion("fatigue")
    assert s.get("pattern_id") == "p_inflam_iron_seq"
    assert s.get("relation") == "SUPPORTS"
    assert "rationale" in s
    assert _get_rule_suggestion("nonexistent_token_xyz") == {}


def test_map_symptoms_lite_mode_keep():
    """Lite mode: token with rule suggestion and pattern in signals -> keep, add node/edge."""
    case_card = {
        "abnormal_markers": ["Ferritin"],
        "signals": ["p_inflam_iron_seq", "p_iron_def"],
    }
    subgraph = {
        "nodes": [
            {"id": "m_ferritin", "type": "Marker", "label": "Ferritin"},
            {"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"},
        ],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = True
    model.model_loaded = False

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["fatigue"], case_card, subgraph, model, reasoner_output={}
    )
    assert len(nodes) == 1
    assert nodes[0]["id"] == "s_fatigue"
    assert nodes[0]["type"] == "Symptom"
    assert nodes[0]["label"] == "fatigue"
    assert nodes[0].get("dynamic") is True
    assert len(edges) == 1
    assert edges[0]["from"] == "s_fatigue"
    assert edges[0]["to"] == "p_inflam_iron_seq"
    assert edges[0]["relation"] == "SUPPORTS"
    assert unmappable == []


def test_map_symptoms_lite_mode_do_not_map():
    """Lite mode: token with no rule or pattern not in signals -> do_not_map, unmappable."""
    case_card = {"abnormal_markers": [], "signals": ["p_iron_def"]}
    subgraph = {
        "nodes": [{"id": "p_iron_def", "type": "Pattern", "label": "Iron def"}],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = True
    model.model_loaded = False

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["gibberish_xyz"], case_card, subgraph, model, reasoner_output={}
    )
    assert nodes == []
    assert edges == []
    assert "gibberish_xyz" in unmappable


def test_map_symptoms_lite_mode_fatigue_not_in_signals():
    """Lite mode: fatigue suggested p_inflam_iron_seq but signals only have p_iron_def -> do_not_map."""
    case_card = {"abnormal_markers": [], "signals": ["p_iron_def"]}
    subgraph = {
        "nodes": [
            {"id": "p_iron_def", "type": "Pattern", "label": "Iron def"},
            {"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"},
        ],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = True
    model.model_loaded = False

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["fatigue"], case_card, subgraph, model, reasoner_output={}
    )
    assert nodes == []
    assert edges == []
    assert unmappable == ["fatigue"]


@patch.dict(os.environ, {"USE_SYMPTOM_MAPPER_MODEL": "1"}, clear=False)
def test_map_symptoms_model_mode_mock_keep():
    """Model mode (mocked): MedGemma returns keep -> add node/edge."""
    case_card = {"abnormal_markers": ["Ferritin"], "signals": ["p_inflam_iron_seq"]}
    subgraph = {
        "nodes": [
            {"id": "m_ferritin", "type": "Marker", "label": "Ferritin"},
            {"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"},
        ],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = False
    model.model_loaded = True
    model.generate = MagicMock(
        return_value={
            "json": {
                "action": "keep",
                "pattern_id": "p_inflam_iron_seq",
                "relation": "SUPPORTS",
                "rationale": "Fatigue fits anemia of inflammation.",
            }
        }
    )

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["fatigue"], case_card, subgraph, model, reasoner_output={"hypotheses": []}
    )
    assert len(nodes) == 1
    assert nodes[0]["id"] == "s_fatigue"
    assert len(edges) == 1
    assert edges[0]["to"] == "p_inflam_iron_seq"
    assert unmappable == []
    model.generate.assert_called_once()


@patch.dict(os.environ, {"USE_SYMPTOM_MAPPER_MODEL": "1"}, clear=False)
def test_map_symptoms_model_mode_mock_do_not_map():
    """Model mode (mocked): MedGemma returns do_not_map -> unmappable."""
    case_card = {"abnormal_markers": [], "signals": ["p_inflam_iron_seq"]}
    subgraph = {
        "nodes": [{"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"}],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = False
    model.model_loaded = True
    model.generate = MagicMock(return_value={"json": {"action": "do_not_map"}})

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["fatigue"], case_card, subgraph, model, reasoner_output={}
    )
    assert nodes == []
    assert edges == []
    assert unmappable == ["fatigue"]


def test_map_symptoms_empty_tokens():
    case_card = {"signals": []}
    subgraph = {"nodes": [], "edges": []}
    model = MagicMock()
    nodes, edges, unmappable = map_symptoms_to_graph(
        [], case_card, subgraph, model, reasoner_output={}
    )
    assert nodes == [] and edges == [] and unmappable == []


def test_map_symptoms_skip_already_in_subgraph():
    """Token that already has a symptom node in subgraph is skipped (no duplicate)."""
    case_card = {"signals": ["p_inflam_iron_seq"]}
    subgraph = {
        "nodes": [
            {"id": "s_fatigue", "type": "Symptom", "label": "Fatigue"},
            {"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"},
        ],
        "edges": [],
    }
    model = MagicMock()
    model.lite_mode = True
    model.model_loaded = False

    nodes, edges, unmappable = map_symptoms_to_graph(
        ["fatigue"], case_card, subgraph, model, reasoner_output={}
    )
    assert nodes == []
    assert edges == []
    assert unmappable == []
