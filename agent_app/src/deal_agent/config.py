from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    nvidia_api_key: str | None = None
    odoo_api_key: str | None = None
    linear_api_key: str | None = None
    github_token: str | None = None
    telegram_bot_token: str | None = None
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    odoo_url: str = "http://localhost:8069"


settings = Settings()
