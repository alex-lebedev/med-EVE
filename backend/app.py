from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import logging
import os
import re
import time
from datetime import datetime
from copy import deepcopy
from typing import Optional
import queue
from core import lab_normalizer, context_selector, evidence_builder, reasoner_medgemma, guardrails, events
from core import dynamic_graph
from core.case_impression import generate_case_impression
from core import symptom_mapper
from core.model_manager import model_manager
from core.text_to_case import text_to_case

class RunRequest(BaseModel):
    case_id: str

class AnalyzeRequest(BaseModel):
    text: str
    merge_with_current: bool = False

# In-memory current case (set after /run or /analyze; used when merge_with_current=True)
current_case: Optional[dict] = None
current_output: Optional[dict] = None


class EventList(list):
    """List that emits events on append for streaming."""
    def __init__(self, emit_callback=None):
        super().__init__()
        self._emit_callback = emit_callback

    def append(self, item):
        super().append(item)
        if self._emit_callback:
            self._emit_callback(item)


def _current_output_path() -> str:
    return os.path.join(os.path.dirname(__file__), "output", "current_output.json")


def _load_current_output() -> Optional[dict]:
    """Load last current_output from disk if present."""
    path = _current_output_path()
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_current_output(case_id: str, reasoner_output: dict) -> Optional[str]:
    """Persist last successful reasoner_output for merge across restarts."""
    out_dir = os.path.join(os.path.dirname(__file__), "output")
    try:
        os.makedirs(out_dir, exist_ok=True)
        payload = {
            "case_id": case_id,
            "timestamp": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            "reasoner_output": deepcopy(reasoner_output),
        }
        path = _current_output_path()
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        return path
    except (OSError, TypeError):
        return None


current_output = _load_current_output()

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
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("REQUEST %s %s", request.method, request.url.path)
    response = await call_next(request)
    return response

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

@app.post("/debug/ping")
def debug_ping():
    return {"status": "ok"}

@app.post("/debug/raw-run")
async def debug_raw_run(request: Request):
    body = await request.body()
    return {
        "status": "ok",
        "content_type": request.headers.get("content-type"),
        "length": len(body),
        "preview": body[:200].decode("utf-8", errors="replace"),
    }

@app.get("/cases")
def get_cases():
    return [{"id": cid, "summary": f"Case {cid}"} for cid in cases]

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    return cases.get(case_id)

