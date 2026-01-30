from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import re
from datetime import datetime
from copy import deepcopy
from typing import Optional
from core import lab_normalizer, context_selector, evidence_builder, reasoner_medgemma, guardrails, events
from core import dynamic_graph
from core.model_manager import model_manager
from core.text_to_case import text_to_case

class RunRequest(BaseModel):
    case_id: str

class AnalyzeRequest(BaseModel):
    text: str
    merge_with_current: bool = False

# In-memory current case (set after /run or /analyze; used when merge_with_current=True)
current_case: Optional[dict] = None

# Load cases
def load_cases():
    cases_dir = os.path.join(os.path.dirname(__file__), 'data_synth', 'cases')
    cases = {}
    for f in os.listdir(cases_dir):
        if f.endswith('.json'):
            with open(os.path.join(cases_dir, f)) as file:
                case = json.load(file)
                cases[case['case_id']] = case
    return cases

cases = load_cases()

app = FastAPI()

# Try to pre-load model if MODE=model is set (in background to not block server)
import threading

def preload_model():
    """Pre-load model in background thread"""
    if os.getenv("MODE", "lite").lower() == "model":
        try:
            print("🔄 Pre-loading model (MODE=model detected)...")
            model_manager.load_model()
            if model_manager.model_loaded:
                print("✅ Model pre-loaded successfully!")
            else:
                print("⚠️  Model pre-load attempted but not loaded (will try on first use)")
        except Exception as e:
            print(f"⚠️  Model pre-load failed (will load on first use): {e}")

# Start model loading in background thread (non-blocking)
model_thread = threading.Thread(target=preload_model, daemon=True)
model_thread.start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "med-EVE (Evidence Vector Engine) Demo API", "endpoints": ["/cases", "/health"]}

@app.get("/cases")
def get_cases():
    return [{"id": cid, "summary": f"Case {cid}"} for cid in cases]

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    return cases.get(case_id)

def _run_pipeline(case: dict, events_list: list) -> dict:
    """Run the full pipeline on a case dict (patient + labs); returns same shape as /run."""
    normalized_labs = lab_normalizer.normalize_labs(case["labs"])
    events.start_step(events_list, events.Step.LAB_NORMALIZE)
    events.end_step(events_list, events.Step.LAB_NORMALIZE)

    events.start_step(events_list, events.Step.CONTEXT_SELECT)
    case_card, subgraph = context_selector.select_context(
        normalized_labs, case["patient"]["context"], events_list
    )
    subgraph = dynamic_graph.extend_subgraph(case_card, subgraph)
    events.highlight(
        events_list, events.Step.CONTEXT_SELECT,
        [n["id"] for n in subgraph["nodes"]], [e["id"] for e in subgraph["edges"]],
        "Context subgraph"
    )
    events.end_step(events_list, events.Step.CONTEXT_SELECT)

    events.start_step(events_list, events.Step.EVIDENCE_SCORE)
    evidence_bundle = evidence_builder.build_evidence(
        case_card, subgraph, normalized_labs, events_list, events
    )
    events.end_step(events_list, events.Step.EVIDENCE_SCORE)

    events.start_step(events_list, events.Step.REASON)
    reasoner_output = reasoner_medgemma.reason(case_card, evidence_bundle, events_list)
    events.end_step(events_list, events.Step.REASON)

    events.start_step(events_list, events.Step.GUARDRAILS)
    guardrail_report = guardrails.check_guardrails(
        reasoner_output, case_card, normalized_labs, events_list
    )
    if guardrail_report["status"] == "FAIL":
        events.guardrail_fail(events_list, events.Step.GUARDRAILS, guardrail_report["failed_rules"])
        before = reasoner_output.copy()
        for patch in guardrail_report["patches"]:
            if patch["op"] == "remove":
                path_parts = patch["path"].strip("/").split("/")
                obj = reasoner_output
                for part in path_parts[:-1]:
                    obj = obj[int(part)] if part.isdigit() else obj[part]
                del obj[int(path_parts[-1])]
        events.guardrail_patch_applied(events_list, events.Step.GUARDRAILS, before, reasoner_output)
    events.end_step(events_list, events.Step.GUARDRAILS)

    events.final_ready(events_list)
    model_calls = [e for e in events_list if e.type == "MODEL_CALLED"]
    agent_decisions = [e for e in events_list if e.type == "AGENT_DECISION"]
    return {
        "normalized_labs": normalized_labs,
        "case_card": case_card,
        "evidence_bundle": evidence_bundle,
        "reasoner_output": reasoner_output,
        "guardrail_report": guardrail_report,
        "events": events_list,
        "timings": {},
        "model_usage": {
            "model_calls": len(model_calls),
            "agent_decisions": len(agent_decisions),
            "model_mode": not model_manager.lite_mode,
        },
    }


