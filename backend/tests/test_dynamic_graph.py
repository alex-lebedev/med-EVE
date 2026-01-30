"""Tests for dynamic_graph.extend_subgraph (inject dynamic nodes/edges, idempotence)."""
from core.dynamic_graph import extend_subgraph


def test_extend_subgraph_adds_node_and_edge_for_anc():
    case_card = {
        "abnormal_markers": ["ANC", "hsCRP"],
        "abnormal_marker_node_ids": ["m_anc", "m_hscrp"],
        "signals": ["p_inflam_iron_seq"],
    }
    subgraph = {
        "nodes": [{"id": "m_hscrp", "type": "Marker", "label": "hsCRP"}, {"id": "p_inflam_iron_seq", "type": "Pattern", "label": "Inflammation"}],
        "edges": [{"id": "e_001", "from": "m_hscrp", "to": "p_inflam_iron_seq", "relation": "SUPPORTS"}],
    }
    out = extend_subgraph(case_card, subgraph)
    node_ids = [n["id"] for n in out["nodes"]]
    assert "m_anc" in node_ids
    anc_node = next(n for n in out["nodes"] if n["id"] == "m_anc")
    assert anc_node.get("dynamic") is True
    assert anc_node["type"] == "Marker"
    assert anc_node["label"] == "ANC"
    edge_from_anc = [e for e in out["edges"] if e.get("from") == "m_anc" or e.get("to") == "m_anc"]
    assert len(edge_from_anc) >= 1
    dyn_edge = next(e for e in edge_from_anc if e.get("from") == "m_anc" and e.get("to") == "p_inflam_iron_seq")
    assert dyn_edge["relation"] == "SUPPORTS"
    assert "rationale" in dyn_edge or "source_label" in dyn_edge


def test_extend_subgraph_idempotent_when_no_dynamic_markers():
    case_card = {
        "abnormal_markers": ["Ferritin"],
        "abnormal_marker_node_ids": ["m_ferritin"],
        "signals": ["p_iron_def"],
    }
    subgraph = {
        "nodes": [{"id": "m_ferritin", "type": "Marker", "label": "Ferritin"}, {"id": "p_iron_def", "type": "Pattern", "label": "Iron def"}],
        "edges": [{"id": "e_001", "from": "m_ferritin", "to": "p_iron_def", "relation": "SUPPORTS"}],
    }
    nodes_before = len(subgraph["nodes"])
    edges_before = len(subgraph["edges"])
    out = extend_subgraph(case_card, subgraph)
    assert len(out["nodes"]) == nodes_before
    assert len(out["edges"]) == edges_before
