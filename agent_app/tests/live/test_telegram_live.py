import os

import pytest

from deal_agent.connectors.telegram import TelegramHttpConnector

pytestmark = pytest.mark.live

REQUIRED_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
SEND_OPT_IN_ENV = "TELEGRAM_LIVE_SEND"


def test_telegram_connector_sends_status_message():
    _skip_unless_telegram_live_send_enabled()

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


def _skip_unless_telegram_live_send_enabled() -> None:
    missing = _missing_telegram_live_requirements()
    if missing:
        pytest.skip(
            "missing live Telegram env vars or explicit send opt-in: "
            f"{', '.join(missing)}"
        )


def _missing_telegram_live_requirements() -> list[str]:
    missing = [name for name in REQUIRED_ENV if _missing_or_placeholder(name)]
    if os.getenv(SEND_OPT_IN_ENV) != "1":
        missing.append(f"{SEND_OPT_IN_ENV}=1")
    return missing


def _missing_or_placeholder(name: str) -> bool:
    value = os.getenv(name)
    return not value or value.startswith("replace-with-")