def _serialize_event(e):
    """Convert Event to dict for JSON (Pydantic v1/v2 compatible)."""
    return e.model_dump() if hasattr(e, "model_dump") else e.dict()


def _merge_parsed_into_current(existing: dict, parsed: dict) -> dict:
    """Merge parsed case (from text) into existing current case. Returns new dict; does not mutate existing."""
    merged = deepcopy(existing)
    # Labs: upsert by marker (existing order first, then new markers from parsed)
    merged_labs = [deepcopy(lab) for lab in existing["labs"]]
    seen = {lab["marker"] for lab in merged_labs}
    for lab in parsed["labs"]:
        if lab["marker"] in seen:
            for i, l in enumerate(merged_labs):
                if l["marker"] == lab["marker"]:
                    merged_labs[i] = deepcopy(lab)
                    break
        else:
            merged_labs.append(deepcopy(lab))
            seen.add(lab["marker"])
    merged["labs"] = merged_labs
    # Patient context: union (parsed overrides)
    merged["patient"] = merged.get("patient") or {"age": None, "sex": None, "context": {}}
    ctx_current = merged["patient"].get("context") or {}
    ctx_parsed = (parsed.get("patient") or {}).get("context") or {}
    merged["patient"]["context"] = {**ctx_current, **ctx_parsed}
    merged["case_id"] = existing.get("case_id") or "FromText"
    return merged


def _write_pipeline_output(case: dict, result: dict) -> Optional[str]:
    """Write pipeline result to output/final_output_{case_id}_{timestamp}.json. Returns path or None on failure."""
    case_id = case.get("case_id") or "FromText"
    sanitized = re.sub(r"[^\w\-]", "_", case_id)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"final_output_{sanitized}_{ts}.json"
    out_dir = os.path.join(os.path.dirname(__file__), "output")
    try:
        os.makedirs(out_dir, exist_ok=True)
        full_path = os.path.join(out_dir, filename)
        payload = deepcopy(result)
        payload["case_id"] = case_id
        payload["timestamp"] = ts
        payload["events"] = [_serialize_event(e) for e in result["events"]]
        with open(full_path, "w") as f:
            json.dump(payload, f, indent=2)
        return os.path.join("output", filename)
    except (OSError, TypeError) as e:
        print(f"Failed to write pipeline output: {e}")
        return None


@app.post("/run")
def run_pipeline(body: RunRequest, mode: str = "lite"):
    case_id = body.case_id
    case = cases[case_id]
    events_list = []

    if os.getenv("MODE", "lite").lower() == "model":
        try:
            model_manager.wait_for_model(timeout=300.0)
        except TimeoutError as e:
            raise HTTPException(
                status_code=503,
                detail="Model did not finish loading. Please try again or check server logs.",
            ) from e

    result = _run_pipeline(case, events_list)
    result["case_id"] = case_id
    result["output_path"] = _write_pipeline_output(case, result)
    global current_case
    current_case = deepcopy(case)
    result["current_case_id"] = case_id
    return result


@app.post("/analyze")
def analyze_from_text(body: AnalyzeRequest):
    """Parse free text into a case, run the same pipeline as /run (local MedGemma), return same shape."""
    events_list = []
    if os.getenv("MODE", "lite").lower() == "model":
        try:
            model_manager.wait_for_model(timeout=300.0)
        except TimeoutError as e:
            raise HTTPException(
                status_code=503,
                detail="Model did not finish loading. Please try again or check server logs.",
            ) from e

    try:
        parsed = text_to_case(body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    global current_case
    if body.merge_with_current and current_case:
        case = _merge_parsed_into_current(current_case, parsed)
    else:
        case = deepcopy(parsed)
        case["case_id"] = "FromText"

    result = _run_pipeline(case, events_list)
    result["case_id"] = case["case_id"]
    result["output_path"] = _write_pipeline_output(case, result)
    current_case = deepcopy(case)
    result["current_case_id"] = case["case_id"]
    return result

@app.get("/current-case")
def get_current_case():
    """Return current case id and summary, or null if none."""
    global current_case
    if current_case is None:
        return None
    cid = current_case.get("case_id") or "FromText"
    n_labs = len(current_case.get("labs") or [])
    return {"case_id": cid, "summary": f"{cid} ({n_labs} labs)"}


@app.delete("/current-case")
def clear_current_case():
    """Clear in-memory current case."""
    global current_case
    current_case = None
    return {"ok": True}


@app.get("/health")
def health():
    return model_manager.get_health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)