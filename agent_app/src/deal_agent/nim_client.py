from __future__ import annotations

import json
from typing import Any

import httpx


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
        response.raise_for_status()

        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("NIM response did not include chat content") from exc

        try:
            return json.loads(_strip_markdown_json_fence(content))
        except json.JSONDecodeError as exc:
            raise ValueError("NIM response content was not valid JSON") from exc


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
