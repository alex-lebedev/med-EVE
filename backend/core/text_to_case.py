"""
Rule-based parser: free text -> case dict (patient + labs + symptom_tokens) for the pipeline.
Uses known marker names and default ref ranges; no OpenAI/MedGemma required.
"""
import re
import os
import yaml
from datetime import datetime
from typing import Optional, List

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


_SYMPTOM_TO_PATTERN_CONFIG = None


def _load_symptom_to_pattern() -> dict:
    global _SYMPTOM_TO_PATTERN_CONFIG
    if _SYMPTOM_TO_PATTERN_CONFIG is None:
        path = os.path.join(os.path.dirname(__file__), "symptom_to_pattern.yml")
        if os.path.isfile(path):
            with open(path) as f:
                _SYMPTOM_TO_PATTERN_CONFIG = yaml.safe_load(f) or {}
        else:
            _SYMPTOM_TO_PATTERN_CONFIG = {}
    return _SYMPTOM_TO_PATTERN_CONFIG


def _extract_symptom_tokens(text: str, patient_context: dict) -> List[str]:
    """Extract symptom/free-text tokens for mapping: keywords found in text + config keys present."""
    lower = (text or "").lower()
    tokens = []
    seen = set()
    for keyword, key, _ in CONTEXT_KEYWORDS:
        if keyword in lower and key not in seen:
            tokens.append(key)
            seen.add(key)
    config = _load_symptom_to_pattern()
    for phrase in config:
        if phrase in lower and phrase not in seen:
            tokens.append(phrase)
            seen.add(phrase)
    return tokens


def _parse_number(s: str) -> Optional[float]:
    s = s.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_fallback_name(name: str) -> str:
    """Normalize fallback marker name: strip, collapse spaces to single space."""
    s = " ".join((name or "").split()).strip()
    return s if s else name


# Fallback: match "name + number + optional unit" for unknown markers (not in MARKER_NAMES)
_FALLBACK_LAB_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9\s\-/]*?)\s+([0-9]+\.?[0-9]*)\s*([a-zA-Zµ/%µL\/dL\.\-]*)?",
    re.IGNORECASE,
)


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

    # Fallback: match "name + number + optional unit" for tokens not in MARKER_NAMES
    known_marker_set = {m.lower() for m in MARKER_NAMES}
    known_marker_set.add("anc")  # canonical
    for m in _FALLBACK_LAB_PATTERN.finditer(text):
        name_raw = (m.group(1) or "").strip()
        name_norm = _normalize_fallback_name(name_raw)
        if not name_norm or len(name_norm) < 2:
            continue
        if name_norm.lower() in known_marker_set:
            continue
        if name_norm in seen_markers:
            continue
        value = _parse_number(m.group(2))
        if value is None:
            continue
        unit = (m.group(3) or "").strip() or ""
        seen_markers.add(name_norm)
        labs.append({
            "marker": name_norm,
            "value": value,
            "unit": unit,
            "ref_low": 0,
            "ref_high": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d"),
            "from_fallback": True,
        })

    if not labs:
        raise ValueError(
            "Could not parse any lab values from text. "
            "Try listing labs like: Ferritin 12 ng/mL, Hb 10.5 g/dL, TSH 2.6 mIU/L"
        )

    symptom_tokens = _extract_symptom_tokens(text, patient_context)

    return {
        "patient": {
            "age": None,
            "sex": None,
            "context": patient_context,
        },
        "labs": labs,
        "symptom_tokens": symptom_tokens,
    }
