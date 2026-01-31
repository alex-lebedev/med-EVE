from core.schemas import ReasonerOutput, CaseCard, EvidenceBundle, GuardrailReport

def test_reasoner_output_schema():
    sample = {
        "hypotheses": [{
            "name": "Anemia of inflammation",
            "confidence": 0.78,
            "evidence": [{"marker": "hsCRP", "status": "HIGH", "edge_id": "e_001"}],
            "counter_evidence": [{"marker": "MCV", "status": "NORMAL"}],
            "next_tests": ["TSAT"],
            "notes": "Do not diagnose."
        }],
        "patient_actions": [{
            "task": "Schedule TSAT test",
            "why": "Differentiate",
            "risk": "low"
        }],
        "red_flags": [],
        "novel_insights": [{
            "insight": "Consider mixed anemia etiology",
            "rationale": "Evidence suggests competing processes",
            "outside_kg": True
        }],
        "novel_actions": [{
            "task": "Discuss alternative causes with clinician",
            "why": "Outside-KG differential considerations",
            "risk": "low",
            "outside_kg": True
        }],
        "provenance": {
            "kg_grounded": False,
            "notes": "Outside-KG ideas included."
        }
    }
    output = ReasonerOutput(**sample)
    assert output.hypotheses[0].name == "Anemia of inflammation"

def test_case_card_schema():
    sample = {
        "abnormal_markers": ["Ferritin"],
        "neighbor_markers": ["Iron"],
        "signals": ["Iron deficiency"],
        "missing_key_tests": ["TSAT"],
        "patient_context": {"age": 30}
    }
    card = CaseCard(**sample)
    assert card.abnormal_markers == ["Ferritin"]

def test_evidence_bundle_schema():
    sample = {
        "subgraph": {"nodes": [], "edges": []},
        "supports": [{"claim": "Test", "markers": ["Ferritin"], "edge_ids": ["e_001"]}],
        "contradictions": [],
        "allowed_claims": ["Test claim"]
    }
    bundle = EvidenceBundle(**sample)
    assert bundle.supports[0].claim == "Test"

def test_guardrail_report_schema():
    sample = {
        "status": "PASS",
        "failed_rules": [],
        "auto_fixes": []
    }
    report = GuardrailReport(**sample)
    assert report.status == "PASS"