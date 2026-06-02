import base64
import json
import os
from pathlib import Path

import pytest

from deal_agent.live_factory import _normalize_nim_base_url
from deal_agent.nim_client import NimAudioClient, NimChatClient
from deal_agent.services.meeting_audio import MeetingAudioProcessor
from deal_agent.services.meeting_audio_eval import keyword_recall, normalized_error_rate


pytestmark = pytest.mark.live

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "audio"
DEFAULT_FIXTURE = FIXTURE_ROOT / "meeting_zh_tw_short.wav"
DEFAULT_EXPECTED = FIXTURE_ROOT / "meeting_zh_tw_short.expected.json"


def test_meeting_audio_live_transcription_quality():
    _skip_unless_audio_live_eval_enabled()
    if not DEFAULT_FIXTURE.exists():
        pytest.skip(f"missing live audio fixture: {DEFAULT_FIXTURE.relative_to(Path.cwd().parent)}")
    if not DEFAULT_EXPECTED.exists():
        pytest.skip(f"missing live audio expected transcript: {DEFAULT_EXPECTED.relative_to(Path.cwd().parent)}")

    expected = json.loads(DEFAULT_EXPECTED.read_text(encoding="utf-8"))
    audio_base64 = base64.b64encode(DEFAULT_FIXTURE.read_bytes()).decode("ascii")
    api_key = os.environ["NVIDIA_API_KEY"]
    base_url = _normalize_nim_base_url(os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    processor = MeetingAudioProcessor(
        audio_client=NimAudioClient(
            api_key=api_key,
            model=os.environ.get("NIM_AUDIO_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
            base_url=base_url,
        ),
        minutes_client=NimChatClient(
            api_key=api_key,
            model=os.environ.get("NIM_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            base_url=base_url,
        ),
    )

    result = processor.process("live_audio_eval", audio_base64, "audio/wav", language_hint=expected.get("language"))

    transcript = result.transcript.transcript
    assert transcript
    assert keyword_recall(transcript, expected.get("keywords", [])) >= expected.get("min_keyword_recall", 0.8)
    assert normalized_error_rate(expected.get("transcript", ""), transcript) <= expected.get(
        "max_normalized_error_rate",
        0.4,
    )


def _skip_unless_audio_live_eval_enabled() -> None:
    missing = []
    if os.environ.get("NVIDIA_AUDIO_LIVE_TEST") != "1":
        missing.append("NVIDIA_AUDIO_LIVE_TEST=1")
    if not os.environ.get("NVIDIA_API_KEY"):
        missing.append("NVIDIA_API_KEY")
    if missing:
        pytest.skip("missing live meeting audio requirements: " + ", ".join(missing))
