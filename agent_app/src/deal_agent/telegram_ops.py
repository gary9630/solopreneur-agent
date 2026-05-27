from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any, Protocol

from deal_agent.tool_models import BusinessCardToolRequest, CrmLookupRequest


class TelegramOpsConnector(Protocol):
    def send_message(self, chat_id: str, text: str) -> Any:
        ...

    def get_file(self, file_id: str) -> dict[str, Any]:
        ...

    def download_file(self, file_path: str) -> bytes:
        ...


BusinessCardTool = Callable[[BusinessCardToolRequest], dict[str, Any]]
CrmLookupTool = Callable[[CrmLookupRequest], dict[str, Any]]


class TelegramOpsBot:
    def __init__(
        self,
        *,
        telegram: TelegramOpsConnector,
        allowed_user_ids: set[int],
        business_card_tool: BusinessCardTool,
        crm_lookup_tool: CrmLookupTool,
    ) -> None:
        self._telegram = telegram
        self._allowed_user_ids = allowed_user_ids
        self._business_card_tool = business_card_tool
        self._crm_lookup_tool = crm_lookup_tool

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return

        chat_id = _chat_id(message)
        user_id = _user_id(message)
        if user_id not in self._allowed_user_ids:
            self._telegram.send_message(chat_id, "Unauthorized user.")
            return

        text = message.get("text")
        if isinstance(text, str) and text.strip() == "/start":
            self._telegram.send_message(
                chat_id,
                "Solopreneur Ops Agent ready: send a business card photo or ask for a CRM lookup.",
            )
            return

        photos = message.get("photo")
        if isinstance(photos, list) and photos:
            self._handle_photo(chat_id, message)
            return

        if isinstance(text, str) and text.strip():
            self._handle_lookup(chat_id, text)

    def _handle_photo(self, chat_id: str, message: dict[str, Any]) -> None:
        photo = max(message["photo"], key=lambda item: item.get("file_size", 0))
        file_info = self._telegram.get_file(str(photo["file_id"]))
        file_path = str(file_info["file_path"])
        image_bytes = self._telegram.download_file(file_path)
        request = BusinessCardToolRequest(
            run_id=f"telegram_card_{message['message_id']}",
            image_base64=base64.b64encode(image_bytes).decode("ascii"),
            mime_type=_mime_type_for_file(file_path),
            live=True,
        )
        result = self._business_card_tool(request)
        contact = result.get("contact", {})
        refs = result.get("external_refs", [])
        ref_text = ", ".join(f"{ref.get('system')}:{ref.get('external_id')}" for ref in refs) or "no refs"
        self._telegram.send_message(
            chat_id,
            f"Business card captured: {contact.get('name') or 'unknown'} "
            f"{contact.get('email') or ''}. Refs: {ref_text}.",
        )

    def _handle_lookup(self, chat_id: str, text: str) -> None:
        result = self._crm_lookup_tool(CrmLookupRequest(query=text, live=True))
        lookup = result.get("result", {})
        contacts = lookup.get("contacts", [])
        if contacts:
            first = contacts[0]
            self._telegram.send_message(
                chat_id,
                f"CRM contact: {first.get('name') or 'unknown'} "
                f"{first.get('email') or ''} {first.get('phone') or ''}".strip(),
            )
            return
        self._telegram.send_message(chat_id, "No CRM contact found.")


def _chat_id(message: dict[str, Any]) -> str:
    chat = message.get("chat")
    if isinstance(chat, dict) and chat.get("id") is not None:
        return str(chat["id"])
    return ""


def _user_id(message: dict[str, Any]) -> int | None:
    sender = message.get("from")
    if isinstance(sender, dict) and sender.get("id") is not None:
        return int(sender["id"])
    return None


def _mime_type_for_file(file_path: str) -> str:
    lowered = file_path.lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
