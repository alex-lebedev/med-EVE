from typing import Dict, Any, List

from .model_manager import model_manager

MAX_EXPLANATION_TOKENS = 200


def _summarize_abnormal(labs: List[dict]) -> str:
    abnormal = [l for l in (labs or []) if l.get("status") != "NORMAL"]
    return ", ".join(
        f"{l.get('marker')}({l.get('status')}): {l.get('value')} {l.get('unit')}"
        for l in abnormal[:12]
    ) or "None"


def _summarize_hypotheses(hypotheses: List[dict]) -> str:
    return "; ".join(
        f"{h.get('name')} ({float(h.get('confidence', 0)):.2f})"
        for h in (hypotheses or [])[:5]
    ) or "None"


def generate_explanation(
    case_card: Dict[str, Any],
    evidence_bundle: Dict[str, Any],
    reasoner_output: Dict[str, Any],
    normalized_labs: List[dict],
) -> str:
    """
    Generate a short, bounded explanation. Falls back to template if model unavailable.
    """
    abnormal_summary = _summarize_abnormal(normalized_labs)
    hypo_summary = _summarize_hypotheses(reasoner_output.get("hypotheses") or [])
    top_discriminators = (evidence_bundle.get("top_discriminators") or [])[:6]
    evidence_summary = "; ".join(
        f"{e.get('marker')}({e.get('marker_status')})->{e.get('pattern_id')}"
        for e in top_discriminators
    ) or "None"

    if model_manager.lite_mode or not model_manager.model_loaded:
        return (
            f"Abnormal markers: {abnormal_summary}. "
            f"Top hypotheses: {hypo_summary}. "
            f"Key evidence: {evidence_summary}."
        )

    system_prompt = (
        "You are a clinical assistant. Provide a short, plain-language explanation "
        "of why the top hypotheses were selected. Keep it under 5 sentences."
    )
    user_prompt = (
        f"Abnormal markers: {abnormal_summary}\n"
        f"Hypotheses: {hypo_summary}\n"
        f"Key evidence: {evidence_summary}\n"
        "Explain briefly."
    )
    try:
        resp = model_manager.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=MAX_EXPLANATION_TOKENS,
            temperature=0.3,
            top_p=0.9,
        )
        text = (resp.get("text") or "").strip()
        if text:
            return text[:1200]
    except Exception:
        pass

    return (
        f"Abnormal markers: {abnormal_summary}. "
        f"Top hypotheses: {hypo_summary}. "
        f"Key evidence: {evidence_summary}."
    )
