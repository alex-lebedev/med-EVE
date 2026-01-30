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
