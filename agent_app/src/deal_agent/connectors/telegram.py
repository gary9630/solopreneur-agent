from __future__ import annotations

from typing import Any

import httpx

from deal_agent.connectors.base import ConnectorError, is_retryable_status, request_json
from deal_agent.models import ExternalRef


class TelegramHttpConnector:
    def __init__(
        self,
        *,
        token: str,
        chat_id: str,
        base_url: str = "https://api.telegram.org",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not token:
            raise ValueError("token is required")
        if not chat_id:
            raise ValueError("chat_id is required")

        self.chat_id = chat_id
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._http_client = http_client or httpx.Client(timeout=30.0)
        self._message_refs: dict[tuple[str, str], ExternalRef] = {}

    def __repr__(self) -> str:
        return f"TelegramHttpConnector(base_url={self.base_url!r}, chat_id={self.chat_id!r})"

    def send_status(self, run_id: str, message: str) -> ExternalRef:
        cache_key = (run_id, message)
        if cache_key in self._message_refs:
            return _copy_ref(self._message_refs[cache_key])

        result = self.send_message(self.chat_id, message)

        external_id = _required_string(result, "message_id")
        chat_id = self.chat_id
        chat = result.get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            chat_id = str(chat["id"])

        ref = ExternalRef(
            system="telegram",
            external_id=external_id,
            metadata={"kind": "message", "run_id": run_id, "chat_id": chat_id},
        )
        self._message_refs[cache_key] = ref
        return _copy_ref(ref)

    def send_message(self, chat_id: str, text: str) -> dict[str, Any]:
        payload = request_json(
            self._http_client,
            "Telegram",
            f"{self.base_url}/bot{self._token}/sendMessage",
            headers={"Content-Type": "application/json"},
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        return _telegram_result(payload)

    def get_updates(self, *, offset: int | None = None, timeout: int = 20) -> list[dict[str, Any]]:
        payload = request_json(
            self._http_client,
            "Telegram",
            f"{self.base_url}/bot{self._token}/getUpdates",
            headers={"Content-Type": "application/json"},
            json=_drop_none({"offset": offset, "timeout": timeout}),
        )
        result = _telegram_result(payload)
        if not isinstance(result, list):
            raise ConnectorError("Telegram getUpdates result was not a list", retryable=False, status_code=200)
        return result

    def get_file(self, file_id: str) -> dict[str, Any]:
        payload = request_json(
            self._http_client,
            "Telegram",
            f"{self.base_url}/bot{self._token}/getFile",
            headers={"Content-Type": "application/json"},
            json={"file_id": file_id},
        )
        result = _telegram_result(payload)
        if not isinstance(result, dict):
            raise ConnectorError("Telegram getFile result was not an object", retryable=False, status_code=200)
        return result

    def download_file(self, file_path: str) -> bytes:
        try:
            response = self._http_client.get(f"{self.base_url}/file/bot{self._token}/{file_path}")
        except httpx.RequestError:
            raise ConnectorError("Telegram file download failed before receiving a response", retryable=True) from None
        if response.status_code >= 400:
            raise ConnectorError(
                "Telegram file download failed",
                retryable=is_retryable_status(response.status_code),
                status_code=response.status_code,
            )
        return response.content


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise ConnectorError(f"Telegram response did not include {key}", retryable=False, status_code=200)
    return str(value)


def _telegram_result(payload: dict[str, Any]) -> Any:
    if payload.get("ok") is not True:
        raise ConnectorError("Telegram request was not accepted", retryable=False, status_code=200)
    if "result" not in payload:
        raise ConnectorError("Telegram response did not include a result", retryable=False, status_code=200)
    return payload["result"]


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _copy_ref(ref: ExternalRef) -> ExternalRef:
    return ref.model_copy(deep=True)
