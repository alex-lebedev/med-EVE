import argparse
import csv
import json
import os
import random
import statistics
import time
from copy import deepcopy
from datetime import datetime

# Evals should own model-loading flow and avoid app-level preload thread.
os.environ.setdefault("DISABLE_MODEL_PRELOAD", "1")

from app import _run_pipeline, load_cases
from core.model_manager import model_manager


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GOLDEN_MANIFEST = os.path.join(ROOT_DIR, "data_synth", "golden_cases", "golden_manifest.json")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "evals", "results")


class _TruthyEventList(list):
    """Ensure optional event emission branches guarded by `if events_list:` execute."""

    def __bool__(self):
        return True


def _seed_from_env(default: int = 42) -> int:
    raw = os.getenv("REPRODUCIBILITY_SEED", str(default)).strip().lower()
    if raw in ("", "off", "none", "false"):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _validate_schema(result: dict) -> bool:
    required = (
        "normalized_labs",
        "case_card",
        "evidence_bundle",
        "reasoner_output",
        "critic_result",
        "guardrail_report",
        "case_impression",
        "events",
        "timings",
        "model_usage",
    )
    if not all(k in result for k in required):
        return False
    if not isinstance(result.get("reasoner_output"), dict):
        return False
    if not isinstance(result.get("guardrail_report"), dict):
        return False
    if not isinstance(result.get("events"), list):
        return False
    return True


def _scenario_expectations(scenario: str) -> dict:
    mapping = {
        "iron_deficiency_anemia": {"target_patterns": ["p_iron_def"], "expect_guardrail_fail": False},
        "anemia_of_inflammation_gotcha": {"target_patterns": ["p_inflam_iron_seq"], "expect_guardrail_fail": False},
        "subclinical_hypothyroid_dyslipidemia": {"target_patterns": ["p_hypothyroid"], "expect_guardrail_fail": False},
        "primary_hypothyroid": {"target_patterns": ["p_hypothyroid"], "expect_guardrail_fail": False},
        "healthy_control": {"target_patterns": [], "expect_guardrail_fail": False},
        "unit_mismatch_missing_units": {"target_patterns": ["p_iron_def", "p_inflam_iron_seq"], "expect_guardrail_fail": False},
        "borderline_values_trend": {"target_patterns": ["p_iron_def", "p_hypothyroid"], "expect_guardrail_fail": False},
        "conflicting_markers_insufficient_data": {"target_patterns": ["p_iron_def", "p_inflam_iron_seq"], "expect_guardrail_fail": False},
    }
    return mapping.get(scenario, {"target_patterns": [], "expect_guardrail_fail": False})


def _materialize_legacy_cases():
    cases = load_cases()
    prepared = []
    for cid, case in cases.items():
        scenario = ((case.get("meta") or {}).get("scenario") or "").strip()
        prepared.append({
            "eval_case_id": cid,
            "scenario": scenario,
            "case": case,
            "expectations": _scenario_expectations(scenario),
        })
    return prepared


def _jitter_case(case: dict, jitter_pct: float, seed: int, nonce: str) -> dict:
    mutated = deepcopy(case)
    rng = random.Random(f"{seed}:{nonce}")
    if jitter_pct <= 0:
        return mutated
    for lab in mutated.get("labs", []):
        val = lab.get("value")
        if isinstance(val, (int, float)):
            delta = rng.uniform(-jitter_pct, jitter_pct)
            lab["value"] = round(float(val) * (1.0 + delta), 4)
    return mutated


def _materialize_golden_cases(manifest_path: str, seed: int):
    cases = load_cases()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    prepared = []
    for profile in manifest.get("profiles", []):
        source_case_id = profile["source_case_id"]
        source_case = cases[source_case_id]
        count = int(profile.get("count", 1))
        jitter_values = profile.get("jitter_sequence_pct") or [0.0]
        expectations = profile.get("expectations", {})
        scenario = ((source_case.get("meta") or {}).get("scenario") or "")
        for idx in range(count):
            jitter = float(jitter_values[idx % len(jitter_values)])
            eval_case_id = f"{source_case_id}__v{idx + 1:02d}"
            case = _jitter_case(source_case, jitter, seed, eval_case_id)
            case["case_id"] = eval_case_id
            prepared.append({
                "eval_case_id": eval_case_id,
                "scenario": scenario,
                "case": case,
                "expectations": expectations,
                "jitter_pct": jitter,
                "source_case_id": source_case_id,
            })
    return prepared


_seen_source_cases = set()