def _run_pipeline(case: dict, events_list: list, emit_callback=None, merge_with_current: bool = False, prev_reasoner_output: Optional[dict] = None) -> dict:
    """Run the full pipeline on a case dict (patient + labs); returns same shape as /run."""
    t_start = time.time()
    step_times = {}

    t_step_start = time.time()
    logger.info("PIPELINE start: LAB_NORMALIZE")
    normalized_labs = lab_normalizer.normalize_labs(case["labs"])
    events.start_step(events_list, events.Step.LAB_NORMALIZE)
    events.end_step(events_list, events.Step.LAB_NORMALIZE)
    step_times["LAB_NORMALIZE"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: LAB_NORMALIZE")

    t_step_start = time.time()
    logger.info("PIPELINE start: CONTEXT_SELECT")
    events.start_step(events_list, events.Step.CONTEXT_SELECT)
    case_card, subgraph = context_selector.select_context(
        normalized_labs, case["patient"]["context"], events_list
    )
    subgraph, suggested_kg_additions = dynamic_graph.extend_subgraph(case_card, subgraph)
    # Symptom mapping: rule suggestion + MedGemma keep/change/do_not_map per token
    symptom_tokens = case.get("symptom_tokens") or list(
        (case.get("patient") or {}).get("context") or {}
    )
    symptom_nodes, symptom_edges, unmappable_inputs = symptom_mapper.map_symptoms_to_graph(
        symptom_tokens, case_card, subgraph, model_manager, reasoner_output=None, events_list=events_list
    )
    if symptom_nodes or symptom_edges:
        subgraph["nodes"] = list(subgraph.get("nodes") or []) + symptom_nodes
        subgraph["edges"] = list(subgraph.get("edges") or []) + symptom_edges
        suggested_kg_additions["nodes"] = list(suggested_kg_additions.get("nodes") or []) + symptom_nodes
        suggested_kg_additions["edges"] = list(suggested_kg_additions.get("edges") or []) + [
            {"from": e["from"], "to": e["to"], "relation": e.get("relation"), "rationale": e.get("rationale")}
            for e in symptom_edges
        ]
    # Unlinked = dynamic markers (not in KG) with no edges; use correct nid->label map, dynamic-only
    edge_node_ids = set()
    for e in subgraph.get("edges") or []:
        edge_node_ids.add(e.get("from"))
        edge_node_ids.add(e.get("to"))
    dynamic_node_ids = {n["id"] for n in (subgraph.get("nodes") or []) if n.get("dynamic") is True}
    abnormal_markers = case_card.get("abnormal_markers") or []
    abnormal_marker_node_ids = case_card.get("abnormal_marker_node_ids") or []
    nid_to_label = {context_selector._marker_to_nid(m): m for m in abnormal_markers}
    unlinked_markers = [
        nid_to_label[nid] for nid in abnormal_marker_node_ids
        if nid in nid_to_label and nid in dynamic_node_ids and nid not in edge_node_ids
    ]
    events.highlight(
        events_list, events.Step.CONTEXT_SELECT,
        [n["id"] for n in subgraph["nodes"]], [e["id"] for e in subgraph["edges"]],
        "Context subgraph"
    )
    events.end_step(events_list, events.Step.CONTEXT_SELECT)
    step_times["CONTEXT_SELECT"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: CONTEXT_SELECT")

    t_step_start = time.time()
    logger.info("PIPELINE start: EVIDENCE_SCORE")
    events.start_step(events_list, events.Step.EVIDENCE_SCORE)
    evidence_bundle = evidence_builder.build_evidence(
        case_card, subgraph, normalized_labs, events_list, events
    )
    events.end_step(events_list, events.Step.EVIDENCE_SCORE)
    step_times["EVIDENCE_SCORE"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: EVIDENCE_SCORE")

    provisional_reasoner_output = None
    if emit_callback:
        try:
            provisional_reasoner_output = reasoner_medgemma._reason_lite_mode(case_card, evidence_bundle)
            provisional_reasoner_output["provisional"] = True
            provisional_reasoner_output = _sanitize_reasoner_output(provisional_reasoner_output)
            emit_callback({
                "type": "partial",
                "payload": {
                    "reasoner_output": provisional_reasoner_output,
                    "provisional": True
                }
            })
        except Exception:
            provisional_reasoner_output = None

    t_step_start = time.time()
    logger.info("PIPELINE start: REASON")
    events.start_step(events_list, events.Step.REASON)
    reasoner_output = reasoner_medgemma.reason(case_card, evidence_bundle, events_list)
    if provisional_reasoner_output and not reasoner_output.get("hypotheses_valid"):
        if merge_with_current and prev_reasoner_output and _is_valid_hypotheses(prev_reasoner_output):
            reasoner_output = _merge_reasoner_output(prev_reasoner_output, provisional_reasoner_output)
        else:
            reasoner_output = provisional_reasoner_output
    reasoner_output = _sanitize_reasoner_output(reasoner_output)
    events.end_step(events_list, events.Step.REASON)
    step_times["REASON"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: REASON")

    t_step_start = time.time()
    logger.info("PIPELINE start: GUARDRAILS")
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
                idx = int(path_parts[-1])
                if isinstance(obj, list) and 0 <= idx < len(obj):
                    del obj[idx]
                else:
                    logger.info("Skipping guardrail patch; index out of range: %s", patch)
        events.guardrail_patch_applied(events_list, events.Step.GUARDRAILS, before, reasoner_output)
    events.end_step(events_list, events.Step.GUARDRAILS)
    step_times["GUARDRAILS"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: GUARDRAILS")

    t_step_start = time.time()
    logger.info("PIPELINE start: CASE_IMPRESSION")
    case_impression = generate_case_impression(case_card, reasoner_output, guardrail_report, events_list)
    step_times["CASE_IMPRESSION"] = round(time.time() - t_step_start, 3)
    logger.info("PIPELINE done: CASE_IMPRESSION")
    events.final_ready(events_list)
    model_calls = [e for e in events_list if e.type == "MODEL_CALLED"]
    agent_decisions = [e for e in events_list if e.type == "AGENT_DECISION"]
    # Per-agent REASON timings (ms) for optimization tuning
    reason_model_events = [
        e for e in events_list
        if e.type == "MODEL_CALLED" and getattr(e.step, "value", e.step) == "REASON"
    ]
    reason_agents_ms = {}
    for e in reason_model_events:
        agent_type = (e.payload or {}).get("agent_type", "unknown")
        ms = (e.payload or {}).get("response_time_ms", 0) or 0
        reason_agents_ms[agent_type] = reason_agents_ms.get(agent_type, 0) + ms
    if reason_agents_ms:
        step_times["REASON_agents_ms"] = reason_agents_ms
    return {
        "normalized_labs": normalized_labs,
        "case_card": case_card,
        "evidence_bundle": evidence_bundle,
        "reasoner_output": reasoner_output,
        "guardrail_report": guardrail_report,
        "case_impression": case_impression,
        "suggested_kg_additions": suggested_kg_additions,
        "unlinked_markers": unlinked_markers,
        "unmappable_inputs": unmappable_inputs,
        "events": events_list,
        "timings": step_times,
        "model_usage": {
            "model_calls": len(model_calls),
            "agent_decisions": len(agent_decisions),
            "model_mode": not model_manager.lite_mode,
        },
    }


def _serialize_event(e):
    """Convert Event to dict for JSON (Pydantic v1/v2 compatible). Ensure step and type are strings for frontend."""
    out = e.model_dump() if hasattr(e, "model_dump") else e.dict()
    if isinstance(out, dict):
        if out.get("step") is None or not isinstance(out.get("step"), str):
            out["step"] = getattr(getattr(e, "step", None), "value", None) or "UNKNOWN"
        if out.get("type") is None or not isinstance(out.get("type"), str):
            out["type"] = getattr(getattr(e, "type", None), "value", None) or "UNKNOWN"
    return out


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


def _normalize_hypothesis_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def _hypothesis_key(hypo: dict) -> str:
    return hypo.get("id") or _normalize_hypothesis_name(hypo.get("name"))


def _evidence_signature(items):
    sig = []
    for item in items or []:
        sig.append((
            item.get("marker"),
            item.get("status"),
            item.get("edge_id"),
        ))
    return set(sig)


def _hypothesis_changed(prev: dict, new: dict, confidence_threshold: float = 0.05) -> bool:
    prev_conf = float(prev.get("confidence", 0))
    new_conf = float(new.get("confidence", 0))
    if abs(new_conf - prev_conf) >= confidence_threshold:
        return True
    if _evidence_signature(prev.get("evidence")) != _evidence_signature(new.get("evidence")):
        return True
    if _evidence_signature(prev.get("counter_evidence")) != _evidence_signature(new.get("counter_evidence")):
        return True
    prev_tests = prev.get("next_tests") or []
    new_tests = new.get("next_tests") or []
    if prev_tests != new_tests:
        return True
    return False


def _is_valid_hypotheses(output: Optional[dict]) -> bool:
    if not output:
        return False
    if "hypotheses_valid" in output:
        return bool(output.get("hypotheses_valid"))
    return bool(output.get("hypotheses"))


def _merge_reasoner_output(prev: Optional[dict], new: Optional[dict]) -> dict:
    """Merge hypotheses; keep prior if unchanged or if new is invalid."""
    if not prev:
        return new or {}
    if not new or not _is_valid_hypotheses(new):
        return deepcopy(prev)

    prev_hypotheses = prev.get("hypotheses") or []
    new_hypotheses = new.get("hypotheses") or []
    prev_map = { _hypothesis_key(h): h for h in prev_hypotheses if _hypothesis_key(h) }
    seen_keys = set()
    merged = []
    updated_any = False

    for hypo in new_hypotheses:
        key = _hypothesis_key(hypo)
        if key and key in prev_map:
            prev_h = prev_map[key]
            if _hypothesis_changed(prev_h, hypo):
                merged_item = deepcopy(hypo)
                merged_item["merge_updated"] = True
                merged.append(merged_item)
                updated_any = True
            else:
                merged_item = deepcopy(prev_h)
                merged_item["merge_updated"] = False
                merged.append(merged_item)
            seen_keys.add(key)
        else:
            merged_item = deepcopy(hypo)
            merged_item["merge_updated"] = True
            merged.append(merged_item)
            updated_any = True
            if key:
                seen_keys.add(key)

    # Keep any previous hypotheses not present in new output
    for prev_h in prev_hypotheses:
        key = _hypothesis_key(prev_h)
        if key and key in seen_keys:
            continue
        merged_item = deepcopy(prev_h)
        merged_item["merge_updated"] = False
        merged.append(merged_item)

    merged_output = deepcopy(new)
    merged_output["hypotheses"] = merged

    # If nothing changed, keep prior patient_actions/red_flags/novel outputs
    if not updated_any:
        for field in ("patient_actions", "red_flags", "novel_insights", "novel_actions", "provenance"):
            if field in prev:
                merged_output[field] = deepcopy(prev.get(field))

    return merged_output


def _sse_payload(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _sanitize_reasoner_output(output: Optional[dict]) -> dict:
    """Remove null/malformed entries to keep UI stable."""
    if not output:
        return {}
    sanitized = deepcopy(output)
    hypotheses = sanitized.get("hypotheses") or []
    for h in hypotheses:
        next_tests = []
        for t in h.get("next_tests") or []:
            if isinstance(t, str) and t.strip():
                next_tests.append({"test_id": t.strip(), "label": t.strip()})
            elif isinstance(t, dict) and (t.get("test_id") or t.get("label")):
                next_tests.append({"test_id": t.get("test_id") or "", "label": t.get("label") or ""})
        h["next_tests"] = next_tests
    sanitized["hypotheses"] = hypotheses
    actions = []
    for a in sanitized.get("patient_actions") or []:
        if isinstance(a, dict):
            task = a.get("task")
            if task is not None and str(task).strip():
                actions.append(a)
    sanitized["patient_actions"] = actions
    return sanitized


def _stream_pipeline(case: dict, case_id: str, merge_with_current: bool = False):
    q: "queue.Queue[Optional[dict]]" = queue.Queue()

    def emit_event_item(event):
        q.put({
            "type": "events",
            "events": [_serialize_event(event)]
        })

    def emit_payload(payload):
        q.put(payload)

    events_list = EventList(emit_event_item)

    def runner():
        global current_output
        global current_case
        try:
            prev_ro = (current_output or {}).get("reasoner_output") or (_load_current_output() or {}).get("reasoner_output")
            result = _run_pipeline(case, events_list, emit_callback=emit_payload, merge_with_current=merge_with_current, prev_reasoner_output=prev_ro)
            if merge_with_current:
                if current_output is None:
                    current_output = _load_current_output()
                prev_output = (current_output or {}).get("reasoner_output")
                merged_reasoner = _merge_reasoner_output(prev_output, result.get("reasoner_output"))
                result["reasoner_output"] = _sanitize_reasoner_output(merged_reasoner)
            else:
                result["reasoner_output"] = _sanitize_reasoner_output(result.get("reasoner_output"))
            result["case_id"] = case_id
            result["output_path"] = _write_pipeline_output(case, result)
            current_case = deepcopy(case)
            result["current_case_id"] = case_id
            current_output_payload = deepcopy(result.get("reasoner_output") or {})
            current_output = {
                "case_id": case_id,
                "reasoner_output": current_output_payload
            }
            _write_current_output(case_id, current_output_payload)
            result["events"] = [_serialize_event(e) for e in events_list]
            q.put({"type": "final", "payload": result})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
        finally:
            q.put(None)

    import threading
    threading.Thread(target=runner, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            yield _sse_payload(item)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/run")
async def run_pipeline(request: Request, mode: str = "lite"):
    logger.info("ENTER /run")
    try:
        payload = await request.json()
    except Exception as e:
        logger.exception("POST /run failed to parse JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    try:
        body = RunRequest(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Missing or invalid case_id") from e

    case_id = body.case_id
    logger.info("POST /run received, case_id=%s, processing...", case_id)
    case = cases.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
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
        result = _run_pipeline(case, events_list)
        result["reasoner_output"] = _sanitize_reasoner_output(result.get("reasoner_output"))
        result["case_id"] = case_id
        result["output_path"] = _write_pipeline_output(case, result)
        global current_case
        current_case = deepcopy(case)
        result["current_case_id"] = case_id
        global current_output
        current_output = {
            "case_id": case_id,
            "reasoner_output": deepcopy(result.get("reasoner_output") or {})
        }
        _write_current_output(case_id, current_output["reasoner_output"])
        return result
    except Exception as e:
        logging.exception("Pipeline failed for /run")
        raise HTTPException(
            status_code=500,
            detail="Pipeline failed. Check server logs.",
        ) from e


@app.post("/run/stream")
async def run_pipeline_stream(request: Request, mode: str = "lite"):
    logger.info("ENTER /run/stream")
    try:
        payload = await request.json()
    except Exception as e:
        logger.exception("POST /run/stream failed to parse JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    try:
        body = RunRequest(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Missing or invalid case_id") from e

    case_id = body.case_id
    logger.info("POST /run/stream received, case_id=%s, processing...", case_id)
    case = cases.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if os.getenv("MODE", "lite").lower() == "model":
        try:
            model_manager.wait_for_model(timeout=300.0)
        except TimeoutError as e:
            raise HTTPException(
                status_code=503,
                detail="Model did not finish loading. Please try again or check server logs.",
            ) from e

    return _stream_pipeline(case, case_id, merge_with_current=False)


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

    try:
        result = _run_pipeline(case, events_list)
        result["reasoner_output"] = _sanitize_reasoner_output(result.get("reasoner_output"))
        global current_output
        if body.merge_with_current:
            if current_output is None:
                current_output = _load_current_output()
            prev_output = (current_output or {}).get("reasoner_output")
            merged_reasoner = _merge_reasoner_output(prev_output, result.get("reasoner_output"))
            result["reasoner_output"] = _sanitize_reasoner_output(merged_reasoner)
        result["case_id"] = case["case_id"]
        result["output_path"] = _write_pipeline_output(case, result)
        current_case = deepcopy(case)
        result["current_case_id"] = case["case_id"]
        current_output = {
            "case_id": case["case_id"],
            "reasoner_output": deepcopy(result.get("reasoner_output") or {})
        }
        _write_current_output(case["case_id"], current_output["reasoner_output"])
        return result
    except Exception as e:
        logging.exception("Pipeline failed for /analyze")
        raise HTTPException(
            status_code=500,
            detail="Pipeline failed. Check server logs.",
        ) from e


@app.post("/analyze/stream")
def analyze_from_text_stream(body: AnalyzeRequest):
    """Parse free text into a case, run pipeline, return SSE stream."""
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

    return _stream_pipeline(case, case["case_id"], merge_with_current=body.merge_with_current)

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
    global current_output
    current_output = None
    try:
        os.remove(_current_output_path())
    except OSError:
        pass
    return {"ok": True}


@app.get("/health")
def health():
    return model_manager.get_health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)