"""
Map symptom/free-text tokens to graph patterns: rule-based suggestion then MedGemma judges keep/change/do_not_map.
Returns nodes and edges to add to subgraph, and list of unmappable tokens.
"""
import os
import re
import json
import yaml
from typing import List, Tuple, Dict, Any

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "symptom_to_pattern.yml")
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "symptom_mapping.txt")

_config_cache = None
_prompt_template = None


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        if os.path.isfile(_CONFIG_PATH):
            with open(_CONFIG_PATH) as f:
                _config_cache = yaml.safe_load(f) or {}
        else:
            _config_cache = {}
    return _config_cache


def _load_prompt() -> str:
    global _prompt_template
    if _prompt_template is None:
        if os.path.isfile(_PROMPT_PATH):
            with open(_PROMPT_PATH) as f:
                _prompt_template = f.read()
        else:
            _prompt_template = ""
    return _prompt_template


def _symptom_to_node_id(token: str) -> str:
    """Canonical node id for a symptom token (e.g. fatigue -> s_fatigue)."""
    safe = re.sub(r"[^\w\-]", "_", (token or "").strip().lower())
    return f"s_{safe}" if safe else f"s_unknown"


def _get_rule_suggestion(token: str) -> dict:
    """First mapping from symptom_to_pattern.yml for this token (lowercase match)."""
    config = _load_config()
    lower = (token or "").strip().lower()
    rules = config.get(lower) or config.get(token) or []
    if not rules:
        return {}
    first = rules[0] if isinstance(rules, list) else rules
    if isinstance(first, dict):
        return {
            "pattern_id": first.get("pattern_id"),
            "relation": first.get("relation") or "SUPPORTS",
            "rationale": first.get("rationale") or "",
        }
    return {}


def _call_model_for_token(
    token: str,
    suggested: dict,
    case_card: dict,
    reasoner_output: dict,
    model_manager,
) -> dict:
    """Call MedGemma to get keep/change/do_not_map and optional pattern_id, relation, rationale."""
    template = _load_prompt()
    if not template or "===SYSTEM===" not in template:
        return {"action": "do_not_map"}
    parts = template.split("===USER===")
    system_prompt = parts[0].replace("===SYSTEM===", "").strip()
    user_template = parts[1].strip() if len(parts) > 1 else ""
    abnormal_markers = case_card.get("abnormal_markers") or []
    hypotheses = reasoner_output.get("hypotheses") or []
    top_hypotheses = "; ".join(
        f"{h.get('name', '?')} ({h.get('confidence', 0):.2f})" for h in hypotheses[:3]
    ) or "None"
    suggested_json = json.dumps(suggested) if suggested else "{}"
    user_prompt = user_template.format(
        symptom_token=token,
        suggested_json=suggested_json,
        abnormal_markers=", ".join(abnormal_markers) or "None",
        top_hypotheses=top_hypotheses,
    )
    try:
        response = model_manager.generate(system_prompt, user_prompt, max_tokens=150)
        data = response.get("json") if isinstance(response, dict) else None
        if data and isinstance(data, dict):
            action = (data.get("action") or "").lower()
            if action in ("keep", "change"):
                pid = data.get("pattern_id")
                rel = data.get("relation") or "SUPPORTS"
                rat = data.get("rationale") or ""
                if pid:
                    return {"action": action, "pattern_id": pid, "relation": rel, "rationale": rat}
            return {"action": "do_not_map"}
    except Exception:
        pass
    return {"action": "do_not_map"}


def map_symptoms_to_graph(
    symptom_tokens: List[str],
    case_card: dict,
    subgraph: dict,
    model_manager,
    reasoner_output: dict = None,
    events_list: list = None,
) -> Tuple[List[dict], List[dict], List[str]]:
    """
    For each token: rule suggestion then MedGemma keep/change/do_not_map.
    Returns (nodes_to_add, edges_to_add, unmappable_list).
    """
    nodes_to_add = []
    edges_to_add = []
    unmappable = []
    signals = set(case_card.get("signals") or [])
    subgraph_node_ids = {n["id"] for n in (subgraph.get("nodes") or [])}
    reasoner_output = reasoner_output or {}
    edge_counter = [0]

    def next_edge_id(symptom_node_id: str, pattern_id: str) -> str:
        edge_counter[0] += 1
        return f"e_sym_{symptom_node_id}_{pattern_id}_{edge_counter[0]}"

    for token in (symptom_tokens or []):
        if not (token or str(token).strip()):
            continue
        token = str(token).strip()
        node_id = _symptom_to_node_id(token)
        if node_id in subgraph_node_ids:
            continue
        suggested = _get_rule_suggestion(token)
        use_symptom_model = os.getenv("USE_SYMPTOM_MAPPER_MODEL", "1").strip().lower() not in ("0", "false")
        if model_manager.lite_mode or not getattr(model_manager, "model_loaded", False) or not use_symptom_model:
            action = "keep" if suggested and suggested.get("pattern_id") in signals else "do_not_map"
            if action == "keep":
                pattern_id = suggested.get("pattern_id")
                relation = suggested.get("relation") or "SUPPORTS"
                rationale = suggested.get("rationale") or ""
            else:
                pattern_id = None
                relation = rationale = ""
        else:
            result = _call_model_for_token(token, suggested, case_card, reasoner_output, model_manager)
            action = result.get("action", "do_not_map")
            pattern_id = result.get("pattern_id")
            relation = result.get("relation") or "SUPPORTS"
            rationale = result.get("rationale") or ""

        if action in ("keep", "change") and pattern_id and pattern_id in signals and pattern_id in subgraph_node_ids:
            label = token.replace("_", " ").strip()
            if not label:
                label = token
            nodes_to_add.append({
                "id": node_id,
                "type": "Symptom",
                "label": label,
                "description": "User-reported symptom or context.",
                "dynamic": True,
            })
            subgraph_node_ids.add(node_id)
            edge_id = next_edge_id(node_id, pattern_id)
            edges_to_add.append({
                "id": edge_id,
                "from": node_id,
                "to": pattern_id,
                "relation": relation,
                "rationale": rationale,
                "source_label": "symptom_mapper",
            })
        else:
            unmappable.append(token)

    return nodes_to_add, edges_to_add, unmappable
