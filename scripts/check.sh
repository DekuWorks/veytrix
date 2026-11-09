#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x .venv/bin/ruff ]]; then
  RUFF=(.venv/bin/ruff)
  PYTEST=(.venv/bin/pytest)
  PYTHON=(.venv/bin/python)
else
  RUFF=(ruff)
  PYTEST=(pytest)
  PYTHON=(python3)
fi

"${RUFF[@]}" check .
"${RUFF[@]}" format --check .
"${PYTEST[@]}"
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
"${PYTHON[@]}" scripts/scan_secrets.py
