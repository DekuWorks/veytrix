import os

os.environ.setdefault("VEYTRIX_ENV", "local")
os.environ.setdefault("VEYTRIX_ENABLE_LIVE_BROKER", "0")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix",
)
