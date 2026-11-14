from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIZMATE_", env_file=BACKEND_ROOT / ".env", extra="ignore"
    )
    demo_merchant_id: str = "merchant_demo"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_path: str = ".data/bizmate.sqlite3"

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path).expanduser()
        return path if path.is_absolute() else BACKEND_ROOT / path
