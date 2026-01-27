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

def select_context(normalized_labs, patient_context, events_list=None):
    # Extract abnormal markers
    abnormal_markers = [lab['marker'] for lab in normalized_labs if lab['status'] != 'NORMAL']
    abnormal_marker_node_ids = sorted([MARKER_TO_NODE.get(m, f"m_{m.lower().replace(' ', '_')}") for m in abnormal_markers])

    # Rule-based pattern detection (fallback)
    signals = []
    if any(m in abnormal_markers for m in ['Ferritin', 'Iron', 'TSAT', 'Hb']):
        signals.append("p_iron_def")
    if any(m in abnormal_markers for m in ['TSH', 'FT4', 'FT3']):
        signals.append("p_hypothyroid")
    if 'hsCRP' in abnormal_markers:
        signals.append("p_inflam_iron_seq")

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
                
                # Extract patterns from model output
                model_patterns = model_output.get('patterns', [])
                if model_patterns:
                    # Use model-identified patterns (merge with rule-based)
                    model_pattern_ids = [p.get('pattern_id') for p in model_patterns if p.get('pattern_id')]
                    signals = list(set(signals + model_pattern_ids))  # Merge, remove duplicates
                
                # Extract missing tests if provided
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

    # Get subgraph from KG based on markers
    subgraph = kg_store.subgraph_from_markers(abnormal_marker_node_ids)

    return case_card, subgraph