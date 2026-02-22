#!/bin/bash

set -euo pipefail

# One-command demo entrypoint.
# Default is lite mode. For model mode:
#   MODE=model ./run_demo.sh

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -x "$ROOT_DIR/run_local.sh" ]; then
    chmod +x "$ROOT_DIR/run_local.sh"
fi

export REPRODUCIBILITY_SEED="${REPRODUCIBILITY_SEED:-42}"

echo "Launching med-EVE demo (MODE=${MODE:-lite}, REPRODUCIBILITY_SEED=${REPRODUCIBILITY_SEED})"
exec "$ROOT_DIR/run_local.sh" demo