def _evaluate_case(item: dict):
    started = time.perf_counter()
    result = _run_pipeline(item["case"], _TruthyEventList())
    latency_s = time.perf_counter() - started

    scenario = item.get("scenario", "")
    expectations = item.get("expectations", {})
    target_patterns = expectations.get("target_patterns", [])
    expect_guardrail_fail = bool(expectations.get("expect_guardrail_fail", False))

    signals = set((result.get("case_card") or {}).get("signals", []))
    guardrail_status = (result.get("guardrail_report") or {}).get("status", "UNKNOWN")
    patches = (result.get("guardrail_report") or {}).get("patches", [])
    critic_ops = (result.get("critic_result") or {}).get("ops", [])
    hyp_count = len((result.get("reasoner_output") or {}).get("hypotheses", []))
    action_count = len((result.get("reasoner_output") or {}).get("patient_actions", []))
    events_count = len(result.get("events", []))
    model_calls = int((result.get("model_usage") or {}).get("model_calls", 0))
    agent_decisions = int((result.get("model_usage") or {}).get("agent_decisions", 0))

    source_id = item.get("source_case_id", item["eval_case_id"])
    first_invocation = source_id not in _seen_source_cases
    _seen_source_cases.add(source_id)

    diagnostic_hit = None
    if target_patterns:
        diagnostic_hit = any(p in signals for p in target_patterns)

    guardrail_triggered = guardrail_status == "FAIL"
    guardrail_catch = guardrail_triggered if expect_guardrail_fail else None
    guardrail_false_positive = guardrail_triggered if not expect_guardrail_fail else None
    schema_valid = _validate_schema(result)

    return {
        "case_id": item["eval_case_id"],
        "source_case_id": source_id,
        "scenario": scenario,
        "diagnostic_hit": diagnostic_hit,
        "target_patterns": ",".join(target_patterns),
        "critic_intervened": bool(critic_ops),
        "critic_ops_count": len(critic_ops),
        "guardrail_status": guardrail_status,
        "guardrail_expected_fail": expect_guardrail_fail,
        "guardrail_catch": guardrail_catch,
        "guardrail_false_positive": guardrail_false_positive,
        "patches_count": len(patches),
        "schema_valid": schema_valid,
        "latency_s": round(latency_s, 4),
        "first_invocation": first_invocation,
        "hypotheses_count": hyp_count,
        "patient_actions_count": action_count,
        "events_count": events_count,
        "model_calls": model_calls,
        "agent_decisions": agent_decisions,
    }


def _rate(values):
    vals = [v for v in values if isinstance(v, bool)]
    if not vals:
        return None
    return sum(1 for v in vals if v) / len(vals)


def _aggregate(records):
    latencies = [r["latency_s"] for r in records]
    sorted_lat = sorted(latencies)
    p95_idx = int(round(0.95 * (len(sorted_lat) - 1))) if sorted_lat else 0

    first_inv = [r for r in records if r.get("first_invocation")]
    first_lat = [r["latency_s"] for r in first_inv]
    sorted_first = sorted(first_lat)

    return {
        "cases_total": len(records),
        "diagnostic_hit_rate": _rate([r["diagnostic_hit"] for r in records]),
        "critic_intervention_rate": _rate([r["critic_intervened"] for r in records]),
        "guardrail_catch_rate": _rate([r["guardrail_catch"] for r in records]),
        "guardrail_false_positive_rate": _rate([r["guardrail_false_positive"] for r in records]),
        "schema_valid_rate": _rate([r["schema_valid"] for r in records]),
        "avg_latency_s": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "p95_latency_s": round(sorted_lat[p95_idx], 4) if sorted_lat else 0.0,
        "first_invocation_count": len(first_inv),
        "first_invocation_avg_latency_s": round(statistics.mean(first_lat), 4) if first_lat else 0.0,
        "first_invocation_p95_latency_s": round(sorted_first[int(round(0.95 * max(0, len(sorted_first) - 1)))], 4) if sorted_first else 0.0,
        "avg_hypotheses_count": round(statistics.mean([r["hypotheses_count"] for r in records]), 3) if records else 0.0,
        "avg_events_count": round(statistics.mean([r["events_count"] for r in records]), 3) if records else 0.0,
        "avg_model_calls": round(statistics.mean([r["model_calls"] for r in records]), 3) if records else 0.0,
        "avg_agent_decisions": round(statistics.mean([r["agent_decisions"] for r in records]), 3) if records else 0.0,
    }


