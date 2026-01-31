import yaml
import os
import json
from .kg_store import kg_store
from .model_manager import model_manager
from .agent_manager import agent_manager
from .events import Step

# Load marker to node mapping
with open(os.path.join(os.path.dirname(__file__), 'marker_to_node.yml')) as f:
    MARKER_TO_NODE = yaml.safe_load(f)

def _rule_based_signals(abnormal_markers):
    """Rule-based pattern IDs (fallback when subgraph-derived signals are empty)."""
    signals = []
    if any(m in abnormal_markers for m in ['Ferritin', 'Iron', 'TSAT', 'Hb']):
        signals.append("p_iron_def")
    if any(m in abnormal_markers for m in ['TSH', 'FT4', 'FT3']):
        signals.append("p_hypothyroid")
    if 'hsCRP' in abnormal_markers:
        signals.append("p_inflam_iron_seq")
    if 'ANC' in abnormal_markers:
        signals.append("p_inflam_iron_seq")
    return signals


def _marker_to_nid(marker: str) -> str:
    """Canonical marker name -> node id (same order as abnormal_markers for downstream pairing)."""
    return MARKER_TO_NODE.get(marker, f"m_{marker.lower().replace(' ', '_')}")


def select_context(normalized_labs, patient_context, events_list=None):
    # Extract abnormal markers and anchor node ids in same order (for correct nid<->label pairing)
    abnormal_markers = [lab['marker'] for lab in normalized_labs if lab['status'] != 'NORMAL']
    abnormal_marker_node_ids = [_marker_to_nid(m) for m in abnormal_markers]

    # Get subgraph from KG based on anchors (pass sorted ids for deterministic subgraph)
    subgraph = kg_store.subgraph_from_markers(sorted(set(abnormal_marker_node_ids)))
    subgraph_node_ids = {n["id"] for n in (subgraph.get("nodes") or [])}

    # Derive signals from subgraph: pattern and condition node IDs in subgraph
    derived_signals = []
    for n in (subgraph.get("nodes") or []):
        if n.get("type") in ("Pattern", "Condition"):
            derived_signals.append(n["id"])
    derived_signals = sorted(derived_signals)

    # Fallback: if no pattern/condition in subgraph, use rule-based signals
    if not derived_signals:
        signals = _rule_based_signals(abnormal_markers)
    else:
        signals = derived_signals

    # Check if we should use model for context selection
    context = {
        'abnormal_markers': abnormal_markers,
        'patient_context': patient_context
    }
    
    use_model = agent_manager.should_use_agent('context_selection', context)
    
    if use_model and not model_manager.lite_mode:
        try:
            # Prepare data for agent
            abnormal_labs_json = json.dumps([
                {
                    "marker": lab['marker'],
                    "value": lab['value'],
                    "unit": lab['unit'],
                    "status": lab['status']
                }
                for lab in normalized_labs if lab['status'] != 'NORMAL'
            ], indent=2)
            
            agent_data = {
                "abnormal_labs_json": abnormal_labs_json,
                "patient_context_json": json.dumps(patient_context, indent=2)
            }
            
            # Call context selection agent
            agent_response = agent_manager.call_agent(
                'context_selection',
                context,
                agent_data,
                events_list=events_list,
                step=Step.CONTEXT_SELECT
            )
            if agent_response.get('use_model') and agent_response.get('result'):
                model_output = agent_response['result']
                # Extract patterns from model output; merge with derived signals (filter to subgraph)
                model_patterns = model_output.get('patterns', [])
                if model_patterns:
                    model_pattern_ids = [p.get('pattern_id') for p in model_patterns if p.get('pattern_id')]
                    merged = set(signals) | {pid for pid in model_pattern_ids if pid in subgraph_node_ids}
                    signals = sorted(merged)
                missing_tests = model_output.get('missing_tests', [])
            else:
                missing_tests = []
        except Exception as e:
            # Fallback to rule-based on error
            if events_list:
                from .events import emit_event, EventType
                emit_event(events_list, Step.CONTEXT_SELECT, EventType.MODEL_CALLED, {
                    'agent_type': 'context_selection',
                    'prompt_type': 'context_selection',
                    'status': 'error',
                    'error': str(e),
                    'response_time_ms': 0
                })
            missing_tests = []
    else:
        missing_tests = []

    case_card = {
        "abnormal_markers": abnormal_markers,
        "abnormal_marker_node_ids": abnormal_marker_node_ids,
        "signals": signals,
        "patient_context": patient_context,
        "normalized_labs": normalized_labs,
        "missing_key_tests": missing_tests
    }
    return case_card, subgraph