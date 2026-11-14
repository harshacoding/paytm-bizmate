"""Run from root: uv run --project backend python backend/scripts/export_openapi.py [--check]"""

import json
import sys
from pathlib import Path

from bizmate.domain.lifecycle import TRANSITIONS
from bizmate.main import create_app

root = Path(__file__).resolve().parents[2]
exports = {
    "openapi.json": create_app().openapi(),
    "lifecycle.json": {
        "contract_version": "0.3.0",
        "transitions": {
            source.value: sorted(target.value for target in targets)
            for source, targets in TRANSITIONS.items()
        },
        "completion_requirement": "Every receipt needs a successful independent verification.",
    },
}
for filename, data in exports.items():
    destination = root / "contracts" / filename
    content = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not destination.exists() or destination.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Contract drift in {filename}: run npm run contracts:generate.")
        print(f"Contract {filename} matches backend.")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")
        print(f"Exported contracts/{filename}")
