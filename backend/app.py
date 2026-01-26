from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from .core import lab_normalizer, context_selector, evidence_builder, reasoner_medgemma, guardrails, events
from .core.model_manager import model_manager

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
def run_pipeline(body: dict, mode: str = "lite"):
    case_id = body['case_id']
    case = cases[case_id]
    events_list = []

    # LAB_NORMALIZE
    events.start_step(events_list, events.Step.LAB_NORMALIZE)
    normalized_labs = lab_normalizer.normalize_labs(case['labs'])
    events.end_step(events_list, events.Step.LAB_NORMALIZE)

    # CONTEXT_SELECT
    events.start_step(events_list, events.Step.CONTEXT_SELECT)
    case_card, subgraph = context_selector.select_context(normalized_labs, case['patient']['context'])
    events.highlight(events_list, events.Step.CONTEXT_SELECT, [n['id'] for n in subgraph['nodes']], [e['id'] for e in subgraph['edges']], "Context subgraph")
    events.end_step(events_list, events.Step.CONTEXT_SELECT)

    # EVIDENCE_SCORE
    events.start_step(events_list, events.Step.EVIDENCE_SCORE)
    evidence_bundle = evidence_builder.build_evidence(case_card, subgraph, normalized_labs, events_list, events)
    events.end_step(events_list, events.Step.EVIDENCE_SCORE)

    # REASON
    events.start_step(events_list, events.Step.REASON)
    reasoner_output = reasoner_medgemma.reason(case_card, evidence_bundle)
    events.end_step(events_list, events.Step.REASON)

    # GUARDRAILS
    events.start_step(events_list, events.Step.GUARDRAILS)
    guardrail_report = guardrails.check_guardrails(reasoner_output, case_card, normalized_labs)
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

    return {
        "normalized_labs": normalized_labs,
        "case_card": case_card,
        "evidence_bundle": evidence_bundle,
        "reasoner_output": reasoner_output,
        "guardrail_report": guardrail_report,
        "events": events_list,
        "timings": {}
    }

@app.get("/health")
def health():
    return model_manager.get_health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)