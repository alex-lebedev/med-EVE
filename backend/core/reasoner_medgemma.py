from .model_manager import model_manager

PATTERN_TO_CONDITION = {
    "p_iron_def": "Iron deficiency anemia",
    "p_inflam_iron_seq": "Anemia of inflammation",
    "p_hypothyroid": "Hypothyroidism"
}

def reason(case_card, evidence_bundle):
    if model_manager.lite_mode:
        # Use candidate_scores to pick top hypothesis
        scores = evidence_bundle.get('candidate_scores', {})
        if not scores:
            return {
                "hypotheses": [],
                "patient_actions": [],
                "red_flags": []
            }

        top_pattern = max(scores, key=scores.get)
        confidence = scores[top_pattern]
        condition = PATTERN_TO_CONDITION.get(top_pattern, "Unknown condition")

        # Build evidence from top_discriminators
        evidence = []
        for item in evidence_bundle.get('top_discriminators', []):
            if item['pattern_id'] == top_pattern:
                evidence.append({
                    "marker": item['marker'],
                    "status": item['marker_status'],
                    "edge_id": item['edge_id']
                })

        counter_evidence = []
        for item in evidence_bundle.get('contradictions', []):
            if item['pattern_id'] == top_pattern:
                counter_evidence.append({
                    "marker": item['marker'],
                    "status": item['marker_status'],
                    "edge_id": item['edge_id']
                })

        next_tests = []
        if top_pattern == "p_inflam_iron_seq":
            next_tests = [{"test_id": "t_stfr", "label": "Soluble transferrin receptor (sTfR)"}]

        what_would_change_mind = ["If ferritin decreases over time", "If CRP normalizes"]

        hypothesis = {
            "id": "H1",
            "name": f"{condition} (possible)",
            "confidence": confidence,
            "evidence": evidence,
            "counter_evidence": counter_evidence,
            "next_tests": next_tests,
            "what_would_change_my_mind": what_would_change_mind
        }

        patient_actions = []
        if top_pattern == "p_inflam_iron_seq":
            patient_actions = [{
                "bucket": "tests",
                "task": "Ask clinician about sTfR or repeat iron studies",
                "why": "Differentiate mixed picture",
                "risk": "low"
            }]

        red_flags = []

        return {
            "hypotheses": [hypothesis],
            "patient_actions": patient_actions,
            "red_flags": red_flags
        }
    else:
        # Use actual model
        return {"error": "Model not loaded"}