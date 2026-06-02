from __future__ import annotations

import base64
import shutil
import subprocess
from typing import Any, Protocol

from pydantic import Field, ValidationError

from deal_agent.models import StrictModel
from deal_agent.nim_client import NimClientError
from deal_agent.tool_models import MeetingMinutes, MeetingTranscript


class AudioTranscriptionClient(Protocol):
    model: str

    def transcribe_audio(
        self,
        audio_base64: str,
        mime_type: str,
        language_hint: str | None = None,
    ) -> Any:
        ...


class MinutesClient(Protocol):
    model: str

    def chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        ...


class AudioConverter(Protocol):
    def convert_to_wav(self, audio_bytes: bytes) -> bytes:
        ...


class MeetingAudioProcessingError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class MeetingAudioResult(StrictModel):
    run_id: str
    transcript: MeetingTranscript
    minutes: MeetingMinutes
    audio_model: str | None = None
    minutes_model: str | None = None
    warnings: list[str] = Field(default_factory=list)


class NoopAudioConverter:
    def convert_to_wav(self, audio_bytes: bytes) -> bytes:
        return audio_bytes


class FfmpegAudioConverter:
    def convert_to_wav(self, audio_bytes: bytes) -> bytes:
        if shutil.which("ffmpeg") is None:
            raise MeetingAudioProcessingError(
                "ffmpeg is required to convert Telegram voice audio",
                retryable=False,
            )
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-f",
                    "wav",
                    "pipe:1",
                ],
                input=audio_bytes,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise MeetingAudioProcessingError("audio conversion failed", retryable=False) from exc
        return result.stdout


class MeetingAudioProcessor:
    def __init__(
        self,
        *,
        audio_client: AudioTranscriptionClient,
        minutes_client: MinutesClient,
        converter: AudioConverter | None = None,
        minimum_confidence: float = 0.45,
    ) -> None:
        self._audio_client = audio_client
        self._minutes_client = minutes_client
        self._converter = converter or FfmpegAudioConverter()
        self._minimum_confidence = minimum_confidence

    def process(
        self,
        run_id: str,
        audio_base64: str,
        mime_type: str,
        filename: str | None = None,
        language_hint: str | None = None,
    ) -> MeetingAudioResult:
        prepared_base64, prepared_mime_type = self._prepare_audio(audio_base64, mime_type, filename)
        transcript = self._transcribe(prepared_base64, prepared_mime_type, language_hint)
        warnings = list(transcript.warnings)
        if transcript.confidence is not None and transcript.confidence < self._minimum_confidence:
            warnings.append("Transcript confidence was below threshold")
        minutes = self._generate_minutes(transcript)
        return MeetingAudioResult(
            run_id=run_id,
            transcript=transcript,
            minutes=minutes,
            audio_model=getattr(self._audio_client, "model", None),
            minutes_model=getattr(self._minutes_client, "model", None),
            warnings=warnings,
        )

    def _prepare_audio(
        self,
        audio_base64: str,
        mime_type: str,
        filename: str | None,
    ) -> tuple[str, str]:
        if not _requires_wav_conversion(mime_type, filename):
            return audio_base64, mime_type
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise MeetingAudioProcessingError("audio_base64 was not valid base64", retryable=False) from exc
        wav_bytes = self._converter.convert_to_wav(audio_bytes)
        return base64.b64encode(wav_bytes).decode("ascii"), "audio/wav"

    def _transcribe(
        self,
        audio_base64: str,
        mime_type: str,
        language_hint: str | None,
    ) -> MeetingTranscript:
        try:
            payload = self._audio_client.transcribe_audio(audio_base64, mime_type, language_hint)
            return MeetingTranscript.model_validate(payload)
        except NimClientError as exc:
            raise MeetingAudioProcessingError(str(exc), retryable=exc.retryable) from exc
        except ValidationError as exc:
            raise MeetingAudioProcessingError("Meeting transcript output failed validation", retryable=False) from exc

    def _generate_minutes(self, transcript: MeetingTranscript) -> MeetingMinutes:
        try:
            payload = self._minutes_client.chat_json(
                _minutes_system_prompt(),
                _minutes_user_prompt(transcript),
            )
            return MeetingMinutes.model_validate(payload)
        except NimClientError as exc:
            raise MeetingAudioProcessingError(str(exc), retryable=exc.retryable) from exc
        except ValidationError as exc:
            raise MeetingAudioProcessingError("Meeting minutes output failed validation", retryable=False) from exc


def _requires_wav_conversion(mime_type: str, filename: str | None) -> bool:
    normalized = mime_type.strip().lower()
    if normalized in {"audio/ogg", "audio/opus"}:
        return True
    return bool(filename and filename.strip().lower().endswith((".ogg", ".opus")))


def _minutes_system_prompt() -> str:
    return (
        "You write concise meeting minutes from transcripts. "
        "Return JSON only with keys language, summary, decisions, action_items, risks, follow_up. "
        "Use Traditional Chinese when the transcript is zh-TW or mixed. Use English when it is English."
    )


def _minutes_user_prompt(transcript: MeetingTranscript) -> str:
    return (
        f"Detected language: {transcript.language}\n"
        "Transcript:\n"
        f"{transcript.transcript}"
    )
