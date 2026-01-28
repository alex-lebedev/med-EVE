# Local model directory

Place MedGemma in `models/medgemma-4b-it/` (repo-relative). The backend looks for `<repo_root>/models/medgemma-4b-it` and loads from disk if `config.json` (and usual weight files) are present.

Run with `MODE=model` (e.g. `MODE=model make demo`).
