import base64

import pytest

from deal_agent.nim_client import NimClientError
from deal_agent.services.meeting_audio import (
    MeetingAudioProcessingError,
    MeetingAudioProcessor,
    NoopAudioConverter,
)


def test_meeting_audio_processor_transcribes_and_generates_minutes_in_zh_tw():
    class StubAudioClient:
        model = "audio-model"

        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            return {
                "language": "zh-TW",
                "transcript": "今天決議下週完成 Odoo demo。",
                "confidence": 0.9,
                "warnings": [],
            }

    class StubMinutesClient:
        model = "minutes-model"

        def chat_json(self, system_prompt, user_prompt):
            assert "今天決議下週完成 Odoo demo。" in user_prompt
            assert "Traditional Chinese" in system_prompt
            return {
                "language": "zh-TW",
                "summary": "討論 Odoo demo 時程。",
                "decisions": ["下週完成 Odoo demo"],
                "action_items": ["準備 demo 腳本"],
                "risks": [],
                "follow_up": ["確認上線時間"],
            }

    processor = MeetingAudioProcessor(
        audio_client=StubAudioClient(),
        minutes_client=StubMinutesClient(),
        converter=NoopAudioConverter(),
    )

    result = processor.process("run_1", "YXVkaW8=", "audio/wav")

    assert result.run_id == "run_1"
    assert result.transcript.transcript == "今天決議下週完成 Odoo demo。"
    assert result.minutes.summary == "討論 Odoo demo 時程。"
    assert result.audio_model == "audio-model"
    assert result.minutes_model == "minutes-model"


def test_meeting_audio_processor_converts_ogg_to_wav_before_transcription():
    class StubConverter:
        def __init__(self) -> None:
            self.seen = []

        def convert_to_wav(self, audio_bytes: bytes) -> bytes:
            self.seen.append(audio_bytes)
            return b"wav-bytes"

    class StubAudioClient:
        def __init__(self) -> None:
            self.calls = []

        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            self.calls.append((audio_base64, mime_type))
            return {
                "language": "en",
                "transcript": "We approved launch.",
                "confidence": 0.92,
                "warnings": [],
            }

    class StubMinutesClient:
        def chat_json(self, system_prompt, user_prompt):
            return {
                "language": "en",
                "summary": "Launch was approved.",
                "decisions": [],
                "action_items": [],
                "risks": [],
                "follow_up": [],
            }

    converter = StubConverter()
    audio_client = StubAudioClient()
    processor = MeetingAudioProcessor(
        audio_client=audio_client,
        minutes_client=StubMinutesClient(),
        converter=converter,
    )

    processor.process(
        "run_1",
        base64.b64encode(b"ogg-bytes").decode("ascii"),
        "audio/ogg",
    )

    assert converter.seen == [b"ogg-bytes"]
    assert audio_client.calls == [(base64.b64encode(b"wav-bytes").decode("ascii"), "audio/wav")]


def test_meeting_audio_processor_warns_on_low_confidence_with_usable_transcript():
    class StubAudioClient:
        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            return {
                "language": "en",
                "transcript": "Some words were unclear.",
                "confidence": 0.4,
                "warnings": ["background noise"],
            }

    class StubMinutesClient:
        def chat_json(self, system_prompt, user_prompt):
            return {
                "language": "en",
                "summary": "Audio was unclear.",
                "decisions": [],
                "action_items": [],
                "risks": [],
                "follow_up": [],
            }

    processor = MeetingAudioProcessor(
        audio_client=StubAudioClient(),
        minutes_client=StubMinutesClient(),
        converter=NoopAudioConverter(),
        minimum_confidence=0.8,
    )

    result = processor.process("run_1", "YXVkaW8=", "audio/wav")

    assert "background noise" in result.warnings
    assert "Transcript confidence was below threshold" in result.warnings


def test_meeting_audio_processor_rejects_empty_transcript():
    class StubAudioClient:
        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            return {
                "language": "en",
                "transcript": "   ",
                "confidence": 0.9,
                "warnings": [],
            }

    processor = MeetingAudioProcessor(
        audio_client=StubAudioClient(),
        minutes_client=object(),
        converter=NoopAudioConverter(),
    )

    with pytest.raises(MeetingAudioProcessingError) as exc_info:
        processor.process("run_1", "YXVkaW8=", "audio/wav")

    assert exc_info.value.retryable is False


def test_meeting_audio_processor_preserves_retryable_nim_errors():
    class StubAudioClient:
        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            raise NimClientError("temporary NIM failure", retryable=True)

    processor = MeetingAudioProcessor(
        audio_client=StubAudioClient(),
        minutes_client=object(),
        converter=NoopAudioConverter(),
    )

    with pytest.raises(MeetingAudioProcessingError) as exc_info:
        processor.process("run_1", "YXVkaW8=", "audio/wav")

    assert exc_info.value.retryable is True
