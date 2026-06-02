from __future__ import annotations

import base64
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


class NimAudioClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com",
        inline_max_bytes: int = 180000,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")
        if inline_max_bytes < 1:
            raise ValueError("inline_max_bytes must be positive")

        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.inline_max_bytes = inline_max_bytes
        self._http_client = http_client or httpx.Client(timeout=60.0)

    def __repr__(self) -> str:
        return f"NimAudioClient(model={self.model!r}, base_url={self.base_url!r})"

    def transcribe_audio(
        self,
        audio_base64: str,
        mime_type: str,
        language_hint: str | None = None,
    ) -> Any:
        audio_bytes = _decode_base64_audio(audio_base64)
        audio_format = _audio_format(mime_type)
        if len(audio_bytes) <= self.inline_max_bytes:
            audio_tag = f'<audio src="data:audio/{audio_format};base64,{audio_base64}" />'
        else:
            asset_id = self._upload_asset(audio_bytes, mime_type)
            audio_tag = f'<audio src="data:audio/{audio_format};asset_id,{asset_id}" />'
        return self._chat_audio(audio_tag, language_hint)

    def _upload_asset(self, audio_bytes: bytes, mime_type: str) -> str:
        try:
            create_response = self._http_client.post(
                "https://api.nvcf.nvidia.com/v2/nvcf/assets",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"contentType": mime_type, "description": "meeting audio"},
            )
        except httpx.RequestError as exc:
            raise NimClientError("NVCF asset creation failed before receiving a response", retryable=True) from exc

        if create_response.status_code >= 400:
            raise NimClientResponseError(
                "NVCF asset creation failed",
                status_code=create_response.status_code,
                retryable=_is_retryable_status(create_response.status_code),
            )

        try:
            asset_payload = create_response.json()
        except JSONDecodeError as exc:
            raise _malformed_response(create_response.status_code, "NVCF asset response body was not valid JSON") from exc

        asset_id = _required_string(asset_payload, "assetId", create_response.status_code, "NVCF asset")
        upload_url = _required_string(asset_payload, "uploadUrl", create_response.status_code, "NVCF asset")

        try:
            upload_response = self._http_client.put(
                upload_url,
                headers={
                    "Content-Type": mime_type,
                    "x-amz-meta-nvcf-asset-description": "meeting audio",
                },
                content=audio_bytes,
            )
        except httpx.RequestError as exc:
            raise NimClientError("NVCF asset upload failed before receiving a response", retryable=True) from exc

        if upload_response.status_code >= 400:
            raise NimClientResponseError(
                "NVCF asset upload failed",
                status_code=upload_response.status_code,
                retryable=_is_retryable_status(upload_response.status_code),
            )
        return asset_id

    def _chat_audio(self, audio_tag: str, language_hint: str | None) -> Any:
        prompt = (
            "/no_think\n"
            "Transcribe this meeting audio. Return JSON only with keys: "
            "language, transcript, confidence, warnings. Preserve spoken language. "
            "Use Traditional Chinese for Chinese speech."
        )
        if language_hint:
            prompt = f"{prompt} Language hint: {language_hint}."
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
                            "content": f"{prompt}\n{audio_tag}",
                        }
                    ],
                    "temperature": 0,
                },
            )
        except httpx.RequestError as exc:
            raise NimClientError("NIM audio request failed before receiving a response", retryable=True) from exc

        if response.status_code >= 400:
            raise NimClientResponseError(
                "NIM audio request failed",
                status_code=response.status_code,
                retryable=_is_retryable_status(response.status_code),
            )

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM audio response body was not valid JSON") from exc

        content = _extract_chat_content(payload, response.status_code)
        try:
            return json.loads(_strip_markdown_json_fence(content))
        except JSONDecodeError as exc:
            raise _malformed_response(response.status_code, "NIM audio content was not valid JSON") from exc


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


def _decode_base64_audio(audio_base64: str) -> bytes:
    try:
        return base64.b64decode(audio_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise NimClientError("audio_base64 was not valid base64", retryable=False) from exc


def _audio_format(mime_type: str) -> str:
    normalized = mime_type.strip().lower()
    if normalized in {"audio/wav", "audio/x-wav"}:
        return "wav"
    if normalized in {"audio/mpeg", "audio/mp3"}:
        return "mp3"
    if normalized in {"audio/ogg", "audio/opus"}:
        return "ogg"
    return normalized.removeprefix("audio/") or "wav"


def _required_string(payload: Any, key: str, status_code: int, label: str) -> str:
    if not isinstance(payload, dict):
        raise _malformed_response(status_code, f"{label} response was not an object")
    value = payload.get(key)
    if value is None:
        raise _malformed_response(status_code, f"{label} response did not include {key}")
    return str(value)
