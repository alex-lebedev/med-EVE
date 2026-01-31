"""Tests for lab_normalizer: REFERENCE_UNKNOWN for fallback/unknown labs, HIGH/LOW/NORMAL for known."""
from core import lab_normalizer


def test_fallback_lab_gets_reference_unknown():
    """Lab with from_fallback=True normalizes to status REFERENCE_UNKNOWN."""
    raw = [
        {"marker": "DDI", "value": 80, "unit": "", "ref_low": 0, "ref_high": 0, "timestamp": "2026-01-30", "from_fallback": True},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "REFERENCE_UNKNOWN"
    assert normalized[0]["from_fallback"] is True
    assert normalized[0]["marker"] == "DDI"
    assert normalized[0]["value"] == 80


def test_ref_zero_zero_gets_reference_unknown():
    """Lab with ref_low=0, ref_high=0 (no from_fallback) gets REFERENCE_UNKNOWN."""
    raw = [
        {"marker": "UnknownLab", "value": 50, "unit": "", "ref_low": 0, "ref_high": 0, "timestamp": "2026-01-30"},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "REFERENCE_UNKNOWN"
    assert normalized[0].get("from_fallback") is False


def test_known_lab_high():
    """Known marker with value above ref_high gets HIGH."""
    raw = [
        {"marker": "Ferritin", "value": 220, "unit": "ng/mL", "ref_low": 15, "ref_high": 150, "timestamp": "2026-01-10"},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "HIGH"
    assert normalized[0]["from_fallback"] is False


def test_known_lab_low():
    """Known marker with value below ref_low gets LOW."""
    raw = [
        {"marker": "Iron", "value": 35, "unit": "µg/dL", "ref_low": 50, "ref_high": 170, "timestamp": "2026-01-10"},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "LOW"


def test_known_lab_normal():
    """Known marker with value in range gets NORMAL."""
    raw = [
        {"marker": "Ferritin", "value": 80, "unit": "ng/mL", "ref_low": 15, "ref_high": 150, "timestamp": "2026-01-10"},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "NORMAL"


def test_anc_high_with_ref_range():
    """ANC 9000 with ref 1.5-8 gets HIGH and keeps ref in output."""
    raw = [
        {"marker": "ANC", "value": 9000, "unit": "K/µL", "ref_low": 1.5, "ref_high": 8, "timestamp": "2026-01-30"},
    ]
    normalized = lab_normalizer.normalize_labs(raw)
    assert len(normalized) == 1
    assert normalized[0]["status"] == "HIGH"
    assert normalized[0]["ref_low"] == 1.5
    assert normalized[0]["ref_high"] == 8
