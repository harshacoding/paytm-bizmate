import pytest
from fastapi.testclient import TestClient

from bizmate.config import Settings
from bizmate.main import create_app


@pytest.fixture
def persistent_client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "api.sqlite3"))
    with TestClient(create_app(settings)) as client:
        yield client
