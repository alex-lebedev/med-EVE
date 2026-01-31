"""Tests for context_selector: anchor-based subgraph, signals derived from subgraph with rule fallback."""
from core import lab_normalizer, context_selector


def test_signals_derived_from_subgraph_iron_case():
    """With iron-deficiency markers, subgraph contains p_iron_def; signals should include it (or fallback)."""
    case = {
        "labs": [
            {"marker": "Ferritin", "value": 12, "unit": "ng/mL", "ref_low": 15, "ref_high": 150, "timestamp": "2026-01-10"},
            {"marker": "Iron", "value": 30, "unit": "µg/dL", "ref_low": 50, "ref_high": 170, "timestamp": "2026-01-10"},
        ],
        "patient": {"context": {}},
    }
    normalized = lab_normalizer.normalize_labs(case["labs"])
    case_card, subgraph = context_selector.select_context(normalized, case["patient"]["context"])
    assert case_card["signals"]
    # Subgraph-derived or rule fallback: iron markers should yield p_iron_def
    assert "p_iron_def" in case_card["signals"]
    subgraph_node_ids = {n["id"] for n in subgraph["nodes"]}
    for sid in case_card["signals"]:
        assert sid in subgraph_node_ids, f"signal {sid} should be in subgraph"


def test_signals_derived_from_subgraph_thyroid_case():
    """With thyroid markers, subgraph contains p_hypothyroid; signals should include it."""
    case = {
        "labs": [
            {"marker": "TSH", "value": 8, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.0, "timestamp": "2026-01-10"},
            {"marker": "FT4", "value": 0.8, "unit": "ng/dL", "ref_low": 0.8, "ref_high": 1.8, "timestamp": "2026-01-10"},
        ],
        "patient": {"context": {}},
    }
    normalized = lab_normalizer.normalize_labs(case["labs"])
    case_card, subgraph = context_selector.select_context(normalized, case["patient"]["context"])
    assert case_card["signals"]
    assert "p_hypothyroid" in case_card["signals"]
