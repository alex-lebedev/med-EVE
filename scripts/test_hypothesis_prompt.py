#!/usr/bin/env python3
"""
Run the exact hypothesis_generation prompt the pipeline uses, without starting the app.
Saves prompt and raw model output to backend/output/ for inspection and iteration.

Use --max-tokens 384 or more for full hypothesis JSON; 64 is too small and yields
continuation of the prompt. Subgraph in the prompt is trimmed (id/type/label, id/from/to/relation)
for faster inference.

Run from repo root:
  MODE=model python scripts/test_hypothesis_prompt.py
  MODE=model python scripts/test_hypothesis_prompt.py --case case_02_anemia_of_inflammation_gotcha
  MODE=model python scripts/test_hypothesis_prompt.py --no-save --max-tokens 384

Or: make hypothesis-test
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="Run hypothesis_generation prompt and save raw output for inspection."
    )
    parser.add_argument(
        "--case",
        default="case_02_anemia_of_inflammation_gotcha",
        help="Case ID (filename without .json). Default: case_02_anemia_of_inflammation_gotcha",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=384,
        help="Max new tokens (default 384). Use 384+ for full hypothesis JSON; 64 is too small.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="Temperature for generation (default 0.3).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print only; do not write prompt or raw output to backend/output/.",
    )
    args = parser.parse_args()

    os.environ.setdefault("MODE", "model")
    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from core import lab_normalizer, context_selector, evidence_builder, events
    from core import dynamic_graph
    from core import symptom_mapper
    from core.model_manager import model_manager
    from core.agent_manager import agent_manager
    from core.reasoner_medgemma import PATTERN_TO_CONDITION, _trim_subgraph_for_prompt

    cases_dir = backend_dir / "data_synth" / "cases"
    case_path = cases_dir / f"{args.case}.json"
    if not case_path.is_file():
        print("Case not found: %s" % case_path)
        sys.exit(1)
    with open(case_path, "r", encoding="utf-8") as f:
        case = json.load(f)

    events_list = []
    normalized_labs = lab_normalizer.normalize_labs(case["labs"])
    patient_context = (case.get("patient") or {}).get("context") or {}
    case_card, subgraph = context_selector.select_context(
        normalized_labs, patient_context, events_list
    )
    subgraph, _ = dynamic_graph.extend_subgraph(case_card, subgraph)
    symptom_tokens = case.get("symptom_tokens") or list((case.get("patient") or {}).get("context") or {})
    symptom_nodes, symptom_edges, _ = symptom_mapper.map_symptoms_to_graph(
        symptom_tokens, case_card, subgraph, model_manager, reasoner_output=None, events_list=events_list
    )
    if symptom_nodes or symptom_edges:
        subgraph["nodes"] = list(subgraph.get("nodes") or []) + symptom_nodes
        subgraph["edges"] = list(subgraph.get("edges") or []) + symptom_edges
    evidence_bundle = evidence_builder.build_evidence(
        case_card, subgraph, normalized_labs, events_list, events
    )

    candidate_patterns = []
    for pattern_id, score in evidence_bundle.get("candidate_scores", {}).items():
        candidate_patterns.append({
            "pattern_id": pattern_id,
            "confidence": score,
            "condition": PATTERN_TO_CONDITION.get(pattern_id, "Unknown condition"),
        })
    evidence_data = {
        "candidate_patterns_json": json.dumps(candidate_patterns, indent=2),
        "evidence_bundle_json": json.dumps({
            "supports": evidence_bundle.get("supports", []),
            "contradictions": evidence_bundle.get("contradictions", []),
            "top_discriminators": evidence_bundle.get("top_discriminators", []),
            "candidate_scores": evidence_bundle.get("candidate_scores", {}),
        }, indent=2),
        "patient_context_json": json.dumps(case_card.get("patient_context", {}), indent=2),
        "subgraph_json": json.dumps(_trim_subgraph_for_prompt(evidence_bundle.get("subgraph", {})), indent=2),
    }
    context = {"case_card": case_card, "evidence_bundle": evidence_bundle}
    system_prompt, user_prompt = agent_manager._build_prompt(
        "hypothesis_generation", context, evidence_data
    )
    user_prompt = user_prompt + "\n{"

    out_dir = backend_dir / "output"
    if not args.no_save:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "hypothesis_prompt_system.txt").write_text(system_prompt, encoding="utf-8")
        (out_dir / "hypothesis_prompt_user.txt").write_text(user_prompt, encoding="utf-8")
        print("Saved prompt to %s/hypothesis_prompt_system.txt and hypothesis_prompt_user.txt" % out_dir)

    print("Loading model...")
    model_manager.load_model()
    if not model_manager.model_loaded:
        print("FAIL: Model did not load.")
        sys.exit(1)
    print("Model loaded. Generating...")
    max_tokens = max(128, min(1024, args.max_tokens))
    result = model_manager.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=args.temperature,
        top_p=0.9,
    )
    response_text = result.get("text") or result.get("raw_output") or ""

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    raw_path = out_dir / ("hypothesis_raw_%s.txt" % ts)
    if not args.no_save:
        raw_path.write_text(response_text, encoding="utf-8")
        print("Saved raw output to %s" % raw_path)
    else:
        print("Raw output (first 1500 chars):")
        print(response_text[:1500])
        if len(response_text) > 1500:
            print("...")

    extracted = model_manager._extract_json_from_text(response_text)
    if extracted is None and response_text.strip():
        extracted = model_manager._extract_json_from_text("{" + response_text)
    if extracted is not None and isinstance(extracted.get("hypotheses"), list):
        n = len(extracted["hypotheses"])
        print("OK: %d hypotheses extracted." % n)
    else:
        print("FAIL: no/invalid JSON or hypotheses not a list.")

    sys.exit(0)


if __name__ == "__main__":
    main()
