from app import _run_pipeline, load_cases

def test_no_invention():
    cases = load_cases()
    case_id = "case_02_anemia_of_inflammation_gotcha"
    case = cases[case_id]
    result = _run_pipeline(case, [])
    all_markers = [lab['marker'] for lab in result['normalized_labs']]
    for hypo in result['reasoner_output']['hypotheses']:
        for ev in hypo['evidence']:
            assert ev['marker'] in all_markers, f"Marker {ev['marker']} not in input"
    assert "case_impression" in result
    assert isinstance(result["case_impression"], str)
    assert len(result["case_impression"]) > 0
    assert "suggested_kg_additions" in result
    assert "nodes" in result["suggested_kg_additions"] and "edges" in result["suggested_kg_additions"]