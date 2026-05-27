import os

import pytest

from deal_agent.nim_client import NimChatClient

pytestmark = pytest.mark.live

REQUIRED_ENV = ("NVIDIA_API_KEY", "NIM_MODEL")
NIM_BASE_URL = "https://integrate.api.nvidia.com"


def test_nim_chat_client_returns_minimal_json():
    _skip_unless_env(REQUIRED_ENV)

    client = NimChatClient(
        api_key=os.environ["NVIDIA_API_KEY"],
        model=os.environ["NIM_MODEL"],
        base_url=_nim_base_url(),
    )

    result = client.chat_json(
        "Return only valid compact JSON. Do not include markdown.",
        'Return exactly {"ok": true} as JSON.',
    )

    assert result == {"ok": True}


def _nim_base_url() -> str:
    base_url = os.getenv("NIM_BASE_URL", NIM_BASE_URL).rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[: -len("/v1")]
    return base_url


def _skip_unless_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if _missing_or_placeholder(name)]
    if missing:
        pytest.skip(f"missing live NIM env vars: {', '.join(missing)}")


def _missing_or_placeholder(name: str) -> bool:
    value = os.getenv(name)
    return not value or value.startswith("replace-with-")
