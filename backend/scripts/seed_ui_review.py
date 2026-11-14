"""Explicit, additive UI review fixtures. Never a public API or a workflow implementation."""

import argparse
from pathlib import Path

from bizmate.domain.models import Task
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context


def seed(database: Path) -> list[str]:
    repository = SQLiteTaskRepository(database)
    context = demo_context("merchant_demo")
    fixtures = Path(__file__).resolve().parents[2] / "frontend/src/test/contract-fixtures"
    created = []
    for name in ("ui-ticket-fixture", "ui-campaign-fixture"):
        snapshot = Task.model_validate_json((fixtures / f"{name}.json").read_text(encoding="utf-8"))
        if repository.get_task(context, snapshot.task_id) is not None:
            continue  # Do not overwrite approvals, receipts or an earlier review run.
        repository.save(context, snapshot.with_updates(revision=0))
        created.append(snapshot.task_id)
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, required=True, help="Use a dedicated UI review SQLite file"
    )
    args = parser.parse_args()
    print({"created": seed(args.database.resolve()), "simulated": True})
