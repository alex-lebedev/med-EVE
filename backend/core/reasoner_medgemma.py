from .model_manager import model_manager
from .agent_manager import agent_manager
from .kg_store import kg_store
from .events import Step, emit_event, EventType, model_reasoning_start, model_reasoning_end, model_called, agent_decision
import json
import os
import re
import time

PATTERN_TO_CONDITION = {
    "p_iron_def": "Iron deficiency anemia",
    "p_inflam_iron_seq": "Anemia of inflammation",
    "p_hypothyroid": "Hypothyroidism"
}

def _condition_label(pattern_id: str, evidence_bundle: dict) -> str:
    """Resolve condition name from PATTERN_TO_CONDITION, then kg_store, then subgraph; last resort 'Unknown condition'."""
    if pattern_id in PATTERN_TO_CONDITION:
        return PATTERN_TO_CONDITION[pattern_id]
    if pattern_id in kg_store.nodes:
        return kg_store.nodes[pattern_id].get("label") or "Unknown condition"
    subgraph = evidence_bundle.get("subgraph") or {}
    for n in (subgraph.get("nodes") or []):
        if n.get("id") == pattern_id:
            return n.get("label") or "Unknown condition"
    return "Unknown condition"


def _trim_subgraph_for_prompt(subgraph: dict) -> dict:
    """Return a minimal subgraph (id, type, label per node; id, from, to, relation per edge) for shorter prompts.
    Optional env HYPOTHESIS_SUBGRAPH_MAX_NODES / HYPOTHESIS_SUBGRAPH_MAX_EDGES (0 = no cap) limit size for small token budgets."""
    if not subgraph:
        return {"nodes": [], "edges": []}
    nodes = []
    for n in subgraph.get("nodes") or []:
        nodes.append({
            "id": n.get("id"),
            "type": n.get("type"),
            "label": n.get("label"),
        })
    edges = []
    for e in subgraph.get("edges") or []:
        edges.append({
            "id": e.get("id"),
            "from": e.get("from"),
            "to": e.get("to"),
            "relation": e.get("relation"),
        })
    max_nodes = int(os.getenv("HYPOTHESIS_SUBGRAPH_MAX_NODES", "0") or "0")
    max_edges = int(os.getenv("HYPOTHESIS_SUBGRAPH_MAX_EDGES", "0") or "0")
    if max_nodes > 0:
        nodes = nodes[:max_nodes]
    if max_edges > 0:
        edges = edges[:max_edges]
    return {"nodes": nodes, "edges": edges}


def _has_ambiguity(hypotheses):
    """Check if hypotheses have ambiguity (top 2 within threshold)"""
    if len(hypotheses) < 2:
        return False
    sorted_hypo = sorted(hypotheses, key=lambda h: h.get('confidence', 0), reverse=True)
    if len(sorted_hypo) < 2:
        return False
    diff = sorted_hypo[0].get('confidence', 0) - sorted_hypo[1].get('confidence', 0)
    return diff < 0.15

def _reason_lite_mode(case_card, evidence_bundle):
    """Generate hypotheses using rule-based logic (lite mode)"""
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

        condition = _condition_label(pattern_id, evidence_bundle)

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
            next_tests = [{"test_id": "t_ferritin", "label": "Ferritin measurement"}]
        elif pattern_id == "p_hypothyroid":
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
            "what_would_change_my_mind": what_would_change_mind,
            "reasoning": "",
        }

        hypotheses.append(hypothesis)

    # Generate patient actions based on top hypothesis
    patient_actions = []
    if sorted_patterns and sorted_patterns[0][0] == "p_inflam_iron_seq":
        iron_patterns = ["p_inflam_iron_seq", "p_iron_def"]
        iron_scores = {p: scores.get(p, 0) for p in iron_patterns if p in scores}
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
        "red_flags": red_flags,
        "hypotheses_valid": len(hypotheses) > 0,
        "provisional": False,
        "novel_insights": [],
        "novel_actions": [],
        "provenance": {
            "kg_grounded": True,
            "notes": "Lite mode: KG-grounded reasoning only."
        }
    }

