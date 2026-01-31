# Model performance and response optimization

This guide walks through running a full experiment to tune model performance and response quality, then applying what you learn.

---

## 1. Run a full experiment (measure)

### Prerequisites

- `MODE=model` and model loaded (e.g. MedGemma in `models/medgemma-4b-it` or `MEDGEMMA_DEVICE=cpu`).
- From repo root: `cd backend` and `export PYTHONPATH=$(pwd)` (or use the Makefile targets below).

### Option A: Single run (current env)

Measure one case with your current environment (useful for ad‑hoc tuning):

```bash
cd backend
export PYTHONPATH=$(pwd)
MODE=model python evals/run_optimization_experiment.py --case case_02_anemia_of_inflammation_gotcha --json
```

Output: JSON with `total_wall_s`, `timings`, `REASON_agents_ms`, `model_calls`, `hypotheses_count`, `patient_actions_count`, `guardrail_status`, `hypotheses_valid`.

### Option B: Experiment matrix (baseline vs fast vs quality)

Compare three configs on one or more cases (each config runs in a subprocess so env is clean):

```bash
cd backend
export PYTHONPATH=$(pwd)
MODE=model python evals/run_optimization_experiment.py --experiment --cases case_02_anemia_of_inflammation_gotcha case_04_primary_hypothyroid
```

Configs:

| Config    | HYPOTHESIS_TOP_PATTERNS | USE_ACTION_GENERATION_MODEL | MEDGEMMA_MAX_TOKENS |
|----------|-------------------------|-----------------------------|----------------------|
| baseline | 5                       | 1                           | 384                  |
| fast     | 3                       | 0                           | 256                  |
| quality  | 8                       | 1                           | 512                  |

Output: summary table (wall time, REASON time, model calls, hypotheses count, actions, guardrail) and full JSON.

### Option C: Custom env (single run)

Try your own knobs:

```bash
cd backend
export PYTHONPATH=$(pwd)
MODE=model HYPOTHESIS_TOP_PATTERNS=3 USE_ACTION_GENERATION_MODEL=0 MEDGEMMA_MAX_TOKENS=256 \
  python evals/run_optimization_experiment.py --case case_02_anemia_of_inflammation_gotcha --json
```

### Metrics to watch

- **total_wall_s** – End‑to‑end pipeline time.
- **timings.REASON** – REASON step wall time.
- **REASON_agents_ms** – Per‑agent breakdown (e.g. `hypothesis_generation`, `action_generation`); use this to see which calls dominate.
- **model_calls** – Total model invocations; fewer is faster if quality is acceptable.
- **hypotheses_count** / **hypotheses_valid** – Response usefulness.
- **guardrail_status** – PASS/FAIL; evals expect specific behaviour (e.g. gotcha case).

---

## 2. Run evals (quality gate)

After changing env or code, ensure quality does not regress:

```bash
make evals
# or: cd backend && PYTHONPATH=$(pwd) python evals/run_evals.py
```

Evals use `_run_pipeline` on all cases and check guardrail status (and gotcha logic). Fix any regressions before locking in optimizations.

---

## 3. Analyze and decide

1. **Compare configs** – From the experiment table/JSON, compare baseline vs fast vs quality (and any custom runs).
2. **Identify trade-offs** – e.g. “fast” gives ~X% lower wall time but Y fewer hypotheses or different guardrail outcome.
3. **Choose targets** – e.g. “We want &lt; 30s wall and guardrail PASS on gotcha” or “We accept one fewer model call (no action_generation) for 20% speedup.”

---

## 4. Implement learned insights

### A. Change defaults in code

- **reasoner_medgemma.py** – Defaults for `TOP_N_CANDIDATE_PATTERNS`, `MAX_SUPPORTS_IN_PROMPT`, etc. are read from env with fallbacks; change the fallbacks if you want new defaults.
- **agent_manager.py** – `USE_ACTION_GENERATION_MODEL` default is `True`; set to `False` if you want to disable the action model by default.

### B. Document recommended env (e.g. “fast” profile)

In README or run scripts, document a “fast” profile:

```bash
# Fast model run (fewer patterns, no action-generation model call)
export MODE=model
export HYPOTHESIS_TOP_PATTERNS=3
export USE_ACTION_GENERATION_MODEL=0
export MEDGEMMA_MAX_TOKENS=256
make run
```

### C. Add a Make target (optional)

In the root `Makefile`:

```makefile
run-fast:
	HYPOTHESIS_TOP_PATTERNS=3 USE_ACTION_GENERATION_MODEL=0 MEDGEMMA_MAX_TOKENS=256 $(MAKE) run
```

### D. Tune prompts

If you see repeated failures (e.g. malformed JSON, missing hypotheses), iterate on:

- `backend/prompts/hypothesis_generation.txt` – Instruction clarity, schema, and length.
- `MEDGEMMA_MAX_TOKENS` – Increase if outputs are truncated.

Re-run the hypothesis test script and evals after prompt changes:

```bash
MODE=model make hypothesis-test   # optional: inspect prompt and raw output
make evals
```

### E. Lock in a “recommended” config

Once you are happy with a config (e.g. baseline vs fast):

1. Update defaults in code or document the env in `docs/OPTIMIZATION.md` and README.
2. Add or adjust tests (e.g. `test_agent_manager.py` for `USE_ACTION_GENERATION_MODEL=0`).
3. Re-run `make test` and `make evals` before committing.

---

## 5. Environment reference

| Variable | Default | Effect |
|----------|--------|--------|
| `MODE` | lite | `model` = use MedGemma for REASON (and other agents when enabled). |
| `HYPOTHESIS_TOP_PATTERNS` | 5 | Max candidate patterns in hypothesis prompt (smaller = faster). |
| `HYPOTHESIS_MAX_SUPPORTS` | 15 | Max supports in hypothesis prompt. |
| `HYPOTHESIS_MAX_CONTRADICTIONS` | 15 | Max contradictions in hypothesis prompt. |
| `HYPOTHESIS_MAX_DISCRIMINATORS` | 20 | Max top_discriminators in hypothesis prompt. |
| `USE_ACTION_GENERATION_MODEL` | 1 | 0 = skip action_generation model call (use hypothesis actions or empty). |
| `MEDGEMMA_MAX_TOKENS` | 384 | Max tokens per model call; lower = faster, higher = less truncation. |
| `USE_SYMPTOM_MAPPER_MODEL` | 1 | 0 = rule-based symptom mapping only. |
| `USE_NOVEL_INSIGHT_MODEL` | 0 | 1 = enable novel_insight agent when conditions met. |

---

## Quick checklist

1. Run experiment: `MODE=model python backend/evals/run_optimization_experiment.py --experiment --cases case_02_anemia_of_inflammation_gotcha`.
2. Run evals: `make evals`.
3. Analyze table/JSON; decide target (speed vs quality).
4. Implement: change defaults or document env; optionally add `run-fast` target.
5. Re-run evals and tests; commit once green.
