import json
import os
import random
from datetime import datetime

# Set seed for deterministic generation
random.seed(42)

# Cases directory
CASES_DIR = 'cases'
os.makedirs(CASES_DIR, exist_ok=True)

# Scenarios
SCENARIOS = [
    {
        "id": "iron_deficiency_anemia",
        "patient": {"age": 35, "sex": "F", "context": {"vegan": True, "fatigue": True}},
        "labs": [
            {"marker": "Ferritin", "value": 12, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"marker": "Iron", "value": 30, "unit": "µg/dL", "ref_low": 50, "ref_high": 170},
            {"marker": "TSAT", "value": 15, "unit": "%", "ref_low": 20, "ref_high": 50},
            {"marker": "Hb", "value": 10.5, "unit": "g/dL", "ref_low": 12, "ref_high": 16},
            {"marker": "MCV", "value": 75, "unit": "fL", "ref_low": 80, "ref_high": 100},
            {"marker": "RDW", "value": 16, "unit": "%", "ref_low": 11.5, "ref_high": 14.5},
            {"marker": "hsCRP", "value": 1.2, "unit": "mg/L", "ref_low": 0, "ref_high": 3},
        ]
    },
    {
        "id": "anemia_of_inflammation_gotcha",
        "patient": {"age": 39, "sex": "F", "context": {"vegan": True, "fatigue": True}},
        "labs": [
            {"marker": "Ferritin", "value": 220, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"marker": "hsCRP", "value": 9.2, "unit": "mg/L", "ref_low": 0, "ref_high": 3},
            {"marker": "Iron", "value": 35, "unit": "µg/dL", "ref_low": 50, "ref_high": 170},
            {"marker": "TSAT", "value": 12, "unit": "%", "ref_low": 20, "ref_high": 50},
            {"marker": "Hb", "value": 11.2, "unit": "g/dL", "ref_low": 12, "ref_high": 16},
            {"marker": "MCV", "value": 82, "unit": "fL", "ref_low": 80, "ref_high": 100},
            {"marker": "RDW", "value": 13.5, "unit": "%", "ref_low": 11.5, "ref_high": 14.5},
        ]
    },
    {
        "id": "subclinical_hypothyroid_dyslipidemia",
        "patient": {"age": 45, "sex": "F", "context": {"weight_gain": True, "cold_intolerance": True}},
        "labs": [
            {"marker": "TSH", "value": 6.5, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.0},
            {"marker": "FT4", "value": 1.1, "unit": "ng/dL", "ref_low": 0.8, "ref_high": 1.8},
            {"marker": "FT3", "value": 3.0, "unit": "pg/mL", "ref_low": 2.3, "ref_high": 4.2},
            {"marker": "Total Cholesterol", "value": 250, "unit": "mg/dL", "ref_low": 0, "ref_high": 200},
            {"marker": "LDL", "value": 160, "unit": "mg/dL", "ref_low": 0, "ref_high": 100},
            {"marker": "HDL", "value": 35, "unit": "mg/dL", "ref_low": 40, "ref_high": 100},
            {"marker": "Triglycerides", "value": 180, "unit": "mg/dL", "ref_low": 0, "ref_high": 150},
        ]
    },
    {
        "id": "primary_hypothyroid",
        "patient": {"age": 50, "sex": "F", "context": {"weight_gain": True, "fatigue": True}},
        "labs": [
            {"marker": "TSH", "value": 15, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.0},
            {"marker": "FT4", "value": 0.5, "unit": "ng/dL", "ref_low": 0.8, "ref_high": 1.8},
            {"marker": "FT3", "value": 2.0, "unit": "pg/mL", "ref_low": 2.3, "ref_high": 4.2},
        ]
    },
    {
        "id": "healthy_control",
        "patient": {"age": 30, "sex": "M", "context": {}},
        "labs": [
            {"marker": "Ferritin", "value": 80, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"marker": "Iron", "value": 100, "unit": "µg/dL", "ref_low": 50, "ref_high": 170},
            {"marker": "TSAT", "value": 30, "unit": "%", "ref_low": 20, "ref_high": 50},
            {"marker": "Hb", "value": 14, "unit": "g/dL", "ref_low": 13, "ref_high": 17},
            {"marker": "MCV", "value": 90, "unit": "fL", "ref_low": 80, "ref_high": 100},
            {"marker": "RDW", "value": 13, "unit": "%", "ref_low": 11.5, "ref_high": 14.5},
            {"marker": "hsCRP", "value": 1.0, "unit": "mg/L", "ref_low": 0, "ref_high": 3},
            {"marker": "TSH", "value": 2.0, "unit": "mIU/L", "ref_low": 0.4, "ref_high": 4.0},
            {"marker": "FT4", "value": 1.2, "unit": "ng/dL", "ref_low": 0.8, "ref_high": 1.8},
        ]
    },
    {
        "id": "unit_mismatch_missing_units",
        "patient": {"age": 40, "sex": "F", "context": {"fatigue": True}},
        "labs": [
            {"marker": "Ferritin", "value": 12, "unit": "ug/L", "ref_low": 15, "ref_high": 150},  # wrong unit
            {"marker": "Iron", "value": 30, "unit": "", "ref_low": 50, "ref_high": 170},  # missing unit
            {"marker": "TSAT", "value": 15, "unit": "%", "ref_low": 20, "ref_high": 50},
        ]
    },
    {
        "id": "borderline_values_trend",
        "patient": {"age": 28, "sex": "F", "context": {"fatigue": True}},
        "labs": [
            {"marker": "Ferritin", "value": 16, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"marker": "Iron", "value": 48, "unit": "µg/dL", "ref_low": 50, "ref_high": 170},
            {"marker": "TSAT", "value": 19, "unit": "µg/dL", "ref_low": 20, "ref_high": 50},  # wrong unit for TSAT
            {"marker": "Hb", "value": 11.8, "unit": "g/dL", "ref_low": 12, "ref_high": 16},
        ]
    },
    {
        "id": "conflicting_markers_insufficient_data",
        "patient": {"age": 55, "sex": "M", "context": {}},
        "labs": [
            {"marker": "Ferritin", "value": 200, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
            {"marker": "Iron", "value": 150, "unit": "µg/dL", "ref_low": 50, "ref_high": 170},
            {"marker": "TSAT", "value": 45, "unit": "%", "ref_low": 20, "ref_high": 50},
        ]
    }
]

def generate_case(scenario, case_num):
    case_id = f"case_{case_num:02d}_{scenario['id']}"
    timestamp = "2026-01-10"
    case = {
        "case_id": case_id,
        "patient": scenario["patient"],
        "labs": [
            {**lab, "timestamp": timestamp} for lab in scenario["labs"]
        ],
        "meta": {"scenario": scenario["id"]}
    }
    return case

def main():
    cases = []
    for i, scenario in enumerate(SCENARIOS, 1):
        case = generate_case(scenario, i)
        cases.append(case)
        # Add some extra labs to make 80-120, but for simplicity, keep as is for now
        # In real, add more normal labs

    # For each case, add filler labs to reach ~100
    all_markers = [
        "Ferritin", "Iron", "TSAT", "Hb", "MCV", "RDW", "hsCRP", "TSH", "FT4", "FT3",
        "Total Cholesterol", "LDL", "HDL", "Triglycerides", "Vitamin B12", "Folate",
        "Reticulocyte Count", "WBC", "Platelets", "Glucose", "Creatinine", "ALT", "AST"
    ]
    normal_ranges = {
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
        "Vitamin B12": (200, 900, "pg/mL"),
        "Folate": (2, 20, "ng/mL"),
        "Reticulocyte Count": (0.5, 2.5, "%"),
        "WBC": (4, 11, "K/µL"),
        "Platelets": (150, 450, "K/µL"),
        "Glucose": (70, 100, "mg/dL"),
        "Creatinine": (0.7, 1.2, "mg/dL"),
        "ALT": (7, 56, "U/L"),
        "AST": (10, 40, "U/L")
    }

    for case in cases:
        existing_markers = {lab["marker"] for lab in case["labs"]}
        num_to_add = random.randint(80 - len(case["labs"]), 120 - len(case["labs"]))
        for _ in range(num_to_add):
            marker = random.choice(all_markers)
            if marker in existing_markers:
                continue
            ref_low, ref_high, unit = normal_ranges[marker]
            value = random.uniform(ref_low * 0.8, ref_high * 1.2)
            lab = {
                "marker": marker,
                "value": round(value, 1),
                "unit": unit,
                "ref_low": ref_low,
                "ref_high": ref_high,
                "timestamp": "2026-01-10"
            }
            case["labs"].append(lab)
            existing_markers.add(marker)

    # Write to files
    for case in cases:
        filename = f"{case['case_id']}.json"
        filepath = os.path.join(CASES_DIR, filename)
        with open(filepath, 'w') as f:
            json.dump(case, f, indent=2)

if __name__ == "__main__":
    main()