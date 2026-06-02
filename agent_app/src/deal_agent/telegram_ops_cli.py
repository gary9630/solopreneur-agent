from __future__ import annotations

import sys
import time
from collections.abc import Callable, Sequence

from deal_agent.config import settings
from deal_agent.connectors.base import ConnectorError
from deal_agent.connectors.telegram import TelegramHttpConnector
from deal_agent.main import run_business_card_tool, run_crm_lookup_tool, run_meeting_audio_tool
from deal_agent.telegram_ops import TelegramOpsBot


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    missing = settings.missing_agent_telegram_config()
    if missing:
        print(f"missing Agent Telegram config: {', '.join(missing)}", file=sys.stderr)
        return 1

    telegram = TelegramHttpConnector(
        token=settings.agent_telegram_bot_token or "",
        chat_id=settings.agent_telegram_chat_id or "0",
    )
    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids=settings.agent_telegram_allowed_user_id_set(),
        business_card_tool=lambda request: run_business_card_tool(request, settings),
        crm_lookup_tool=lambda request: run_crm_lookup_tool(request, settings),
        meeting_audio_tool=lambda request: run_meeting_audio_tool(request, settings),
        max_message_chars=settings.meeting_audio_max_telegram_chars,
    )

    print("Agent Telegram ops bot polling started.")
    try:
        run_poll_loop(telegram=telegram, bot=bot)
    except KeyboardInterrupt:
        print("Agent Telegram ops bot stopped.")
        return 0


def run_poll_loop(
    *,
    telegram,
    bot,
    poll_timeout: int = 20,
    idle_sleep_seconds: float = 1,
    retry_sleep_seconds: float = 5,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
) -> None:
    offset = None
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            updates = telegram.get_updates(offset=offset, timeout=poll_timeout)
        except ConnectorError as exc:
            if not exc.retryable:
                raise
            print("Telegram polling hit a retryable connection error; retrying.", file=sys.stderr)
            sleep(retry_sleep_seconds)
            continue

        for update in updates:
            bot.handle_update(update)
            if update.get("update_id") is not None:
                offset = int(update["update_id"]) + 1
        sleep(idle_sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
