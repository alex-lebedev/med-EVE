from pydantic import BaseModel
from enum import Enum
import time

class Step(str, Enum):
    LAB_NORMALIZE = "LAB_NORMALIZE"
    CONTEXT_SELECT = "CONTEXT_SELECT"
    EVIDENCE_SCORE = "EVIDENCE_SCORE"
    REASON = "REASON"
    GUARDRAILS = "GUARDRAILS"
    FINAL = "FINAL"

class EventType(str, Enum):
    STEP_START = "STEP_START"
    STEP_END = "STEP_END"
    HIGHLIGHT = "HIGHLIGHT"
    CANDIDATES = "CANDIDATES"
    EVIDENCE_APPLIED = "EVIDENCE_APPLIED"
    SCORE_UPDATE = "SCORE_UPDATE"
    HYPOTHESIS_READY = "HYPOTHESIS_READY"
    GUARDRAIL_FAIL = "GUARDRAIL_FAIL"
    GUARDRAIL_PATCH_APPLIED = "GUARDRAIL_PATCH_APPLIED"
    FINAL_READY = "FINAL_READY"

class Event(BaseModel):
    ts: float
    step: Step
    type: EventType
    payload: dict = {}

def emit_event(events, step, event_type, payload=None):
    event = Event(
        ts=time.time(),
        step=step,
        type=event_type,
        payload=payload or {}
    )
    events.append(event)

# Helper to start/end steps
def start_step(events, step):
    emit_event(events, step, EventType.STEP_START)

def end_step(events, step, timings=None):
    emit_event(events, step, EventType.STEP_END, {"timings": timings})

# Specific events
def highlight(events, step, node_ids, edge_ids, label=""):
    emit_event(events, step, EventType.HIGHLIGHT, {"node_ids": node_ids, "edge_ids": edge_ids, "label": label})

def candidates(events, step, candidates):
    emit_event(events, step, EventType.CANDIDATES, {"candidates": candidates})

def evidence_applied(events, step, evidence_item):
    emit_event(events, step, EventType.EVIDENCE_APPLIED, {"evidence": evidence_item})

def score_update(events, step, scores):
    emit_event(events, step, EventType.SCORE_UPDATE, {"scores": scores})

def hypothesis_ready(events, step, hypothesis):
    emit_event(events, step, EventType.HYPOTHESIS_READY, {"hypothesis": hypothesis})

def guardrail_fail(events, step, failed_rules):
    emit_event(events, step, EventType.GUARDRAIL_FAIL, {"failed_rules": failed_rules})

def guardrail_patch_applied(events, step, before, after):
    emit_event(events, step, EventType.GUARDRAIL_PATCH_APPLIED, {"before": before, "after": after})

def final_ready(events):
    emit_event(events, Step.FINAL, EventType.FINAL_READY)