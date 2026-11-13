#!/bin/bash
# Local research worker. Sources the gitignored .env and does not print it.
set -euo pipefail
cd /Users/marcusbrown/Developer/veytrix-sanctum-preview
set -a
# shellcheck disable=SC1091
source /Users/marcusbrown/Developer/veytrix/.env
set +a
export VEYTRIX_ENV=local
export VEYTRIX_ENABLE_LIVE_BROKER=0
export DATABASE_URL="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix"
export PYTHONPATH="/Users/marcusbrown/Developer/veytrix-sanctum-preview/services/api:/Users/marcusbrown/Developer/veytrix-sanctum-preview/services/market-data:/Users/marcusbrown/Developer/veytrix-sanctum-preview/services/risk:/Users/marcusbrown/Developer/veytrix-sanctum-preview/services/quant:/Users/marcusbrown/Developer/veytrix-sanctum-preview/services/ai-research"
exec /Users/marcusbrown/Developer/veytrix/.venv/bin/python -m veytrix_api.worker