def _fmt_pct(value):
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _write_artifacts(records, summary, output_dir, dataset_name):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(output_dir, f"{dataset_name}_{ts}")

    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cases": records}, f, indent=2)

    csv_fields = list(records[0].keys()) if records else []
    with open(f"{base}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(records)

    mode_label = "model" if not model_manager.lite_mode else "lite"
    lines = [
        "# Safety Verification Summary",
        "",
        "> This report verifies internal consistency and safety architecture.",
        "> Signal detection measures deterministic KG correctness (not model quality).",
        "> MedGemma adds value through confidence re-calibration, reasoning prose,",
        "> critic safety review, and contextual case impressions.",
        "",
        f"- Mode: **{mode_label}**",
        f"- Cases: {summary['cases_total']}",
        f"- Signal detection rate: {_fmt_pct(summary['diagnostic_hit_rate'])}",
        f"- Critic intervention rate: {_fmt_pct(summary['critic_intervention_rate'])}",
        f"- Guardrail catch rate: {_fmt_pct(summary['guardrail_catch_rate'])}",
        f"- Guardrail false-positive rate: {_fmt_pct(summary['guardrail_false_positive_rate'])}",
        f"- Schema valid rate: {_fmt_pct(summary['schema_valid_rate'])}",
        f"- Avg model calls per case: {summary['avg_model_calls']}",
        f"- Avg agent decisions per case: {summary['avg_agent_decisions']}",
        "",
        "### Latency",
        "",
        f"- Avg latency (all cases): {summary['avg_latency_s']}s",
        f"- P95 latency (all cases): {summary['p95_latency_s']}s",
        f"- First-invocation cases: {summary['first_invocation_count']}",
        f"- Avg latency (first invocation only): {summary['first_invocation_avg_latency_s']}s",
        f"- P95 latency (first invocation only): {summary['first_invocation_p95_latency_s']}s",
        "",
        "> **Note:** The model caches responses for identical prompts. Jittered variants",
        "> of the same base case often produce identical prompts (marker names, not values),",
        "> so only the first variant per base case invokes the model. First-invocation",
        "> latency reflects true model inference time.",
        "",
        "## Case Table",
        "",
        "| Case ID | Scenario | Signal | Critic | GR | Patches | Model | Agent | 1st | Latency(s) |",
        "|---|---|:---:|---:|---|---:|---:|---:|:---:|---:|",
    ]
    for r in records:
        diag = "n/a" if r["diagnostic_hit"] is None else ("Y" if r["diagnostic_hit"] else "N")
        first = "Y" if r.get("first_invocation") else "-"
        lines.append(
            f"| {r['case_id']} | {r['scenario']} | {diag} | {r['critic_ops_count']} "
            f"| {r['guardrail_status']} | {r['patches_count']} | {r['model_calls']} "
            f"| {r['agent_decisions']} | {first} | {r['latency_s']} |"
        )
    with open(f"{base}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"json": f"{base}.json", "csv": f"{base}.csv", "md": f"{base}.md"}


def main():
    parser = argparse.ArgumentParser(description="Run med-EVE evaluation suite.")
    parser.add_argument("--dataset", choices=("legacy", "golden"), default="golden")
    parser.add_argument("--manifest", default=DEFAULT_GOLDEN_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=_seed_from_env())
    parser.add_argument("--model-wait-timeout", type=float, default=float(os.getenv("EVAL_MODEL_WAIT_TIMEOUT_S", "180")))
    parser.add_argument("--limit", type=int, default=0, help="Optional: evaluate only first N cases (0 = all).")
    args = parser.parse_args()

    os.environ["REPRODUCIBILITY_SEED"] = str(args.seed)
    if not model_manager.lite_mode:
        if not model_manager.model_loaded:
            print("MODE=model detected. Loading model before eval...")
            model_manager.load_model()
        if not model_manager.model_loaded:
            raise RuntimeError(
                "MODE=model requested but model failed to load. "
                "Check dependency stack and model files."
            )

    if args.dataset == "legacy":
        items = _materialize_legacy_cases()
    else:
        items = _materialize_golden_cases(args.manifest, args.seed)
    if args.limit and args.limit > 0:
        items = items[:args.limit]

    records = []
    for item in items:
        records.append(_evaluate_case(item))

    summary = _aggregate(records)
    artifacts = _write_artifacts(records, summary, args.output_dir, args.dataset)

    print("Evaluation complete:")
    print(f"  mode: {'model' if not model_manager.lite_mode else 'lite'}")
    print(f"  dataset: {args.dataset}")
    print(f"  cases: {summary['cases_total']}")
    print(f"  signal_detection_rate: {_fmt_pct(summary['diagnostic_hit_rate'])}")
    print(f"  critic_intervention_rate: {_fmt_pct(summary['critic_intervention_rate'])}")
    print(f"  guardrail_catch_rate: {_fmt_pct(summary['guardrail_catch_rate'])}")
    print(f"  guardrail_false_positive_rate: {_fmt_pct(summary['guardrail_false_positive_rate'])}")
    print(f"  avg_model_calls: {summary['avg_model_calls']}")
    print(f"  avg_agent_decisions: {summary['avg_agent_decisions']}")
    print(f"  avg_latency_s: {summary['avg_latency_s']}")
    print(f"  first_invocation_count: {summary['first_invocation_count']}")
    print(f"  first_invocation_avg_latency_s: {summary['first_invocation_avg_latency_s']}")
    print(f"  artifacts: {artifacts['json']}, {artifacts['csv']}, {artifacts['md']}")


if __name__ == "__main__":
    main()