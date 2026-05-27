from __future__ import annotations

from deal_agent.config import Settings
from deal_agent.connectors import (
    GitHubHttpConnector,
    LinearHttpConnector,
    OdooHttpConnector,
    TelegramHttpConnector,
)
from deal_agent.nim_client import NimChatClient
from deal_agent.runner import DealWorkflowRunner
from deal_agent.services import NimModelServices


def create_live_runner(settings: Settings) -> DealWorkflowRunner:
    owner, repo = _parse_github_repository(settings.github_repository or "")
    nim_base_url = _normalize_nim_base_url(settings.nim_base_url)
    nim_client = NimChatClient(
        api_key=settings.nvidia_api_key or "",
        model=settings.nim_model or settings.nvidia_model,
        base_url=nim_base_url,
    )

    return DealWorkflowRunner(
        models=NimModelServices(nim_client),
        odoo=OdooHttpConnector(
            base_url=settings.odoo_url,
            token=settings.odoo_api_key or "",
            database=settings.odoo_database,
        ),
        linear=LinearHttpConnector(
            api_key=settings.linear_api_key or "",
            team_id=settings.linear_team_id or "",
        ),
        github=GitHubHttpConnector(
            token=settings.github_token or "",
            owner=owner,
            repo=repo,
        ),
        telegram=TelegramHttpConnector(
            token=settings.agent_telegram_bot_token or "",
            chat_id=settings.agent_telegram_chat_id or "",
        ),
    )


def _parse_github_repository(repository: str) -> tuple[str, str]:
    owner, separator, repo = repository.strip().partition("/")
    if not owner or separator != "/" or not repo or "/" in repo:
        raise ValueError("GITHUB_REPOSITORY must use owner/repository format")
    return owner, repo


def _normalize_nim_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized
