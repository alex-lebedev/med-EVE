"""Tests for unlinked_markers: unknown marker gets dynamic node and appears in unlinked_markers when no edge config."""
from app import _run_pipeline
from core.text_to_case import text_to_case


def test_unknown_marker_gets_dynamic_node_and_unlinked():
    """Case with only unknown marker (FooBar) yields dynamic node and unlinked_markers."""
    case = text_to_case("FooBar 1.0")
    events_list = []
    result = _run_pipeline(case, events_list)
    assert "unlinked_markers" in result
    assert "FooBar" in result["unlinked_markers"]
    subgraph = result["evidence_bundle"]["subgraph"]
    node_ids = [n["id"] for n in subgraph["nodes"]]
    assert "m_foobar" in node_ids
    foobar_node = next(n for n in subgraph["nodes"] if n["id"] == "m_foobar")
    assert foobar_node.get("dynamic") is True
