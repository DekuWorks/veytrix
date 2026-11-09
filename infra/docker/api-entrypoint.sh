#!/bin/sh
set -eu

# Alembic runs only for the local paper posture. The application also refuses
# to boot when live broker mode is set or the environment is not local.
if [ "${VEYTRIX_ENV:-}" = "local" ]; then
  alembic upgrade head
else
  echo "Alembic upgrade skipped: VEYTRIX_ENV is not local." >&2
fi

# 0.0.0.0 is the container interface. Compose publishes 127.0.0.1 on the host.
exec uvicorn veytrix_api.main:app --host 0.0.0.0 --port 8000 --no-access-log
