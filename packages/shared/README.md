# Shared contract

`openapi.json` is the committed OpenAPI document for the sprint routes. `tests/test_contract.py` loads the FastAPI app and fails if the live schema differs.

Regenerate it after an intentional API change:

```bash
python scripts/export_openapi.py
```

Review the diff. Do not regenerate it inside CI to hide a contract change.
