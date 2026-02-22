import time
from typing import Dict, Any, List, Optional

from .model_manager import model_manager
from .events import Step, model_reasoning_start, model_reasoning_end, model_called, agent_decision

MAX_CRITIC_TOKENS = 160


def _summarize_hypotheses(hypotheses: List[dict]) -> str:
    parts = []
    for h in (hypotheses or [])[:5]:
        parts.append(f"{h.get('id')}|{h.get('name')}|{float(h.get('confidence', 0)):.2f}")
    return "; ".join(parts) or "None"


def _summarize_evidence(evidence_bundle: Dict[str, Any]) -> str:
    top = (evidence_bundle.get("top_discriminators") or [])[:6]
    if not top:
        return "None"
    return "; ".join(
        f"{e.get('marker')}({e.get('marker_status')})->{e.get('pattern_id')}"
        for e in top
    )


def _parse_critic_lines(text: str) -> List[dict]:
    """
    Parse critic lines into patch ops.
    Supported line formats:
      REMOVE_HYPOTHESIS H2
      LOWER_CONFIDENCE H1 0.55
      REMOVE_ACTION patient_actions 0
    """
    ops = []
    if not text:
        return ops
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        cmd = parts[0].upper()
        if cmd == "REMOVE_HYPOTHESIS" and len(parts) >= 2:
            ops.append({"op": "remove_hypothesis", "id": parts[1].upper()})
        elif cmd == "LOWER_CONFIDENCE" and len(parts) >= 3:
            try:
                val = float(parts[2])
            except ValueError:
                continue
            ops.append({"op": "lower_confidence", "id": parts[1].upper(), "value": val})
        elif cmd == "REMOVE_ACTION" and len(parts) >= 3:
            scope = parts[1]
            try:
                idx = int(parts[2])
            except ValueError:
                continue
            ops.append({"op": "remove_action", "scope": scope, "index": idx})
    return ops


def run_critic(
    reasoner_output: Dict[str, Any],
    case_card: Dict[str, Any],
    evidence_bundle: Dict[str, Any],
    normalized_labs: List[dict],
    events_list: Optional[list] = None,
) -> Dict[str, Any]:
    """
    MedGemma-only critic. Produces a short patch plan.
    Returns: {"ops": [...], "raw_output": str, "model_used": bool}
    """
    if model_manager.lite_mode or not model_manager.model_loaded:
        if events_list:
            agent_decision(events_list, Step.CRITIC, "critic",
                           "use_rules", "Model not available; skipping critic")
        return {"ops": [], "raw_output": "", "model_used": False}

    if events_list:
        agent_decision(events_list, Step.CRITIC, "critic",
                       "use_model", "Model loaded; running MedGemma safety critic")

    hypotheses = reasoner_output.get("hypotheses") or []
    abnormal = case_card.get("abnormal_markers") or []
    hypo_summary = _summarize_hypotheses(hypotheses)
    evidence_summary = _summarize_evidence(evidence_bundle)
    abnormal_summary = ", ".join(abnormal[:10]) if abnormal else "None"

    system_prompt = (
        "You are a medical safety critic. "
        "Only output patch commands, one per line, from this list:\n"
        "REMOVE_HYPOTHESIS <H#>\n"
        "LOWER_CONFIDENCE <H#> <0-1>\n"
        "REMOVE_ACTION <patient_actions|novel_actions> <index>\n"
        "Output nothing else."
    )
    user_prompt = (
        f"Abnormal markers: {abnormal_summary}\n"
        f"Hypotheses: {hypo_summary}\n"
        f"Top evidence: {evidence_summary}\n"
        "If any hypothesis is unsafe or contradicted, remove or lower it. "
        "If any action is unsafe, remove it."
    )

    if events_list:
        model_reasoning_start(events_list, Step.CRITIC, "MedGemma is critiquing...")
    t0 = time.perf_counter()
    raw = ""
    try:
        resp = model_manager.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=MAX_CRITIC_TOKENS,
            temperature=0.2,
            top_p=0.9,
        )
        raw = (resp.get("text") or "").strip()
        if events_list:
            model_called(events_list, Step.CRITIC, "critic", "critic",
                         response_time_ms=(time.perf_counter() - t0) * 1000,
                         cached=resp.get("cached", False))
    except Exception as e:
        if events_list:
            model_called(events_list, Step.CRITIC, "critic", "critic", status="error", error=str(e))
    finally:
        if events_list:
            model_reasoning_end(events_list, Step.CRITIC, response_time_ms=(time.perf_counter() - t0) * 1000)

    ops = _parse_critic_lines(raw)
    return {"ops": ops, "raw_output": raw, "model_used": True}
