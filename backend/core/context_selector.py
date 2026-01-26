import yaml
import os
from .kg_store import kg_store

# Load marker to node mapping
with open(os.path.join(os.path.dirname(__file__), 'marker_to_node.yml')) as f:
    MARKER_TO_NODE = yaml.safe_load(f)

def select_context(normalized_labs, patient_context):
    # Extract abnormal markers
    abnormal_markers = [lab['marker'] for lab in normalized_labs if lab['status'] != 'NORMAL']
    abnormal_marker_node_ids = sorted([MARKER_TO_NODE.get(m, f"m_{m.lower().replace(' ', '_')}") for m in abnormal_markers])

    # Signals as pattern node IDs
    signals = []
    if any(m in abnormal_markers for m in ['Ferritin', 'Iron', 'TSAT', 'Hb']):
        signals.append("p_iron_def")
    if any(m in abnormal_markers for m in ['TSH', 'FT4', 'FT3']):
        signals.append("p_hypothyroid")
    if 'hsCRP' in abnormal_markers:
        signals.append("p_inflam_iron_seq")

    case_card = {
        "abnormal_markers": abnormal_markers,
        "abnormal_marker_node_ids": abnormal_marker_node_ids,
        "signals": signals,
        "patient_context": patient_context,
        "normalized_labs": normalized_labs
    }

    # Get subgraph from KG based on markers
    subgraph = kg_store.subgraph_from_markers(abnormal_marker_node_ids)

    return case_card, subgraph