# Limits for hypothesis prompt (smaller payload = faster inference)
TOP_N_CANDIDATE_PATTERNS = int(os.getenv("HYPOTHESIS_TOP_PATTERNS", "5"))
MAX_SUPPORTS_IN_PROMPT = int(os.getenv("HYPOTHESIS_MAX_SUPPORTS", "15"))
MAX_CONTRADICTIONS_IN_PROMPT = int(os.getenv("HYPOTHESIS_MAX_CONTRADICTIONS", "15"))
MAX_DISCRIMINATORS_IN_PROMPT = int(os.getenv("HYPOTHESIS_MAX_DISCRIMINATORS", "20"))

# Hybrid: rank top N hypotheses with model; add reasoning for top 1-2
HYBRID_RANK_TOP_N = int(os.getenv("HYBRID_RANK_TOP_N", "5"))
HYBRID_REASON_TOP_N = int(os.getenv("HYBRID_REASON_TOP_N", "2"))


def _parse_ranking_line(text: str) -> dict:
    """Parse a line like 'H1=0.8 H2=0.5 H3=0.3' or 'H1=0.8, H2=0.5' into {id: confidence}."""
    out = {}
    if not text or not isinstance(text, str):
        return out
    # Match H1=0.8, H2=0.5, etc. (id = H followed by digits, value = float)
    for m in re.finditer(r"(H\d+)\s*=\s*([0-9]*\.?[0-9]+)", text.strip(), re.IGNORECASE):
        hid, val = m.group(1), m.group(2)
        try:
            v = float(val)
            if 0 <= v <= 1:
                out[hid.upper()] = v
        except ValueError:
            pass
    return out


