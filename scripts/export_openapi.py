"""Write the committed OpenAPI snapshot from the running app factory."""

from __future__ import annotations

import json
from pathlib import Path

from veytrix_api.main import create_app


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "packages" / "shared" / "openapi.json"
    document = create_app().openapi()
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
