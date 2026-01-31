"""
Generate a short case impression (patient overview) after guardrails.
Model mode: prompt-based 2–4 sentence summary. Lite mode: rule-based string.
"""
import os
import time
from .model_manager import model_manager
from .events import Step, model_reasoning_start, model_reasoning_end


def _lite_impression(case_card: dict, reasoner_output: dict, guardrail_report: dict) -> str:
    """Build a short impression from top hypothesis, abnormal markers, and guardrail status."""
    parts = []
    hypotheses = reasoner_output.get("hypotheses") or []
    if hypotheses:
        top = hypotheses[0]
        name = top.get("name", "Unknown")
        parts.append(f"Top consideration: {name}.")
    abnormal = case_card.get("abnormal_markers") or []
    if abnormal:
        parts.append(f"Notable abnormal markers: {', '.join(abnormal)}.")
    if guardrail_report.get("status") == "FAIL":
        parts.append("Recommendations were adjusted for safety.")
    if not parts:
        return "Case reviewed; no hypotheses above threshold."
    return " ".join(parts)


def _model_impression(case_card: dict, reasoner_output: dict, guardrail_report: dict, events_list=None) -> str:
    """Generate impression via model using case_impression prompt."""
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "case_impression.txt")
    if not os.path.isfile(prompt_path):
        return _lite_impression(case_card, reasoner_output, guardrail_report)
    with open(prompt_path) as f:
        template = f.read()
    if "===SYSTEM===" in template and "===USER===" in template:
        parts = template.split("===USER===")
        system_prompt = parts[0].replace("===SYSTEM===", "").strip()
        user_template = parts[1].strip()
    else:
        system_prompt = template
        user_template = ""
    abnormal = case_card.get("abnormal_markers") or []
    hypotheses = reasoner_output.get("hypotheses") or []
    hypotheses_summary = "; ".join(
        f"{h.get('name', '?')} ({h.get('confidence', 0):.2f})" for h in hypotheses[:3]
    ) or "None"
    actions = reasoner_output.get("patient_actions") or []
    actions_summary = "; ".join((a.get("task") or "")[:80] for a in actions[:3]) or "None"
    guardrail_status = guardrail_report.get("status", "PASS")
    failed_rules = guardrail_report.get("failed_rules") or []
    if failed_rules:
        rule_ids = [r.get("id") or r.get("message", "") for r in failed_rules[:3]]
        guardrail_status += f" (adjusted: {', '.join(str(x) for x in rule_ids)})"
    user_prompt = user_template.format(
        abnormal_markers=", ".join(abnormal) or "None",
        hypotheses_summary=hypotheses_summary,
        actions_summary=actions_summary,
        guardrail_status=guardrail_status,
    )
    try:
        if events_list is not None:
            model_reasoning_start(events_list, Step.FINAL, "MedGemma is writing case impression...")
        t0 = time.perf_counter()
        response = model_manager.generate(system_prompt, user_prompt, max_tokens=150)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if events_list is not None:
            model_reasoning_end(events_list, Step.FINAL, response_time_ms=elapsed_ms)
        if response and isinstance(response, dict):
            text = (response.get("text") or "").strip()
            if len(text) > 10:
                return text
    except Exception:
        if events_list is not None:
            model_reasoning_end(events_list, Step.FINAL, response_time_ms=0)
        pass
    return _lite_impression(case_card, reasoner_output, guardrail_report)


def generate_case_impression(
    case_card: dict,
    reasoner_output: dict,
    guardrail_report: dict,
    events_list=None,
) -> str:
    """
    Return a short case impression (2–4 sentences).
    Model mode: uses case_impression prompt; lite mode: rule-based from top hypothesis and abnormal markers.
    Set USE_CASE_IMPRESSION_MODEL=0 to use lite impression even when model is loaded (fewer model calls).
    """
    use_impression_model = os.getenv("USE_CASE_IMPRESSION_MODEL", "1").strip().lower() not in ("0", "false")
    if model_manager.lite_mode or not model_manager.model_loaded or not use_impression_model:
        return _lite_impression(case_card, reasoner_output, guardrail_report)
    return _model_impression(case_card, reasoner_output, guardrail_report, events_list)
