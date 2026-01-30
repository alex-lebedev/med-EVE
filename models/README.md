# Local model directory (optional)

This folder is **optional**. Use it if you want med-EVE to load a model from the repo instead of the HuggingFace cache.

## Recommended: use the actual medical model in the repo

Placing the 4B model in `models/medgemma-4b-it/` (e.g. via `python scripts/download_model.py`) is the **recommended** way to use the actual medical model. The backend **prefers** this folder over HuggingFace when it exists: it loads from here and does not call the HuggingFace API, so you can run fully offline.

## When the app uses this folder

- If you place a model here (e.g. `models/medgemma-4b-it/` or `models/medgemma-27b-text-it/`) with `config.json` and the usual weight files, the backend **prefers** this and loads from here (no HuggingFace API; works offline).
- If you don’t put anything here, the app downloads from HuggingFace and uses `~/.cache/huggingface` (see main [README](../README.md) section **Running modes and models**).

## Folder layout

- **Folder name** must match the last part of the model id:
  - `medgemma-4b-it` for `google/medgemma-4b-it`
  - `medgemma-27b-text-it` for `google/medgemma-27b-text-it`
- **Required:** `config.json` plus the usual weight files (e.g. `*.safetensors`, tokenizer files).

Example:

```
models/
  medgemma-4b-it/
    config.json
    model-00001-of-00002.safetensors
    ...
  medgemma-27b-text-it/
    config.json
    ...
```

## How to run

- `export MODE=model`
- Optionally `export MEDGEMMA_MODEL=google/medgemma-27b-text-it` (or leave default for 4B)
- `make demo`

The repo’s `models/` contents are gitignored except this README, so large weights are not committed.
