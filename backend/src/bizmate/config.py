from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIZMATE_", env_file=BACKEND_ROOT / ".env", extra="ignore"
    )
    demo_merchant_id: str = "merchant_demo"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_path: str = ".data/bizmate.sqlite3"
    demo_controls_enabled: bool = True
    planner_mode: Literal["demo", "openai"] = "demo"
    planner_model: str = "gpt-4o-mini"
    openai_api_key: SecretStr | None = None

    @property
    def checkpoint_file(self) -> Path:
        return self.database_file.with_name(self.database_file.stem + "-checkpoints.sqlite3")

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path).expanduser()
        return path if path.is_absolute() else BACKEND_ROOT / path
