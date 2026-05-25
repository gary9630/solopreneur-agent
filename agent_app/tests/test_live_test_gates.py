import importlib.util
from pathlib import Path


TELEGRAM_LIVE_TEST_PATH = Path(__file__).parent / "live" / "test_telegram_live.py"


def _load_telegram_live_test_module():
    spec = importlib.util.spec_from_file_location(
        "telegram_live_test_module",
        TELEGRAM_LIVE_TEST_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_telegram_live_gate_requires_explicit_send_opt_in(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.delenv("TELEGRAM_LIVE_SEND", raising=False)

    module = _load_telegram_live_test_module()

    assert module._missing_telegram_live_requirements() == ["TELEGRAM_LIVE_SEND=1"]
