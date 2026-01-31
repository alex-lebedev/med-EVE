from .kg_store import kg_store
from .model_manager import model_manager
from .agent_manager import agent_manager
from .events import Step
import yaml
import os
import json

# Load marker to node mapping
with open(os.path.join(os.path.dirname(__file__), 'marker_to_node.yml')) as f:
    MARKER_TO_NODE = yaml.safe_load(f)


def _pattern_label(pattern_id: str, subgraph: dict) -> str:
    """Resolve pattern label from kg_store; if missing (e.g. dynamic), from subgraph nodes."""
    if pattern_id in kg_store.nodes:
        return kg_store.nodes[pattern_id].get("label") or pattern_id
    for n in (subgraph.get("nodes") or []):
        if n.get("id") == pattern_id:
            return n.get("label") or pattern_id
    return pattern_id

# Weights for evidence (rule-based fallback)
WEIGHTS = {
    'hsCRP': {'SUPPORTS': 0.8, 'CONTRADICTS': 0.0},
    'Ferritin': {'HIGH': {'SUPPORTS': 0.7, 'CONTRADICTS': 0.6}, 'LOW': {'SUPPORTS': 0.6, 'CONTRADICTS': 0.7}},
    'Iron': {'LOW': {'SUPPORTS': 0.5, 'CONTRADICTS': 0.4}},
    'TSAT': {'LOW': {'SUPPORTS': 0.4, 'CONTRADICTS': 0.3}},
    'Hb': {'LOW': {'SUPPORTS': 0.3, 'CONTRADICTS': 0.2}},
    'RDW': {'NORMAL': {'SUPPORTS': 0.2, 'CONTRADICTS': 0.1}},
}

