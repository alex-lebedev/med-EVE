from .model_manager import model_manager
from .agent_manager import agent_manager
from .events import Step
import json

PATTERN_TO_CONDITION = {
    "p_iron_def": "Iron deficiency anemia",
    "p_inflam_iron_seq": "Anemia of inflammation",
    "p_hypothyroid": "Hypothyroidism"
}

def _has_ambiguity(hypotheses):
    """Check if hypotheses have ambiguity (top 2 within threshold)"""
    if len(hypotheses) < 2:
        return False
    sorted_hypo = sorted(hypotheses, key=lambda h: h.get('confidence', 0), reverse=True)
    if len(sorted_hypo) < 2:
        return False
    diff = sorted_hypo[0].get('confidence', 0) - sorted_hypo[1].get('confidence', 0)
    return diff < 0.15

def reason(case_card, evidence_bundle, events_list=None):
    if model_manager.lite_mode:
        # Generate multiple hypotheses for differential diagnosis
        scores = evidence_bundle.get('candidate_scores', {})
        if not scores:
            return {
                "hypotheses": [],
                "patient_actions": [],
                "red_flags": []
            }

        # Sort patterns by confidence (descending)
        sorted_patterns = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Generate hypothesis for each candidate pattern (filter low confidence ones)
        MIN_CONFIDENCE_THRESHOLD = 0.1  # Only show hypotheses with at least 10% confidence
        hypotheses = []
        
        for idx, (pattern_id, confidence) in enumerate(sorted_patterns):
            if confidence < MIN_CONFIDENCE_THRESHOLD:
                continue
                
            condition = PATTERN_TO_CONDITION.get(pattern_id, "Unknown condition")
            
            # Build evidence for this pattern
            evidence = []
            for item in evidence_bundle.get('top_discriminators', []):
                if item['pattern_id'] == pattern_id:
                    evidence.append({
                        "marker": item['marker'],
                        "status": item['marker_status'],
                        "edge_id": item['edge_id']
                    })

            counter_evidence = []
            for item in evidence_bundle.get('contradictions', []):
                if item['pattern_id'] == pattern_id:
                    counter_evidence.append({
                        "marker": item['marker'],
                        "status": item['marker_status'],
                        "edge_id": item['edge_id']
                    })

            # Determine next tests based on pattern
            next_tests = []
            if pattern_id == "p_inflam_iron_seq":
                next_tests = [{"test_id": "t_stfr", "label": "Soluble transferrin receptor (sTfR)"}]
            elif pattern_id == "p_iron_def":
                # If iron deficiency is a possibility, recommend iron studies
                next_tests = [{"test_id": "t_ferritin", "label": "Ferritin measurement"}]
            elif pattern_id == "p_hypothyroid":
                # If hypothyroidism is a possibility, recommend TPO antibodies
                next_tests = [{"test_id": "t_tpo_ab", "label": "Thyroid peroxidase antibodies"}]

            # Generate "what would change my mind" based on pattern
            what_would_change_mind = []
            if pattern_id == "p_inflam_iron_seq":
                what_would_change_mind = ["If ferritin decreases over time", "If CRP normalizes", "If sTfR is elevated (suggests true iron deficiency)"]
            elif pattern_id == "p_iron_def":
                what_would_change_mind = ["If ferritin increases with iron supplementation", "If MCV normalizes", "If inflammation markers appear"]
            elif pattern_id == "p_hypothyroid":
                what_would_change_mind = ["If TSH normalizes", "If thyroid antibodies are negative", "If symptoms resolve with treatment"]

            # Determine hypothesis name based on confidence
            if confidence >= 0.7:
                qualifier = "likely"
            elif confidence >= 0.4:
                qualifier = "possible"
            else:
                qualifier = "unlikely but considered"

            hypothesis = {
                "id": f"H{idx + 1}",
                "name": f"{condition} ({qualifier})",
                "confidence": confidence,
                "evidence": evidence,
                "counter_evidence": counter_evidence,
                "next_tests": next_tests,
                "what_would_change_my_mind": what_would_change_mind
            }
            
            hypotheses.append(hypothesis)

        # Generate patient actions based on top hypothesis
        patient_actions = []
        if sorted_patterns and sorted_patterns[0][0] == "p_inflam_iron_seq":
            # Check if there's ambiguity between inflammation and iron deficiency
            iron_patterns = ["p_inflam_iron_seq", "p_iron_def"]
            iron_scores = {p: scores.get(p, 0) for p in iron_patterns if p in scores}
            
            # If both have significant scores, there's ambiguity
            if len(iron_scores) == 2 and min(iron_scores.values()) > 0.3:
                patient_actions = [{
                    "bucket": "tests",
                    "task": "Consider sTfR test to differentiate between inflammation and iron deficiency",
                    "why": "Both patterns are possible - sTfR helps distinguish",
                    "risk": "low"
                }]
            else:
                patient_actions = [{
                    "bucket": "tests",
                    "task": "Ask clinician about sTfR or repeat iron studies",
                    "why": "Differentiate mixed picture",
                    "risk": "low"
                }]

        red_flags = []

        return {
            "hypotheses": hypotheses,
            "patient_actions": patient_actions,
            "red_flags": red_flags
        }
    else:
        # Use Hypothesis Generation Agent (always uses model)
        try:
            # Prepare data for agent
            candidate_patterns = []
            for pattern_id, score in evidence_bundle.get('candidate_scores', {}).items():
                candidate_patterns.append({
                    "pattern_id": pattern_id,
                    "confidence": score,
                    "condition": PATTERN_TO_CONDITION.get(pattern_id, "Unknown condition")
                })
            
            # Format evidence bundle for prompt
            evidence_data = {
                "candidate_patterns_json": json.dumps(candidate_patterns, indent=2),
                "evidence_bundle_json": json.dumps({
                    "supports": evidence_bundle.get('supports', []),
                    "contradictions": evidence_bundle.get('contradictions', []),
                    "top_discriminators": evidence_bundle.get('top_discriminators', []),
                    "candidate_scores": evidence_bundle.get('candidate_scores', {})
                }, indent=2),
                "patient_context_json": json.dumps(case_card.get('patient_context', {}), indent=2),
                "subgraph_json": json.dumps(evidence_bundle.get('subgraph', {}), indent=2)
            }
            
            context = {
                'case_card': case_card,
                'evidence_bundle': evidence_bundle
            }
            
            # Call agent
            agent_response = agent_manager.call_agent(
                'hypothesis_generation',
                context,
                evidence_data,
                events_list=events_list,
                step=Step.REASON
            )
            
            if agent_response.get('use_model') and agent_response.get('result'):
                # Parse and validate model output
                model_output = agent_response['result']
                
                # Validate and convert to expected format
                hypotheses_raw = model_output.get('hypotheses', [])
                patient_actions_raw = model_output.get('patient_actions', [])
                red_flags = model_output.get('red_flags', [])
                
                # Ensure all hypotheses have required fields
                validated_hypotheses = []
                for hypo in hypotheses_raw:
                    validated_hypo = {
                        "id": hypo.get('id', 'H1'),
                        "name": hypo.get('name', 'Unknown condition'),
                        "confidence": float(hypo.get('confidence', 0.5)),
                        "evidence": hypo.get('evidence', []),
                        "counter_evidence": hypo.get('counter_evidence', []),
                        "next_tests": hypo.get('next_tests', []),
                        "what_would_change_my_mind": hypo.get('what_would_change_my_mind', [])
                    }
                    validated_hypotheses.append(validated_hypo)
                
                # If actions not provided or empty, call action generation agent
                if (not patient_actions_raw or len(patient_actions_raw) == 0) and not model_manager.lite_mode:
                    try:
                        action_agent_data = {
                            "hypotheses_json": json.dumps(validated_hypotheses, indent=2),
                            "evidence_bundle_json": json.dumps({
                                "supports": evidence_bundle.get('supports', []),
                                "contradictions": evidence_bundle.get('contradictions', [])
                            }, indent=2),
                            "patient_context_json": json.dumps(case_card.get('patient_context', {}), indent=2)
                        }
                        
                        action_agent_response = agent_manager.call_agent(
                            'action_generation',
                            {'hypotheses': validated_hypotheses, 'case_card': case_card},
                            action_agent_data,
                            events_list=events_list,
                            step=Step.REASON
                        )
                        
                        if action_agent_response.get('use_model') and action_agent_response.get('result'):
                            patient_actions_raw = action_agent_response['result'].get('patient_actions', [])
                    except Exception as e:
                        # Continue without actions if agent fails
                        pass
                
                patient_actions = patient_actions_raw
                
                # Check for ambiguity and call test recommendation agent if needed
                has_amb = _has_ambiguity(validated_hypotheses)
                no_tests = not any(h.get('next_tests') for h in validated_hypotheses)
                
                if (has_amb or no_tests) and not model_manager.lite_mode:
                    try:
                        # Get available tests from knowledge graph
                        from .kg_store import kg_store
                        available_tests = [
                            {"test_id": node['id'], "label": node['label']}
                            for node in evidence_bundle.get('subgraph', {}).get('nodes', [])
                            if node.get('type') == 'Test'
                        ]
                        
                        # Call test recommendation agent
                        test_agent_data = {
                            "hypotheses_json": json.dumps(validated_hypotheses, indent=2),
                            "already_performed_tests_json": json.dumps([], indent=2),  # TODO: track performed tests
                            "available_tests_json": json.dumps(available_tests, indent=2),
                            "patient_context_json": json.dumps(case_card.get('patient_context', {}), indent=2)
                        }
                        
                        test_agent_response = agent_manager.call_agent(
                            'test_recommendation',
                            {'hypotheses': validated_hypotheses},
                            test_agent_data,
                            events_list=events_list,
                            step=Step.REASON
                        )
                        
                        if test_agent_response.get('use_model') and test_agent_response.get('result'):
                            recommended_tests = test_agent_response['result'].get('recommended_tests', [])
                            # Merge with hypothesis tests, prioritizing model recommendations
                            for hypo in validated_hypotheses:
                                if not hypo.get('next_tests') or len(hypo['next_tests']) == 0:
                                    # Add high-priority tests from model
                                    high_priority = [t for t in recommended_tests if t.get('priority') == 'high']
                                    if high_priority:
                                        hypo['next_tests'] = high_priority[:2]  # Top 2 high priority
                    except Exception as e:
                        # Continue without test recommendations if agent fails
                        pass
                
                return {
                    "hypotheses": validated_hypotheses,
                    "patient_actions": patient_actions,
                    "red_flags": red_flags,
                    "model_used": True,
                    "raw_model_output": agent_response.get('raw_output')
                }
            else:
                # Fallback to lite mode if model call failed
                if events_list:
                    from .events import emit_event, EventType
                    emit_event(events_list, Step.REASON, EventType.MODEL_CALLED, {
                        'agent_type': 'hypothesis_generation',
                        'prompt_type': 'hypothesis_generation',
                        'status': 'fallback',
                        'error': agent_response.get('error', 'Model call failed'),
                        'response_time_ms': 0
                    })
                # Recursively call lite mode
                model_manager.lite_mode = True
                return reason(case_card, evidence_bundle, events_list)
        
        except Exception as e:
            # Fallback to lite mode on error
            if events_list:
                from .events import emit_event, EventType
                emit_event(events_list, Step.REASON, EventType.MODEL_CALLED, {
                    'agent_type': 'hypothesis_generation',
                    'prompt_type': 'hypothesis_generation',
                    'status': 'error',
                    'error': str(e),
                    'response_time_ms': 0
                })
            model_manager.lite_mode = True
            return reason(case_card, evidence_bundle, events_list)