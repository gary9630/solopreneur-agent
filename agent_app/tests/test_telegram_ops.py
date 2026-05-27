import base64
import tomllib
from pathlib import Path

from deal_agent.connectors.base import ConnectorError
from deal_agent import telegram_ops_cli
from deal_agent.telegram_ops import TelegramOpsBot
from deal_agent.tool_models import BusinessCardToolRequest, CrmLookupRequest


REPO_ROOT = Path(__file__).resolve().parents[2]


class StubTelegram:
    def __init__(self) -> None:
        self.messages = []
        self.downloaded = []

    def send_message(self, chat_id: str, text: str):
        self.messages.append((chat_id, text))

    def get_file(self, file_id: str):
        return {"file_path": f"photos/{file_id}.jpg"}

    def download_file(self, file_path: str):
        self.downloaded.append(file_path)
        return b"card-bytes"


def _message_update(**message):
    base = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 123456789},
            "chat": {"id": 123456789},
        },
    }
    base["message"].update(message)
    return base


def test_telegram_ops_rejects_unauthorized_user():
    telegram = StubTelegram()
    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids={42},
        business_card_tool=lambda request: {},
        crm_lookup_tool=lambda request: {},
    )

    bot.handle_update(_message_update(text="find Ada"))

    assert telegram.messages == [("123456789", "Unauthorized user.")]


def test_telegram_ops_start_message_lists_capabilities():
    telegram = StubTelegram()
    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids={123456789},
        business_card_tool=lambda request: {},
        crm_lookup_tool=lambda request: {},
    )

    bot.handle_update(_message_update(text="/start"))

    assert "business card" in telegram.messages[0][1]
    assert "CRM lookup" in telegram.messages[0][1]


def test_telegram_ops_text_message_routes_to_crm_lookup():
    telegram = StubTelegram()
    seen: list[CrmLookupRequest] = []

    def lookup(request: CrmLookupRequest):
        seen.append(request)
        return {
            "result": {
                "contacts": [{"name": "Ada Lovelace", "email": "ada@example.com"}],
                "leads": [],
            }
        }

    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids={123456789},
        business_card_tool=lambda request: {},
        crm_lookup_tool=lookup,
    )

    bot.handle_update(_message_update(text="查 Ada 聯絡方式"))

    assert seen[0].query == "查 Ada 聯絡方式"
    assert seen[0].live is True
    assert "ada@example.com" in telegram.messages[0][1]


def test_telegram_ops_photo_routes_highest_resolution_to_business_card_tool():
    telegram = StubTelegram()
    seen: list[BusinessCardToolRequest] = []

    def business_card(request: BusinessCardToolRequest):
        seen.append(request)
        return {
            "contact": {"name": "Ada Lovelace", "email": "ada@example.com"},
            "external_refs": [{"system": "odoo", "external_id": "77", "metadata": {"kind": "contact"}}],
        }

    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids={123456789},
        business_card_tool=business_card,
        crm_lookup_tool=lambda request: {},
    )

    bot.handle_update(
        _message_update(
            photo=[
                {"file_id": "small", "file_size": 100},
                {"file_id": "large", "file_size": 500},
            ]
        )
    )

    assert telegram.downloaded == ["photos/large.jpg"]
    assert base64.b64decode(seen[0].image_base64.encode("ascii")) == b"card-bytes"
    assert seen[0].mime_type == "image/jpeg"
    assert seen[0].live is True
    assert "Ada Lovelace" in telegram.messages[0][1]


def test_telegram_ops_cli_entrypoint_is_registered():
    pyproject = tomllib.loads((REPO_ROOT / "agent_app" / "pyproject.toml").read_text())

    assert pyproject["project"]["scripts"]["deal-agent-telegram-ops"] == "deal_agent.telegram_ops_cli:main"


def test_telegram_ops_cli_retries_retryable_polling_errors():
    class PollingTelegram:
        def __init__(self) -> None:
            self.calls = 0

        def get_updates(self, *, offset=None, timeout=20):
            self.calls += 1
            if self.calls == 1:
                raise ConnectorError("temporary Telegram DNS failure", retryable=True)
            return [_message_update(text="/start")]

    class Bot:
        def __init__(self) -> None:
            self.handled = []

        def handle_update(self, update):
            self.handled.append(update)

    telegram = PollingTelegram()
    bot = Bot()

    telegram_ops_cli.run_poll_loop(
        telegram=telegram,
        bot=bot,
        sleep=lambda seconds: None,
        max_iterations=2,
    )

    assert telegram.calls == 2
    assert bot.handled[0]["message"]["text"] == "/start"
