from pydantic import BaseModel
from typing import List, Optional

class Evidence(BaseModel):
    marker: str
    status: str
    edge_id: Optional[str] = None

class Hypothesis(BaseModel):
    name: str
    confidence: float
    evidence: List[Evidence]
    counter_evidence: List[Evidence]
    next_tests: List[str]
    notes: str
    merge_updated: Optional[bool] = None

class PatientAction(BaseModel):
    task: str
    why: str
    risk: str

class NovelInsight(BaseModel):
    insight: str
    rationale: str
    outside_kg: bool = True

class NovelAction(BaseModel):
    task: str
    why: str
    risk: str
    outside_kg: bool = True

class Provenance(BaseModel):
    kg_grounded: bool
    notes: Optional[str] = None

class ReasonerOutput(BaseModel):
    hypotheses: List[Hypothesis]
    patient_actions: List[PatientAction]
    red_flags: List[str]
    hypotheses_valid: Optional[bool] = None
    provisional: Optional[bool] = None
    novel_insights: Optional[List[NovelInsight]] = []
    novel_actions: Optional[List[NovelAction]] = []
    provenance: Optional[Provenance] = None

class CaseCard(BaseModel):
    abnormal_markers: List[str]
    neighbor_markers: List[str]
    signals: List[str]
    missing_key_tests: List[str]
    patient_context: dict

class EvidenceItem(BaseModel):
    claim: str
    markers: List[str]
    edge_ids: List[str]

class EvidenceBundle(BaseModel):
    subgraph: dict
    supports: List[EvidenceItem]
    contradictions: List[EvidenceItem]
    allowed_claims: List[str]
class GuardrailReport(BaseModel):
    status: str
    failed_rules: List[dict]
    auto_fixes: List[dict]
    explanations: Optional[List[dict]] = []
