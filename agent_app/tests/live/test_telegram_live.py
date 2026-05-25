import os

import pytest

from deal_agent.connectors.telegram import TelegramHttpConnector

pytestmark = pytest.mark.live

REQUIRED_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def test_telegram_connector_sends_status_message():
    _skip_unless_env(REQUIRED_ENV)

    connector = TelegramHttpConnector(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )

    ref = connector.send_status(
        "live_smoke",
        "deal-agent live smoke test",
    )

    assert ref.system == "telegram"
    assert ref.external_id
    assert ref.metadata["kind"] == "message"


def _skip_unless_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if _missing_or_placeholder(name)]
    if missing:
        pytest.skip(f"missing live Telegram env vars: {', '.join(missing)}")


def _missing_or_placeholder(name: str) -> bool:
    value = os.getenv(name)
    return not value or value.startswith("replace-with-")
