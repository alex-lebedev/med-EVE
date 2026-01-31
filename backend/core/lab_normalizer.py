import yaml
import os

# Load marker synonyms
MARKER_MAP = {
    "Thyrotropin": "TSH",
    "Thyroxine": "T4",  # but we have FT4
    "Triiodothyronine": "T3",
    # Add more if needed
}

# Unit conversions
UNIT_CONVERSIONS = {
    "Ferritin": {
        "ug/L": lambda x: x / 1000,  # to ng/mL
        "ng/mL": lambda x: x,
    },
    "Iron": {
        "umol/L": lambda x: x * 5.585,  # to µg/dL
        "µg/dL": lambda x: x,
    },
    "TSAT": {
        "%": lambda x: x,
    },
    # Add more as needed
}

STANDARD_UNITS = {
    "ANC": "K/µL",
    "Ferritin": "ng/mL",
    "Iron": "µg/dL",
    "TSAT": "%",
    "Hb": "g/dL",
    "MCV": "fL",
    "RDW": "%",
    "hsCRP": "mg/L",
    "TSH": "mIU/L",
    "FT4": "ng/dL",
    "FT3": "pg/mL",
    "Total Cholesterol": "mg/dL",
    "LDL": "mg/dL",
    "HDL": "mg/dL",
    "Triglycerides": "mg/dL",
    # Add more
}

def normalize_marker(marker):
    return MARKER_MAP.get(marker, marker)

def normalize_unit(marker, value, unit):
    if unit == "":
        # Assume standard
        return value, STANDARD_UNITS.get(marker, unit)
    if marker in UNIT_CONVERSIONS and unit in UNIT_CONVERSIONS[marker]:
        converted = UNIT_CONVERSIONS[marker][unit](value)
        return converted, STANDARD_UNITS[marker]
    return value, unit

def get_status(value, ref_low, ref_high):
    if value < ref_low:
        return "LOW"
    elif value > ref_high:
        return "HIGH"
    else:
        return "NORMAL"

def normalize_labs(raw_labs):
    normalized = []
    for lab in raw_labs:
        marker = normalize_marker(lab["marker"])
        value, unit = normalize_unit(marker, lab["value"], lab["unit"])
        ref_low, ref_high = lab["ref_low"], lab["ref_high"]
        from_fallback = lab.get("from_fallback", False)
        if from_fallback or (ref_low == 0 and ref_high == 0):
            status = "REFERENCE_UNKNOWN"
        else:
            status = get_status(value, ref_low, ref_high)
        normalized_lab = {
            "marker": marker,
            "value": round(value, 2),
            "unit": unit or "",
            "ref_low": ref_low,
            "ref_high": ref_high,
            "status": status,
            "timestamp": lab["timestamp"],
            "from_fallback": from_fallback,
        }
        normalized.append(normalized_lab)
    return normalized