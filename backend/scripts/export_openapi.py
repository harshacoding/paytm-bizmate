"""Run from root: uv run --project backend python backend/scripts/export_openapi.py [--check]"""

import json
import sys
from pathlib import Path

from bizmate.main import create_app

root = Path(__file__).resolve().parents[2]
destination = root / "contracts" / "openapi.json"
content = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
if "--check" in sys.argv:
    if not destination.exists() or destination.read_text(encoding="utf-8") != content:
        raise SystemExit(
            "OpenAPI drift: run npm run contracts:generate and commit contracts + types."
        )
    print("OpenAPI contract matches backend.")
else:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")
    print("Exported contracts/openapi.json")
