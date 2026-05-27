from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})


class NimClientError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class NimClientResponseError(NimClientError):
    def __init__(self, message: str, *, status_code: int, retryable: bool) -> None:
        super().__init__(message, retryable=retryable)
        self.status_code = status_code


class NimChatClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")

        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30.0)

    def __repr__(self) -> str:
        return f"NimChatClient(model={self.model!r}, base_url={self.base_url!r})"

    def chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        try:
            response = self._http_client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                },
            )
        except httpx.RequestError as exc:
            raise NimClientError("NIM request failed before receiving a response", retryable=True) from exc

        if response.status_code >= 400:
            raise NimClientResponseError(
                "NIM request failed",
                status_code=response.status_code,
                retryable=_is_retryable_status(response.status_code),
            )

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM response body was not valid JSON") from exc

        content = _extract_chat_content(payload, response.status_code)
        try:
            return json.loads(_strip_markdown_json_fence(content))
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM response content was not valid JSON") from exc


class NimVisionClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")

        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30.0)

    def __repr__(self) -> str:
        return f"NimVisionClient(model={self.model!r}, base_url={self.base_url!r})"

    def extract_business_card(self, image_base64: str, mime_type: str) -> Any:
        data_url = f"data:{mime_type};base64,{image_base64}"
        try:
            response = self._http_client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract business card fields. Return JSON only with keys: "
                                        "name, company, title, email, phone, website, raw_text, confidence."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        }
                    ],
                    "temperature": 0,
                },
            )
        except httpx.RequestError as exc:
            raise NimClientError("NIM vision request failed before receiving a response", retryable=True) from exc

        if response.status_code >= 400:
            raise NimClientResponseError(
                "NIM vision request failed",
                status_code=response.status_code,
                retryable=_is_retryable_status(response.status_code),
            )

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM vision response body was not valid JSON") from exc

        content = _extract_chat_content(payload, response.status_code)
        try:
            return json.loads(_strip_markdown_json_fence(content))
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM vision content was not valid JSON") from exc


def _is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def _malformed_response(status_code: int, message: str) -> NimClientResponseError:
    return NimClientResponseError(message, status_code=status_code, retryable=False)


def _extract_chat_content(payload: Any, status_code: int) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise _malformed_response(status_code, "NIM response did not include chat content") from exc

    if not isinstance(content, str):
        raise _malformed_response(status_code, "NIM response chat content was not a string")
    return content


def _strip_markdown_json_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
