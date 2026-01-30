"""
Rule-based parser: free text -> case dict (patient + labs) for the pipeline.
Uses known marker names and default ref ranges; no OpenAI/MedGemma required.
"""
import re
from datetime import datetime
from typing import Optional

# Marker names we recognize (case-insensitive match); order longer names first for regex
MARKER_NAMES = [
    "Absolute neutrophil count", "Total Cholesterol", "Reticulocyte Count", "Vitamin B12",
    "Triglycerides", "hsCRP", "Ferritin", "Folate", "Creatinine",
    "Platelets", "Glucose", "Iron", "TSAT", "Hb", "MCV", "RDW",
    "TSH", "FT4", "FT3", "ALT", "AST", "WBC", "LDL", "HDL",
    "ANC",
]

# Default ref ranges and units per marker (ref_low, ref_high, unit)
DEFAULT_REFS = {
    "Ferritin": (15, 150, "ng/mL"),
    "Iron": (50, 170, "µg/dL"),
    "TSAT": (20, 50, "%"),
    "Hb": (12, 16, "g/dL"),
    "MCV": (80, 100, "fL"),
    "RDW": (11.5, 14.5, "%"),
    "hsCRP": (0, 3, "mg/L"),
    "TSH": (0.4, 4.0, "mIU/L"),
    "FT4": (0.8, 1.8, "ng/dL"),
    "FT3": (2.3, 4.2, "pg/mL"),
    "Total Cholesterol": (0, 200, "mg/dL"),
    "LDL": (0, 100, "mg/dL"),
    "HDL": (40, 100, "mg/dL"),
    "Triglycerides": (0, 150, "mg/dL"),
    "ALT": (7, 56, "U/L"),
    "AST": (10, 40, "U/L"),
    "WBC": (4, 11, "K/µL"),
    "Glucose": (70, 100, "mg/dL"),
    "Platelets": (150, 450, "K/µL"),
    "Creatinine": (0.7, 1.2, "mg/dL"),
    "Folate": (2, 20, "ng/mL"),
    "Vitamin B12": (200, 900, "pg/mL"),
    "Reticulocyte Count": (0.5, 2.5, "%"),
    "ANC": (1.5, 8, "K/µL"),
    "Absolute neutrophil count": (1.5, 8, "K/µL"),
}

# Patient context keywords -> context dict keys
CONTEXT_KEYWORDS = [
    ("vegan", "vegan", True),
    ("vegetarian", "vegan", True),
    ("fatigue", "fatigue", True),
    ("tired", "fatigue", True),
    ("elderly", "elderly", True),
    ("chronic disease", "chronic_disease", True),
    ("inflammatory", "inflammatory", True),
]


def _extract_context(text: str) -> dict:
    out = {}
    lower = text.lower()
    for keyword, key, value in CONTEXT_KEYWORDS:
        if keyword in lower:
            out[key] = value
    return out


def _parse_number(s: str) -> Optional[float]:
    s = s.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def text_to_case(text: str) -> dict:
    """
    Parse free text into a case dict: { patient: { context }, labs: [ ... ] }.
    Raises ValueError with a message if parsing fails or no labs found.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("No text provided.")

    patient_context = _extract_context(text)
    labs = []
    # Build regex: match marker name then optional number and optional unit
    # Try each known marker (longest first)
    seen_markers = set()
    for marker in sorted(MARKER_NAMES, key=len, reverse=True):
        # Pattern: marker name, then optional spaces, then number (with optional decimal)
        # and optional unit (letters, /, µ, etc.)
        escaped = re.escape(marker)
        # Allow "Ferritin 12" or "Ferritin: 12 ng/mL" or "Ferritin 12 ng/mL"
        pattern = rf"\b{escaped}\s*[:\s]\s*([0-9]+\.?[0-9]*)\s*([a-zA-Zµ/%µL\/dL\.\-]*)?"
        for m in re.finditer(pattern, text, re.IGNORECASE):
            value = _parse_number(m.group(1))
            if value is None:
                continue
            unit = (m.group(2) or "").strip()
            ref_low, ref_high, default_unit = DEFAULT_REFS.get(
                marker, (0, 1000, "")
            )
            if not unit:
                unit = default_unit
            # Normalize marker name (use canonical; map "Absolute neutrophil count" -> "ANC")
            canonical = "ANC" if marker == "Absolute neutrophil count" else marker
            if canonical in seen_markers:
                continue
            seen_markers.add(canonical)
            labs.append({
                "marker": canonical,
                "value": value,
                "unit": unit or default_unit,
                "ref_low": ref_low,
                "ref_high": ref_high,
                "timestamp": datetime.now().strftime("%Y-%m-%d"),
            })

    if not labs:
        raise ValueError(
            "Could not parse any lab values from text. "
            "Try listing labs like: Ferritin 12 ng/mL, Hb 10.5 g/dL, TSH 2.6 mIU/L"
        )

    return {
        "patient": {
            "age": None,
            "sex": None,
            "context": patient_context,
        },
        "labs": labs,
    }
