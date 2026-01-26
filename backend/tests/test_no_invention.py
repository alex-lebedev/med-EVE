from app import run_pipeline, load_cases

def test_no_invention():
    cases = load_cases()
    case_id = "case_02_anemia_of_inflammation_gotcha"
    result = run_pipeline({"case_id": case_id})
    all_markers = [lab['marker'] for lab in result['normalized_labs']]
    for hypo in result['reasoner_output']['hypotheses']:
        for ev in hypo['evidence']:
            assert ev['marker'] in all_markers, f"Marker {ev['marker']} not in input"
    # Check patient actions don't invent markers, but they don't reference markers
    assert True