"""Tests for text_to_case parser (including ANC and unknown markers)."""
from core.text_to_case import text_to_case

def test_anc_parsed_as_lab():
    text = "ANC 8000 cells/µL"
    case = text_to_case(text)
    assert case["labs"]
    labs = [l for l in case["labs"] if l["marker"] == "ANC"]
    assert len(labs) == 1
    assert labs[0]["value"] == 8000
    assert labs[0]["ref_low"] == 1.5
    assert labs[0]["ref_high"] == 8
    assert "unit" in labs[0]

def test_absolute_neutrophil_count_normalizes_to_anc():
    text = "Absolute neutrophil count 5000"
    case = text_to_case(text)
    assert case["labs"]
    labs = [l for l in case["labs"] if l["marker"] == "ANC"]
    assert len(labs) == 1
    assert labs[0]["value"] == 5000


def test_stfr_parsed_as_lab():
    """Fallback: sTfR 6.5 mg/L parses to one lab with marker sTfR, value 6.5, unit mg/L."""
    text = "sTfR 6.5 mg/L"
    case = text_to_case(text)
    assert len(case["labs"]) == 1
    lab = case["labs"][0]
    assert lab["marker"] == "sTfR"
    assert lab["value"] == 6.5
    assert lab["unit"] == "mg/L"
    assert lab.get("from_fallback") is True
    assert lab["ref_low"] == 0 and lab["ref_high"] == 0


def test_mixed_ferritin_and_stfr_yields_two_labs():
    """Known Ferritin + fallback sTfR yields two labs."""
    text = "Ferritin 12 ng/mL, sTfR 6.5 mg/L"
    case = text_to_case(text)
    assert len(case["labs"]) == 2
    markers = {l["marker"] for l in case["labs"]}
    assert "Ferritin" in markers and "sTfR" in markers


def test_unknown_only_input_no_longer_raises():
    """Unknown-only input (e.g. sTfR 6.5 mg/L) no longer raises; parses via fallback."""
    text = "sTfR 6.5 mg/L"
    case = text_to_case(text)
    assert case["labs"]
    assert case["labs"][0]["marker"] == "sTfR"
