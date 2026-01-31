#!/usr/bin/env python3
"""
Run pipeline under different env configs and collect timing + quality metrics for optimization.

Usage:
  # Single run (current env); prints JSON to stdout
  MODE=model python evals/run_optimization_experiment.py --case case_02_anemia_of_inflammation_gotcha

  # Full experiment: run predefined configs (baseline, fast, quality) and print summary table
  MODE=model python evals/run_optimization_experiment.py --experiment --cases case_02_anemia_of_inflammation_gotcha case_04_primary_hypothyroid

  # Custom config via env (run once)
  MODE=model HYPOTHESIS_TOP_PATTERNS=3 USE_ACTION_GENERATION_MODEL=0 python evals/run_optimization_experiment.py --case case_02_anemia_of_inflammation_gotcha

Output JSON (single run) includes: case_id, timings (step times + REASON_agents_ms), model_usage,
hypotheses_count, guardrail_status, patient_actions_count, total_wall_s.
"""

import json
import os
import sys
import subprocess
import time

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_one(case_id: str) -> dict:
    """Run pipeline once for case_id using current env; return metrics dict."""
    from app import _run_pipeline, load_cases

    cases = load_cases()
    if case_id not in cases:
        return {"error": f"case not found: {case_id}"}
    case = cases[case_id]
    t0 = time.time()
    result = _run_pipeline(case, [])
    wall_s = time.time() - t0

    timings = result.get("timings") or {}
    reasoner = result.get("reasoner_output") or {}
    guardrail = result.get("guardrail_report") or {}
    model_usage = result.get("model_usage") or {}

    metrics = {
        "case_id": case_id,
        "total_wall_s": round(wall_s, 2),
        "timings": {k: v for k, v in timings.items() if isinstance(v, (int, float))},
        "REASON_agents_ms": timings.get("REASON_agents_ms") or {},
        "model_calls": model_usage.get("model_calls", 0),
        "hypotheses_count": len(reasoner.get("hypotheses") or []),
        "patient_actions_count": len(reasoner.get("patient_actions") or []),
        "guardrail_status": guardrail.get("status", "UNKNOWN"),
        "hypotheses_valid": result.get("reasoner_output", {}).get("hypotheses_valid", False),
    }
    return metrics


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run optimization experiment: single run or matrix of configs")
    parser.add_argument("--case", type=str, help="Run single case (e.g. case_02_anemia_of_inflammation_gotcha)")
    parser.add_argument("--experiment", action="store_true", help="Run full experiment matrix (subprocess per config)")
    parser.add_argument("--cases", nargs="*", default=["case_02_anemia_of_inflammation_gotcha"], help="Case IDs for --experiment")
    parser.add_argument("--json", action="store_true", help="Print full JSON for single run; default is summary line")
    args = parser.parse_args()

    if args.experiment:
        # Run each config in subprocess so env is clean (module-level env reads)
        configs = [
            ("baseline", {"HYPOTHESIS_TOP_PATTERNS": "5", "USE_ACTION_GENERATION_MODEL": "1", "MEDGEMMA_MAX_TOKENS": "384"}),
            ("fast", {"HYPOTHESIS_TOP_PATTERNS": "3", "USE_ACTION_GENERATION_MODEL": "0", "MEDGEMMA_MAX_TOKENS": "256"}),
            ("quality", {"HYPOTHESIS_TOP_PATTERNS": "8", "USE_ACTION_GENERATION_MODEL": "1", "MEDGEMMA_MAX_TOKENS": "512"}),
        ]
        env_base = dict(os.environ)
        if "MODE" not in env_base or env_base.get("MODE") != "model":
            env_base["MODE"] = "model"
        all_results = []
        for config_name, env_overrides in configs:
            for case_id in args.cases:
                env = {**env_base, **env_overrides}
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cmd = [sys.executable, "-c",
                       "import sys; sys.path.insert(0, %r); from evals.run_optimization_experiment import run_one; "
                       "import json; print(json.dumps(run_one(%r)))" % (backend_dir, case_id)]
                try:
                    out = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=backend_dir, env=env)
                    if out.returncode != 0:
                        all_results.append({"config": config_name, "case_id": case_id, "error": out.stderr or "non-zero exit"})
                    else:
                        metrics = json.loads(out.stdout.strip())
                        metrics["config"] = config_name
                        all_results.append(metrics)
                except subprocess.TimeoutExpired:
                    all_results.append({"config": config_name, "case_id": case_id, "error": "timeout"})
                except Exception as e:
                    all_results.append({"config": config_name, "case_id": case_id, "error": str(e)})
        # Summary table
        print("Config      Case     Wall(s)  REASON(s)  ModelCalls  Hypos  Actions  Guardrail")
        print("-" * 75)
        for r in all_results:
            if "error" in r:
                print("%-11s %-30s ERROR: %s" % (r.get("config", "?"), r.get("case_id", "?"), r["error"][:40]))
                continue
            reason_s = (sum((r.get("REASON_agents_ms") or {}).values()) or 0) / 1000.0
            print("%-11s %-30s %6.1f   %6.1f   %10d %5d %7d   %s" % (
                r.get("config", ""),
                r.get("case_id", "")[:30],
                r.get("total_wall_s", 0),
                reason_s,
                r.get("model_calls", 0),
                r.get("hypotheses_count", 0),
                r.get("patient_actions_count", 0),
                r.get("guardrail_status", ""),
            ))
        print()
        print("Full results (JSON):")
        print(json.dumps(all_results, indent=2))
        return

    if not args.case:
        parser.error("Either --case CASE_ID or --experiment required")
    metrics = run_one(args.case)
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        reason_s = (sum((metrics.get("REASON_agents_ms") or {}).values()) or 0) / 1000.0
        print("wall_s=%.1f reason_s=%.1f model_calls=%d hypotheses=%d actions=%d guardrail=%s" % (
            metrics.get("total_wall_s", 0), reason_s,
            metrics.get("model_calls", 0), metrics.get("hypotheses_count", 0),
            metrics.get("patient_actions_count", 0), metrics.get("guardrail_status", ""),
        ))
        if metrics.get("REASON_agents_ms"):
            print("  REASON_agents_ms:", metrics["REASON_agents_ms"])


if __name__ == "__main__":
    main()
