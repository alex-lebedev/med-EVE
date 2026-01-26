from .kg_store import kg_store
import yaml
import os

# Load marker to node mapping
with open(os.path.join(os.path.dirname(__file__), 'marker_to_node.yml')) as f:
    MARKER_TO_NODE = yaml.safe_load(f)

# Weights for evidence
WEIGHTS = {
    'hsCRP': {'SUPPORTS': 0.8, 'CONTRADICTS': 0.0},
    'Ferritin': {'HIGH': {'SUPPORTS': 0.7, 'CONTRADICTS': 0.6}, 'LOW': {'SUPPORTS': 0.6, 'CONTRADICTS': 0.7}},
    'Iron': {'LOW': {'SUPPORTS': 0.5, 'CONTRADICTS': 0.4}},
    'TSAT': {'LOW': {'SUPPORTS': 0.4, 'CONTRADICTS': 0.3}},
    'Hb': {'LOW': {'SUPPORTS': 0.3, 'CONTRADICTS': 0.2}},
    'RDW': {'NORMAL': {'SUPPORTS': 0.2, 'CONTRADICTS': 0.1}},
}

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
                weight = WEIGHTS.get(marker, {}).get(status, {}).get(relation, 0.1) if isinstance(WEIGHTS.get(marker, {}), dict) else WEIGHTS.get(marker, {}).get(relation, 0.1)

                evidence_item = {
                    "pattern_id": pattern_id,
                    "marker": marker,
                    "marker_node_id": marker_node_id,
                    "marker_status": status,
                    "edge_id": edge['id'],
                    "relation": relation,
                    "weight": weight,
                    "label": f"{marker} {status} {relation.lower()} {kg_store.nodes[pattern_id]['label']}"
                }

                # Emit evidence applied
                events.evidence_applied(events_list, events.Step.EVIDENCE_SCORE, evidence_item)

                if relation == 'SUPPORTS':
                    supports.append(evidence_item)
                    candidate_scores[pattern_id] += weight
                elif relation == 'CONTRADICTS':
                    contradictions.append(evidence_item)
                    candidate_scores[pattern_id] -= weight

                # Emit score update
                events.score_update(events_list, events.Step.EVIDENCE_SCORE, candidate_scores.copy())

                top_discriminators.append(evidence_item)

    # Normalize scores to 0-1
    for pid in candidate_scores:
        candidate_scores[pid] = max(0, min(1, candidate_scores[pid]))

    # Sort top_discriminators by weight desc
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