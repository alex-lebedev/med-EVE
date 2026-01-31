import yaml
import os
import json
from .model_manager import model_manager
from .agent_manager import agent_manager
from .events import Step

with open(os.path.join(os.path.dirname(__file__), '..', 'guardrails', 'guardrails.yml'), 'r') as f:
    GUARDRAILS = yaml.safe_load(f)['rules']

ALLOWED_BUCKETS = [
    "tests", "scheduling", "questions for clinician", "low-risk defaults"
]


def _task_in_allowed_buckets(task_lower: str) -> bool:
    """True if task text matches at least one allowed bucket. 'test' or 'tests' satisfies tests bucket."""
    if "test" in task_lower:  # "test" or "tests" satisfies tests bucket
        return True
    for bucket in ALLOWED_BUCKETS:
        if bucket == "tests":
            continue  # already handled above
        if bucket in task_lower:
            return True
    return False

def _apply_action_guardrails(actions, inflammation_pattern, failed_rules, patches, scope):
    """Apply action guardrails to a list of actions."""
    for i, action in enumerate(actions):
        task_lower = action.get('task', '').lower()
        if "iron" in task_lower and "supplement" in task_lower and inflammation_pattern:
            failed_rules.append({
                "id": "GR_001",
                "message": "Iron supplementation blocked under inflammation pattern.",
                "scope": scope
            })
            patches.append({"op": "remove", "path": f"/{scope}/{i}"})
        if any(word in task_lower for word in ["mg", "dose", "supplement"]):
            failed_rules.append({
                "id": "GR_003",
                "message": "No dosing recommendations allowed.",
                "scope": scope
            })
            patches.append({"op": "remove", "path": f"/{scope}/{i}"})
        if not _task_in_allowed_buckets(task_lower):
            failed_rules.append({
                "id": "GR_004",
                "message": f"Action '{action.get('task', '')}' not in allowed buckets.",
                "scope": scope
            })
            patches.append({"op": "remove", "path": f"/{scope}/{i}"})

def check_guardrails(reasoner_output, case_card, normalized_labs, events_list=None):
    failed_rules = []
    patches = []

    # GR_001, GR_003, GR_004: Apply to patient and novel actions
    inflammation_pattern = "p_inflam_iron_seq" in case_card['signals']
    patient_actions = reasoner_output.get('patient_actions', [])
    novel_actions = reasoner_output.get('novel_actions', [])
    _apply_action_guardrails(patient_actions, inflammation_pattern, failed_rules, patches, "patient_actions")
    _apply_action_guardrails(novel_actions, inflammation_pattern, failed_rules, patches, "novel_actions")

    # GR_005: No invention
    all_markers = [lab['marker'] for lab in normalized_labs]
    hypotheses = reasoner_output.get('hypotheses', [])
    for h_idx, hypo in enumerate(hypotheses):
        evidence = hypo.get('evidence', [])
        for e_idx, ev in enumerate(evidence):
            if ev['marker'] not in all_markers:
                failed_rules.append({"id": "GR_005", "message": f"Marker '{ev['marker']}' not in input."})
                patches.append({"op": "remove", "path": f"/hypotheses/{h_idx}/evidence/{e_idx}"})

    status = "FAIL" if failed_rules else "PASS"
    
    # If guardrails failed and model is available, generate explanations
    explanations = []
    if status == "FAIL" and not model_manager.lite_mode and agent_manager.should_use_agent(
        "guardrail_explanation",
        {"guardrail_failed": True, "failed_rules": failed_rules}
    ):
        try:
            for failed_rule in failed_rules:
                rule_id = failed_rule.get('id', 'Unknown')
                rule_message = failed_rule.get('message', '')
                
                guardrail_agent_data = {
                    "rule_id": rule_id,
                    "rule_message": rule_message,
                    "triggered_action_json": json.dumps({
                        "patient_actions": reasoner_output.get('patient_actions', []),
                        "novel_actions": reasoner_output.get('novel_actions', [])
                    }, indent=2),
                    "hypotheses_json": json.dumps(reasoner_output.get('hypotheses', []), indent=2),
                    "case_card_json": json.dumps(case_card, indent=2),
                    "patient_context_json": json.dumps(case_card.get('patient_context', {}), indent=2)
                }
                
                guardrail_agent_response = agent_manager.call_agent(
                    'guardrail_explanation',
                    {'guardrail_failed': True, 'failed_rules': failed_rules},
                    guardrail_agent_data,
                    events_list=events_list,
                    step=Step.GUARDRAILS
                )
                
                if guardrail_agent_response.get('use_model') and guardrail_agent_response.get('result'):
                    explanations.append({
                        "rule_id": rule_id,
                        "explanation": guardrail_agent_response['result'].get('explanation', ''),
                        "risk_level": guardrail_agent_response['result'].get('risk_level', 'medium'),
                        "alternative_actions": guardrail_agent_response['result'].get('alternative_actions', [])
                    })
        except Exception as e:
            # Continue without explanations if agent fails
            pass
    
    return {
        "status": status,
        "failed_rules": failed_rules,
        "patches": patches,
        "explanations": explanations
    }