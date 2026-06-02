from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any, Protocol

from deal_agent.tool_models import BusinessCardToolRequest, CrmLookupRequest, MeetingAudioToolRequest


class TelegramOpsConnector(Protocol):
    def send_message(self, chat_id: str, text: str) -> Any:
        ...

    def get_file(self, file_id: str) -> dict[str, Any]:
        ...

    def download_file(self, file_path: str) -> bytes:
        ...


BusinessCardTool = Callable[[BusinessCardToolRequest], dict[str, Any]]
CrmLookupTool = Callable[[CrmLookupRequest], dict[str, Any]]
MeetingAudioTool = Callable[[MeetingAudioToolRequest], dict[str, Any]]


class TelegramOpsBot:
    def __init__(
        self,
        *,
        telegram: TelegramOpsConnector,
        allowed_user_ids: set[int],
        business_card_tool: BusinessCardTool,
        crm_lookup_tool: CrmLookupTool,
        meeting_audio_tool: MeetingAudioTool,
        max_message_chars: int = 3900,
    ) -> None:
        self._telegram = telegram
        self._allowed_user_ids = allowed_user_ids
        self._business_card_tool = business_card_tool
        self._crm_lookup_tool = crm_lookup_tool
        self._meeting_audio_tool = meeting_audio_tool
        self._max_message_chars = max(1, max_message_chars)

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
                "Solopreneur Ops Agent ready: send a business card photo, meeting audio, or ask for a CRM lookup.",
            )
            return

        photos = message.get("photo")
        if isinstance(photos, list) and photos:
            self._handle_photo(chat_id, message)
            return

        audio_payload = _audio_payload(message)
        if audio_payload is not None:
            self._handle_audio(chat_id, message, audio_payload)
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

    def _handle_audio(
        self,
        chat_id: str,
        message: dict[str, Any],
        audio_payload: tuple[str, str, str | None, str],
    ) -> None:
        file_id, mime_type, filename, source = audio_payload
        file_info = self._telegram.get_file(file_id)
        file_path = str(file_info["file_path"])
        audio_bytes = self._telegram.download_file(file_path)
        request = MeetingAudioToolRequest(
            run_id=f"telegram_audio_{message['message_id']}",
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            mime_type=mime_type,
            filename=filename or file_path.rsplit("/", 1)[-1],
            source=source,
            live=True,
        )
        result = self._meeting_audio_tool(request)
        self._send_chunked(chat_id, _format_transcript(result))
        self._send_chunked(chat_id, _format_minutes(result))

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

    def _send_chunked(self, chat_id: str, text: str) -> None:
        for chunk in _chunk_text(text, self._max_message_chars):
            self._telegram.send_message(chat_id, chunk)


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


def _audio_payload(message: dict[str, Any]) -> tuple[str, str, str | None, str] | None:
    voice = message.get("voice")
    if isinstance(voice, dict) and voice.get("file_id"):
        return str(voice["file_id"]), str(voice.get("mime_type") or "audio/ogg"), None, "voice"

    audio = message.get("audio")
    if isinstance(audio, dict) and audio.get("file_id"):
        mime_type = str(audio.get("mime_type") or _mime_type_for_audio_file(str(audio.get("file_name") or "")))
        filename = str(audio["file_name"]) if audio.get("file_name") else None
        if _is_supported_audio(mime_type, filename):
            return str(audio["file_id"]), mime_type, filename, "audio"

    document = message.get("document")
    if isinstance(document, dict) and document.get("file_id"):
        mime_type = str(document.get("mime_type") or _mime_type_for_audio_file(str(document.get("file_name") or "")))
        filename = str(document["file_name"]) if document.get("file_name") else None
        if _is_supported_audio(mime_type, filename):
            return str(document["file_id"]), mime_type, filename, "document"
    return None


def _is_supported_audio(mime_type: str | None, filename: str | None) -> bool:
    normalized = (mime_type or "").strip().lower()
    if normalized in {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/ogg", "audio/opus"}:
        return True
    lowered = (filename or "").strip().lower()
    return lowered.endswith((".wav", ".mp3", ".ogg", ".opus"))


def _mime_type_for_audio_file(file_path: str) -> str:
    lowered = file_path.lower()
    if lowered.endswith(".wav"):
        return "audio/wav"
    if lowered.endswith(".mp3"):
        return "audio/mpeg"
    if lowered.endswith((".ogg", ".opus")):
        return "audio/ogg"
    return "application/octet-stream"


def _format_transcript(result: dict[str, Any]) -> str:
    transcript = result.get("transcript", {})
    if not isinstance(transcript, dict):
        transcript = {}
    text = str(transcript.get("transcript") or "")
    language = transcript.get("language")
    confidence = transcript.get("confidence")
    lines = ["逐字稿 / Transcript"]
    if language:
        lines.append(f"Language: {language}")
    if confidence is not None:
        lines.append(f"Confidence: {confidence}")
    lines.extend(["", text])
    warnings = result.get("warnings") or transcript.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.extend(["", "Warnings:", *[str(warning) for warning in warnings]])
    return "\n".join(lines).strip()


def _format_minutes(result: dict[str, Any]) -> str:
    minutes = result.get("minutes", {})
    if not isinstance(minutes, dict):
        minutes = {}
    lines = ["會議紀要 / Meeting Minutes", "", str(minutes.get("summary") or "")]
    _append_list(lines, "Decisions", minutes.get("decisions"))
    _append_list(lines, "Action Items", minutes.get("action_items"))
    _append_list(lines, "Risks", minutes.get("risks"))
    _append_list(lines, "Follow Up", minutes.get("follow_up"))
    return "\n".join(line for line in lines if line is not None).strip()


def _append_list(lines: list[str], label: str, values: Any) -> None:
    if not isinstance(values, list) or not values:
        return
    lines.extend(["", f"{label}:"])
    lines.extend(f"- {value}" for value in values)


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[index:index + max_chars] for index in range(0, len(text), max_chars)]
