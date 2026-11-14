import pytest
from fastapi.testclient import TestClient

from bizmate.config import Settings
from bizmate.main import create_app


@pytest.fixture(autouse=True)
def offline_planner(monkeypatch):
    # Keep regression runs independent of a developer's configured paid-provider mode.
    # Explicit Settings(planner_mode="openai") still exercises mocked adapter tests.
    monkeypatch.setenv("BIZMATE_PLANNER_MODE", "demo")
    monkeypatch.delenv("BIZMATE_OPENAI_API_KEY", raising=False)


@pytest.fixture
def persistent_client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "api.sqlite3"))
    with TestClient(create_app(settings)) as client:
        yield client
