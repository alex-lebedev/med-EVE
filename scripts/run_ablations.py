#!/usr/bin/env python3
"""
Run internal med-EVE ablations across execution modes and export summary artifacts.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_SCRIPT = os.path.join(ROOT_DIR, "backend", "evals", "run_evals.py")
DEFAULT_MANIFEST = os.path.join(ROOT_DIR, "backend", "data_synth", "golden_cases", "golden_manifest.json")
DEFAULT_OUT_DIR = os.path.join(ROOT_DIR, "backend", "evals", "results", "ablations")

ABLATIONS = {
    "lite": {
        "MODE": "lite",
        "USE_CONTEXT_SELECTION_MODEL": "0",
        "USE_EVIDENCE_WEIGHTING_MODEL": "0",
        "USE_HYPOTHESIS_GENERATION_MODEL": "0",
        "USE_TEST_RECOMMENDATION_MODEL": "0",
        "USE_ACTION_GENERATION_MODEL": "0",
        "USE_GUARDRAIL_EXPLANATION_MODEL": "0",
        "USE_SYMPTOM_MAPPER_MODEL": "0",
        "USE_CASE_IMPRESSION_MODEL": "0",
        "USE_NOVEL_INSIGHT_MODEL": "0",
    },
    "hybrid_default": {
        "MODE": "model",
        "USE_CONTEXT_SELECTION_MODEL": "0",
        "USE_EVIDENCE_WEIGHTING_MODEL": "0",
        "USE_HYPOTHESIS_GENERATION_MODEL": "0",
        "USE_TEST_RECOMMENDATION_MODEL": "0",
        "USE_ACTION_GENERATION_MODEL": "0",
        "USE_GUARDRAIL_EXPLANATION_MODEL": "0",
        "USE_NOVEL_INSIGHT_MODEL": "0",
    },
    "full_agent": {
        "MODE": "model",
        "USE_CONTEXT_SELECTION_MODEL": "1",
        "USE_EVIDENCE_WEIGHTING_MODEL": "1",
        "USE_HYPOTHESIS_GENERATION_MODEL": "1",
        "USE_TEST_RECOMMENDATION_MODEL": "1",
        "USE_ACTION_GENERATION_MODEL": "1",
        "USE_GUARDRAIL_EXPLANATION_MODEL": "1",
        "USE_SYMPTOM_MAPPER_MODEL": "1",
        "USE_CASE_IMPRESSION_MODEL": "1",
        "USE_NOVEL_INSIGHT_MODEL": "1",
    },
}


def _run_config(name: str, env_overrides: dict, dataset: str, manifest: str, output_dir: str, seed: int):
    env = os.environ.copy()
    env.update(env_overrides)
    env["REPRODUCIBILITY_SEED"] = str(seed)
    env["PYTHONPATH"] = os.path.join(ROOT_DIR, "backend")

    cmd = [
        sys.executable,
        EVAL_SCRIPT,
        "--dataset",
        dataset,
        "--manifest",
        manifest,
        "--output-dir",
        output_dir,
        "--seed",
        str(seed),
    ]
    completed = subprocess.run(cmd, cwd=os.path.join(ROOT_DIR, "backend"), env=env, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Ablation '{name}' failed (exit={completed.returncode})\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    match = re.search(r"artifacts:\s+([^,]+),\s*([^,]+),\s*([^\n]+)", completed.stdout)
    if not match:
        raise RuntimeError(f"Could not parse artifacts path for '{name}'. Output:\n{completed.stdout}")
    json_path = match.group(1).strip()
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    summary = payload.get("summary", {})
    return {
        "config": name,
        "cases_total": summary.get("cases_total"),
        "diagnostic_hit_rate": summary.get("diagnostic_hit_rate"),
        "critic_intervention_rate": summary.get("critic_intervention_rate"),
        "guardrail_catch_rate": summary.get("guardrail_catch_rate"),
        "schema_valid_rate": summary.get("schema_valid_rate"),
        "avg_latency_s": summary.get("avg_latency_s"),
        "p95_latency_s": summary.get("p95_latency_s"),
        "source_json": json_path,
    }


def _pct(v):
    if v is None:
        return "n/a"
    return f"{100.0 * float(v):.1f}%"


def _write_summary(records, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(output_dir, f"ablation_summary_{ts}")

    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump({"rows": records}, f, indent=2)

    fields = list(records[0].keys()) if records else []
    with open(f"{base}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    lines = [
        "# Ablation Summary",
        "",
        "| Config | Cases | Diagnostic Hit | Critic Interventions | Guardrail Catch | Schema Valid | Avg Latency(s) | P95 Latency(s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in records:
        lines.append(
            f"| {r['config']} | {r['cases_total']} | {_pct(r['diagnostic_hit_rate'])} | {_pct(r['critic_intervention_rate'])} | "
            f"{_pct(r['guardrail_catch_rate'])} | {_pct(r['schema_valid_rate'])} | {r['avg_latency_s']} | {r['p95_latency_s']} |"
        )
    with open(f"{base}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"json": f"{base}.json", "csv": f"{base}.csv", "md": f"{base}.md"}


def main():
    parser = argparse.ArgumentParser(description="Run internal ablations for med-EVE.")
    parser.add_argument("--dataset", choices=("legacy", "golden"), default="golden")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=int(os.getenv("REPRODUCIBILITY_SEED", "42")))
    parser.add_argument("--configs", nargs="*", default=["lite", "hybrid_default", "full_agent"])
    args = parser.parse_args()

    selected = []
    for cfg in args.configs:
        if cfg not in ABLATIONS:
            raise ValueError(f"Unknown config '{cfg}'. Available: {', '.join(ABLATIONS.keys())}")
        selected.append(cfg)

    rows = []
    for cfg in selected:
        cfg_out = os.path.join(args.output_dir, cfg)
        os.makedirs(cfg_out, exist_ok=True)
        rows.append(_run_config(cfg, ABLATIONS[cfg], args.dataset, args.manifest, cfg_out, args.seed))

    artifacts = _write_summary(rows, args.output_dir)
    print("Ablation complete:")
    print(f"  configs: {', '.join(selected)}")
    print(f"  summary: {artifacts['json']}, {artifacts['csv']}, {artifacts['md']}")


if __name__ == "__main__":
    main()