def _model_rank_hypotheses(hypotheses: list, lab_summary: str, events_list=None) -> None:
    """Call model with short prompt to get ranking line; update hypothesis confidence in place."""
    if not hypotheses or not model_manager.model_loaded:
        return
    top = hypotheses[:HYBRID_RANK_TOP_N]
    line = "Hypotheses: " + "; ".join(f"{h['id']}={h.get('name','')} (current {h.get('confidence',0):.2f})" for h in top)
    prompt = f"Given lab summary: {lab_summary[:200]}. Rank confidence 0-1 for each. Reply with one line only, e.g. H1=0.8 H2=0.5 H3=0.3.\n{line}\nYour line:"
    t0 = time.perf_counter()
    try:
        resp = model_manager.generate(
            system_prompt="You are a clinical assistant. Reply with only a single line of the form H1=x H2=y etc with numbers between 0 and 1.",
            user_prompt=prompt,
            max_tokens=64,
            temperature=0.2,
            top_p=0.9,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        text = (resp.get("text") or "").strip()
        ranking = _parse_ranking_line(text)
        if ranking:
            for h in hypotheses:
                hid = (h.get("id") or "").upper()
                if hid in ranking:
                    h["confidence"] = ranking[hid]
        if events_list:
            model_called(events_list, Step.REASON, "ranking", "ranking",
                         response_time_ms=elapsed_ms, cached=resp.get("cached", False))
    except Exception as e:
        if events_list:
            model_called(events_list, Step.REASON, "ranking", "ranking",
                         status="error", error=str(e),
                         response_time_ms=(time.perf_counter() - t0) * 1000)


def _model_reasoning_for_hypothesis(condition_name: str, lab_summary: str, events_list=None) -> str:
    """One-sentence reason why condition is most likely. Returns empty string on failure."""
    if not model_manager.model_loaded:
        return ""
    prompt = f"Labs: {lab_summary[:150]}. In one sentence, why is {condition_name} most likely here? Reply with one sentence only."
    t0 = time.perf_counter()
    try:
        resp = model_manager.generate(
            system_prompt="You are a clinical assistant. Reply with one short sentence only.",
            user_prompt=prompt,
            max_tokens=80,
            temperature=0.3,
            top_p=0.9,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        text = (resp.get("text") or "").strip()
        if events_list:
            model_called(events_list, Step.REASON, "reasoning", "reasoning",
                         response_time_ms=elapsed_ms, cached=resp.get("cached", False))
        if text and len(text) > 10:
            return text[:500]
    except Exception as e:
        if events_list:
            model_called(events_list, Step.REASON, "reasoning", "reasoning",
                         status="error", error=str(e),
                         response_time_ms=(time.perf_counter() - t0) * 1000)
    return ""


def reason(case_card, evidence_bundle, events_list=None):
    # 1. Always build primary hypothesis list via lite (reliable schema)
    base_result = _reason_lite_mode(case_card, evidence_bundle)
    hypotheses = base_result.get("hypotheses") or []
    patient_actions = base_result.get("patient_actions") or []
    red_flags = base_result.get("red_flags") or []
    novel_insights = base_result.get("novel_insights") or []
    novel_actions = base_result.get("novel_actions") or []
    provenance = base_result.get("provenance") or {"kg_grounded": True, "notes": "Lite mode: KG-grounded reasoning only."}

    if model_manager.lite_mode:
        if events_list:
            agent_decision(events_list, Step.REASON, "hybrid_routing", "use_rules",
                           "Lite mode active; using KG-only reasoning")
        return base_result

    # Model mode: hybrid = lite + model ranking + reasoning prose (default)
    use_hypothesis_json = os.getenv("USE_HYPOTHESIS_GENERATION_MODEL", "").strip().lower() in ("1", "true", "yes")
    if use_hypothesis_json and model_manager.model_loaded:
        # Optional: full hypothesis_generation JSON path (fallback if explicitly enabled)
        try:
            context = {"case_card": case_card, "evidence_bundle": evidence_bundle}
            scores = evidence_bundle.get("candidate_scores", {})
            sorted_patterns = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:TOP_N_CANDIDATE_PATTERNS]
            candidate_patterns = [
                {"pattern_id": pid, "confidence": score, "condition": PATTERN_TO_CONDITION.get(pid, "Unknown condition")}
                for pid, score in sorted_patterns
            ]
            evidence_data = {
                "candidate_patterns_json": json.dumps(candidate_patterns, indent=2),
                "evidence_bundle_json": json.dumps({
                    "supports": (evidence_bundle.get("supports") or [])[:MAX_SUPPORTS_IN_PROMPT],
                    "contradictions": (evidence_bundle.get("contradictions") or [])[:MAX_CONTRADICTIONS_IN_PROMPT],
                    "top_discriminators": (evidence_bundle.get("top_discriminators") or [])[:MAX_DISCRIMINATORS_IN_PROMPT],
                    "candidate_scores": dict(sorted_patterns),
                }, indent=2),
                "patient_context_json": json.dumps(case_card.get("patient_context", {}), indent=2),
                "subgraph_json": json.dumps(_trim_subgraph_for_prompt(evidence_bundle.get("subgraph", {})), indent=2),
            }
            agent_response = agent_manager.call_agent(
                "hypothesis_generation", context, evidence_data, events_list=events_list, step=Step.REASON
            )
            model_output = agent_response.get("result")
            if agent_response.get("use_model") and not model_output and agent_response.get("raw_output"):
                fallback = model_manager._extract_json_from_text(agent_response.get("raw_output") or "")
                if isinstance(fallback, dict) and fallback.get("hypotheses"):
                    model_output = fallback
            if agent_response.get("use_model") and model_output and model_output.get("hypotheses"):
                validated = []
                for h in model_output.get("hypotheses", []):
                    validated.append({
                        "id": h.get("id", "H1"),
                        "name": h.get("name", "Unknown condition"),
                        "confidence": float(h.get("confidence", 0.5)),
                        "evidence": h.get("evidence", []),
                        "counter_evidence": h.get("counter_evidence", []),
                        "next_tests": h.get("next_tests", []),
                        "what_would_change_my_mind": h.get("what_would_change_my_mind", []),
                        "reasoning": h.get("reasoning", ""),
                    })
                hypotheses = validated
                patient_actions = model_output.get("patient_actions") or patient_actions
                red_flags = model_output.get("red_flags") or red_flags
                provenance = {"kg_grounded": True, "notes": "Model hypothesis JSON used."}
                # Optional action_generation / novel_insight (gated by env)
                if agent_manager.should_use_agent("action_generation", {"hypotheses": hypotheses, "case_card": case_card}):
                    try:
                        action_data = {
                            "hypotheses_json": json.dumps(hypotheses, indent=2),
                            "evidence_bundle_json": json.dumps({"supports": evidence_bundle.get("supports", []), "contradictions": evidence_bundle.get("contradictions", [])}, indent=2),
                            "patient_context_json": json.dumps(case_card.get("patient_context", {}), indent=2),
                        }
                        action_resp = agent_manager.call_agent("action_generation", {"hypotheses": hypotheses, "case_card": case_card}, action_data, events_list=events_list, step=Step.REASON)
                        if action_resp.get("use_model") and action_resp.get("result") and action_resp["result"].get("patient_actions"):
                            patient_actions = action_resp["result"]["patient_actions"]
                    except Exception:
                        pass
                novelty_context = {
                    "hypotheses": hypotheses, "case_card": case_card, "evidence_bundle": evidence_bundle,
                    "top_confidence": (hypotheses[0].get("confidence", 0) if hypotheses else 0),
                    "confidence_margin": (hypotheses[0].get("confidence", 0) - hypotheses[1].get("confidence", 0)) if len(hypotheses) > 1 else 1.0,
                    "contradiction_count": len(evidence_bundle.get("contradictions", [])),
                    "support_count": len(evidence_bundle.get("supports", [])),
                    "force_novelty": os.getenv("USE_NOVEL_INSIGHT_MODEL", "").strip().lower() == "force",
                }
                if agent_manager.should_use_agent("novel_insight", novelty_context):
                    try:
                        novelty_data = {
                            "case_card_json": json.dumps(case_card, indent=2),
                            "hypotheses_json": json.dumps(hypotheses, indent=2),
                            "evidence_bundle_json": json.dumps({"supports": evidence_bundle.get("supports", []), "contradictions": evidence_bundle.get("contradictions", []), "candidate_scores": evidence_bundle.get("candidate_scores", {}), "top_discriminators": evidence_bundle.get("top_discriminators", [])}, indent=2),
                            "subgraph_json": json.dumps(evidence_bundle.get("subgraph", {}), indent=2),
                        }
                        novelty_resp = agent_manager.call_agent("novel_insight", novelty_context, novelty_data, events_list=events_list, step=Step.REASON)
                        if novelty_resp.get("use_model") and novelty_resp.get("result"):
                            novel_insights = novelty_resp["result"].get("novel_insights") or []
                            novel_actions = novelty_resp["result"].get("novel_actions") or []
                            for i in novel_insights:
                                i["outside_kg"] = True
                            for a in novel_actions:
                                a["outside_kg"] = True
                            if novel_insights or novel_actions:
                                provenance["kg_grounded"] = False
                                provenance["notes"] = "Outside-KG ideas from novelty agent."
                    except Exception:
                        pass
                return {
                    "hypotheses": hypotheses,
                    "patient_actions": patient_actions,
                    "red_flags": red_flags,
                    "hypotheses_valid": len(hypotheses) > 0,
                    "provisional": False,
                    "novel_insights": novel_insights,
                    "novel_actions": novel_actions,
                    "provenance": provenance,
                    "model_used": True,
                    "raw_model_output": agent_response.get("raw_output"),
                }
        except Exception:
            pass
        # Fall through to hybrid if JSON path failed
    # Hybrid: lite + model ranking + reasoning prose
    if model_manager.model_loaded and hypotheses:
        if events_list:
            agent_decision(events_list, Step.REASON, "hybrid_routing", "use_model",
                           "Hybrid path: KG hypotheses + model ranking and reasoning prose")
        abnormal = case_card.get("abnormal_markers") or []
        lab_summary = "Abnormal: " + ", ".join(abnormal[:10]) if abnormal else "No abnormal markers"
        # Ranking
        if events_list:
            model_reasoning_start(events_list, Step.REASON, "MedGemma is ranking hypotheses...")
        t0 = time.perf_counter()
        _model_rank_hypotheses(hypotheses, lab_summary, events_list)
        if events_list:
            model_reasoning_end(events_list, Step.REASON, response_time_ms=(time.perf_counter() - t0) * 1000)
        # Reasoning prose for top 1-2
        for h in hypotheses[:HYBRID_REASON_TOP_N]:
            cond = (h.get("name") or "").split(" (")[0].strip() or "This condition"
            if events_list:
                model_reasoning_start(events_list, Step.REASON, "MedGemma is explaining...")
            t1 = time.perf_counter()
            reasoning_text = _model_reasoning_for_hypothesis(cond, lab_summary, events_list)
            if events_list:
                model_reasoning_end(events_list, Step.REASON, response_time_ms=(time.perf_counter() - t1) * 1000)
            if reasoning_text:
                h["reasoning"] = reasoning_text
        provenance["notes"] = "Hybrid: KG-grounded reasoning with model-augmented ranking and explanations."
    # Optional action_generation (gated; default off)
    _action_use = agent_manager.should_use_agent("action_generation", {"hypotheses": hypotheses, "case_card": case_card})
    if events_list:
        agent_decision(events_list, Step.REASON, "action_generation",
                       "use_model" if _action_use else "use_rules",
                       "Action generation gated by env flag and case complexity")
    if _action_use:
        try:
            action_data = {
                "hypotheses_json": json.dumps(hypotheses, indent=2),
                "evidence_bundle_json": json.dumps({"supports": evidence_bundle.get("supports", []), "contradictions": evidence_bundle.get("contradictions", [])}, indent=2),
                "patient_context_json": json.dumps(case_card.get("patient_context", {}), indent=2),
            }
            action_resp = agent_manager.call_agent("action_generation", {"hypotheses": hypotheses, "case_card": case_card}, action_data, events_list=events_list, step=Step.REASON)
            if action_resp.get("use_model") and action_resp.get("result") and action_resp["result"].get("patient_actions"):
                patient_actions = action_resp["result"]["patient_actions"]
        except Exception:
            pass
    # Optional novel_insight (gated; default off)
    novelty_context = {
        "hypotheses": hypotheses, "case_card": case_card, "evidence_bundle": evidence_bundle,
        "top_confidence": (hypotheses[0].get("confidence", 0) if hypotheses else 0),
        "confidence_margin": (hypotheses[0].get("confidence", 0) - hypotheses[1].get("confidence", 0)) if len(hypotheses) > 1 else 1.0,
        "contradiction_count": len(evidence_bundle.get("contradictions", [])),
        "support_count": len(evidence_bundle.get("supports", [])),
        "force_novelty": os.getenv("USE_NOVEL_INSIGHT_MODEL", "").strip().lower() == "force",
    }
    _novelty_use = agent_manager.should_use_agent("novel_insight", novelty_context)
    if events_list:
        agent_decision(events_list, Step.REASON, "novel_insight",
                       "use_model" if _novelty_use else "use_rules",
                       "Novel insight gated by env flag and case ambiguity")
    if _novelty_use:
        try:
            novelty_data = {
                "case_card_json": json.dumps(case_card, indent=2),
                "hypotheses_json": json.dumps(hypotheses, indent=2),
                "evidence_bundle_json": json.dumps({"supports": evidence_bundle.get("supports", []), "contradictions": evidence_bundle.get("contradictions", []), "candidate_scores": evidence_bundle.get("candidate_scores", {}), "top_discriminators": evidence_bundle.get("top_discriminators", [])}, indent=2),
                "subgraph_json": json.dumps(evidence_bundle.get("subgraph", {}), indent=2),
            }
            novelty_resp = agent_manager.call_agent("novel_insight", novelty_context, novelty_data, events_list=events_list, step=Step.REASON)
            if novelty_resp.get("use_model") and novelty_resp.get("result"):
                novel_insights = novelty_resp["result"].get("novel_insights") or []
                novel_actions = novelty_resp["result"].get("novel_actions") or []
                for i in novel_insights:
                    i["outside_kg"] = True
                for a in novel_actions:
                    a["outside_kg"] = True
                if novel_insights or novel_actions:
                    provenance["kg_grounded"] = False
                    provenance["notes"] = "Outside-KG ideas from novelty agent."
        except Exception:
            pass

    return {
        "hypotheses": hypotheses,
        "patient_actions": patient_actions,
        "red_flags": red_flags,
        "hypotheses_valid": len(hypotheses) > 0,
        "provisional": False,
        "novel_insights": novel_insights,
        "novel_actions": novel_actions,
        "provenance": provenance,
        "model_used": model_manager.model_loaded,
    }