def _coerce_weight(value, default=0.1) -> float:
    """Ensure evidence weight is numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _infer_support_relation(relation: str, status: str) -> str:
    """Map causal relations to SUPPORTS/CONTRADICTS when direction matches lab status."""
    if status not in ("HIGH", "LOW"):
        return ""
    if relation == "INCREASES":
        return "SUPPORTS" if status == "HIGH" else "CONTRADICTS"
    if relation == "DECREASES":
        return "SUPPORTS" if status == "LOW" else "CONTRADICTS"
    return ""

def get_evidence_weight(marker, status, relation, pattern_id, case_card, evidence_bundle, events_list):
    """
    Get weight for evidence item, using model if needed
    """
    # Check if we should use model for weighting
    context = {
        'marker': marker,
        'status': status,
        'evidence_bundle': evidence_bundle
    }
    
    if agent_manager.should_use_agent('evidence_weighting', context) and not model_manager.lite_mode:
        try:
            # Prepare data for agent
            context_markers = case_card.get('abnormal_markers', [])
            agent_data = {
                "marker": marker,
                "status": status,
                "relation": relation,
                "pattern_id": pattern_id,
                "context_markers": ", ".join(context_markers),
                "patient_context_json": json.dumps(case_card.get('patient_context', {}), indent=2)
            }
            
            # Call evidence weighting agent
            agent_response = agent_manager.call_agent(
                'evidence_weighting',
                context,
                agent_data,
                events_list=events_list,
                step=Step.EVIDENCE_SCORE
            )
            
            if agent_response.get('use_model') and agent_response.get('result'):
                model_output = agent_response['result']
                weight = _coerce_weight(model_output.get('weight', 0.5), default=0.5)
                rationale = model_output.get('rationale', '')
                
                # Emit model weight assigned event
                if events_list:
                    model_weight_assigned(
                        events_list,
                        Step.EVIDENCE_SCORE,
                        marker,
                        status,
                        relation,
                        pattern_id,
                        weight,
                        rationale
                    )
                
                return weight
        except Exception as e:
            # Fallback to rule-based on error
            pass
    
    # Use rule-based weight
    marker_weights = WEIGHTS.get(marker, {})
    if isinstance(marker_weights, dict):
        if status in marker_weights:
            status_weights = marker_weights[status]
            if isinstance(status_weights, dict):
                return _coerce_weight(status_weights.get(relation, 0.1))
            return _coerce_weight(status_weights)
        else:
            # Check if marker_weights has direct relation keys (for markers like 'hsCRP')
            return _coerce_weight(marker_weights.get(relation, 0.1))
    return _coerce_weight(0.1)

def build_evidence(case_card, subgraph, normalized_labs, events_list, events):
    abnormal_markers = case_card['abnormal_markers']
    abnormal_marker_node_ids = case_card['abnormal_marker_node_ids']
    signals = case_card['signals']  # now pattern IDs
    marker_status = {lab['marker']: lab['status'] for lab in normalized_labs}

    supports = []
    contradictions = []
    candidate_scores = {}
    top_discriminators = []

    # Initialize scores for candidate patterns
    for pattern_id in signals:
        candidate_scores[pattern_id] = 0.5  # baseline

    # Emit candidates
    events.candidates(events_list, events.Step.EVIDENCE_SCORE, list(candidate_scores.keys()))

    # For each abnormal marker, find edges to patterns
    for marker, marker_node_id in zip(abnormal_markers, abnormal_marker_node_ids):
        status = marker_status[marker]
        for edge in subgraph['edges']:
            if edge['from'] == marker_node_id or edge['to'] == marker_node_id:
                # Determine if edge connects to a pattern
                pattern_id = None
                if edge['from'] in signals:
                    pattern_id = edge['from']
                elif edge['to'] in signals:
                    pattern_id = edge['to']
                if not pattern_id:
                    continue

                relation = edge['relation']
                
                # Get weight (may use model for complex cases)
                weight = get_evidence_weight(
                    marker, status, relation, pattern_id,
                    case_card, {'supports': supports, 'contradictions': contradictions}, events_list
                )

                pattern_label = _pattern_label(pattern_id, subgraph)
                evidence_item = {
                    "pattern_id": pattern_id,
                    "marker": marker,
                    "marker_node_id": marker_node_id,
                    "marker_status": status,
                    "edge_id": edge['id'],
                    "relation": relation,
                    "weight": weight,
                    "label": f"{marker} {status} {relation.lower()} {pattern_label}"
                }

                # Emit evidence applied
                events.evidence_applied(events_list, events.Step.EVIDENCE_SCORE, evidence_item)

                scoring_relation = relation
                if relation in ("INCREASES", "DECREASES"):
                    inferred = _infer_support_relation(relation, status)
                    if inferred:
                        scoring_relation = inferred

                if scoring_relation == 'SUPPORTS':
                    supports.append(evidence_item)
                    candidate_scores[pattern_id] += weight
                elif scoring_relation == 'CONTRADICTS':
                    contradictions.append(evidence_item)
                    candidate_scores[pattern_id] -= weight

                # Emit score update
                events.score_update(events_list, events.Step.EVIDENCE_SCORE, candidate_scores.copy())

                top_discriminators.append(evidence_item)

    # Normalize scores to 0-1
    for pid in candidate_scores:
        candidate_scores[pid] = max(0, min(1, candidate_scores[pid]))

    # Sort top_discriminators by weight desc (ensure numeric)
    for item in top_discriminators:
        if not isinstance(item.get("weight"), (int, float)):
            item["weight"] = _coerce_weight(item.get("weight"))
    top_discriminators.sort(key=lambda x: x['weight'], reverse=True)
    top_discriminators = top_discriminators[:5]  # top 5

    allowed_claims = [
        "Possible iron deficiency pattern",
        "Recommend TSAT test",
        "Avoid iron supplementation as first-line if inflammation pattern present"
    ]

    evidence_bundle = {
        "subgraph": subgraph,
        "supports": supports,
        "contradictions": contradictions,
        "candidate_scores": candidate_scores,
        "top_discriminators": top_discriminators,
        "allowed_claims": allowed_claims
    }

    return evidence_bundle