from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from core import lab_normalizer, context_selector, evidence_builder, reasoner_medgemma, guardrails, events
from core.model_manager import model_manager

class RunRequest(BaseModel):
    case_id: str

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
    return {"message": "Aletheia Demo API", "endpoints": ["/cases", "/health"]}

@app.get("/cases")
def get_cases():
    return [{"id": cid, "summary": f"Case {cid}"} for cid in cases]

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    return cases.get(case_id)

@app.post("/run")
def run_pipeline(body: RunRequest, mode: str = "lite"):
    case_id = body.case_id
    case = cases[case_id]
    events_list = []

    # When MODE=model, block until model is loaded before running pipeline
    if os.getenv("MODE", "lite").lower() == "model":
        try:
            model_manager.wait_for_model(timeout=300.0)
        except TimeoutError as e:
            raise HTTPException(
                status_code=503,
                detail="Model did not finish loading. Please try again or check server logs.",
            ) from e

    # LAB_NORMALIZE
    events.start_step(events_list, events.Step.LAB_NORMALIZE)
    normalized_labs = lab_normalizer.normalize_labs(case['labs'])
    events.end_step(events_list, events.Step.LAB_NORMALIZE)

    # CONTEXT_SELECT
    events.start_step(events_list, events.Step.CONTEXT_SELECT)
    case_card, subgraph = context_selector.select_context(normalized_labs, case['patient']['context'], events_list)
    events.highlight(events_list, events.Step.CONTEXT_SELECT, [n['id'] for n in subgraph['nodes']], [e['id'] for e in subgraph['edges']], "Context subgraph")
    events.end_step(events_list, events.Step.CONTEXT_SELECT)

    # EVIDENCE_SCORE
    events.start_step(events_list, events.Step.EVIDENCE_SCORE)
    evidence_bundle = evidence_builder.build_evidence(case_card, subgraph, normalized_labs, events_list, events)
    events.end_step(events_list, events.Step.EVIDENCE_SCORE)

    # REASON
    events.start_step(events_list, events.Step.REASON)
    reasoner_output = reasoner_medgemma.reason(case_card, evidence_bundle, events_list)
    events.end_step(events_list, events.Step.REASON)

    # GUARDRAILS
    events.start_step(events_list, events.Step.GUARDRAILS)
    guardrail_report = guardrails.check_guardrails(reasoner_output, case_card, normalized_labs, events_list)
    if guardrail_report['status'] == 'FAIL':
        events.guardrail_fail(events_list, events.Step.GUARDRAILS, guardrail_report['failed_rules'])
        before = reasoner_output.copy()
        # Apply patches (simple implementation for removes)
        for patch in guardrail_report['patches']:
            if patch['op'] == 'remove':
                path_parts = patch['path'].strip('/').split('/')
                obj = reasoner_output
                for part in path_parts[:-1]:
                    if part.isdigit():
                        obj = obj[int(part)]
                    else:
                        obj = obj[part]
                index = int(path_parts[-1])
                del obj[index]
        after = reasoner_output
        events.guardrail_patch_applied(events_list, events.Step.GUARDRAILS, before, after)
    events.end_step(events_list, events.Step.GUARDRAILS)

    events.final_ready(events_list)

    # Track model usage statistics
    model_calls = [e for e in events_list if e.type == 'MODEL_CALLED']
    agent_decisions = [e for e in events_list if e.type == 'AGENT_DECISION']
    
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
            "model_mode": not model_manager.lite_mode
        }
    }

@app.get("/health")
def health():
    return model_manager.get_health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)