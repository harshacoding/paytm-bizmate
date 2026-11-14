from pathlib import Path
from runpy import run_path

from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import demo_context


def test_ui_fixture_seed_is_additive_and_preserves_existing_work(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/seed_ui_review.py"
    seed = run_path(str(script))["seed"]
    database = tmp_path / "ui-review.sqlite3"
    assert set(seed(database)) == {"ui-ticket-fixture", "ui-campaign-fixture"}
    repository = SQLiteTaskRepository(database)
    context = demo_context("merchant_demo")
    ticket = repository.get_task(context, "ui-ticket-fixture")
    assert ticket.status.value == "READY"
    repository.save(context, ticket.with_updates(next_action="Keep this review progress"))
    assert seed(database) == []
    assert repository.get_task(context, ticket.task_id).next_action == "Keep this review progress"
    assert repository.list_tasks(demo_context("merchant_other")) == []
