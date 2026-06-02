from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    nvidia_api_key: str | None = None
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nim_vision_model: str | None = None
    nim_audio_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    nim_audio_inline_max_bytes: int = 180000
    meeting_audio_min_confidence: float = 0.45
    meeting_audio_max_telegram_chars: int = 3900
    odoo_api_key: str | None = None
    odoo_database: str | None = None
    linear_api_key: str | None = None
    linear_team_id: str | None = None
    github_token: str | None = None
    github_repository: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    agent_telegram_bot_token: str | None = None
    agent_telegram_chat_id: str | None = None
    agent_telegram_allowed_user_ids: str | None = None
    live_workflow_enabled: bool = False
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    odoo_url: str = "http://localhost:8069"

    def missing_live_workflow_config(self) -> list[str]:
        return _missing_env_names(
            self,
            {
                "NVIDIA_API_KEY": "nvidia_api_key",
                "ODOO_API_KEY": "odoo_api_key",
                "LINEAR_API_KEY": "linear_api_key",
                "LINEAR_TEAM_ID": "linear_team_id",
                "GITHUB_TOKEN": "github_token",
                "GITHUB_REPOSITORY": "github_repository",
                "AGENT_TELEGRAM_BOT_TOKEN": "agent_telegram_bot_token",
                "AGENT_TELEGRAM_CHAT_ID": "agent_telegram_chat_id",
            },
        )

    def missing_agent_telegram_config(self) -> list[str]:
        return _missing_env_names(
            self,
            {
                "AGENT_TELEGRAM_BOT_TOKEN": "agent_telegram_bot_token",
                "AGENT_TELEGRAM_ALLOWED_USER_IDS": "agent_telegram_allowed_user_ids",
            },
        )

    def agent_telegram_allowed_user_id_set(self) -> set[int]:
        if not self.agent_telegram_allowed_user_ids:
            return set()

        allowed: set[int] = set()
        for raw_value in self.agent_telegram_allowed_user_ids.split(","):
            raw_value = raw_value.strip()
            if not raw_value:
                continue
            try:
                allowed.add(int(raw_value))
            except ValueError:
                continue
        return allowed


def _missing_env_names(settings: Settings, env_to_field: dict[str, str]) -> list[str]:
    missing = []
    for env_name, field_name in env_to_field.items():
        value = getattr(settings, field_name)
        if value is None:
            missing.append(env_name)
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.startswith("replace-with-"):
                missing.append(env_name)
    return missing


settings = Settings()
