# Telegram Meeting Audio Design

## Goal

Add a Telegram audio workflow for the Agent App bot:

1. The operator sends a Telegram voice note or audio file.
2. The bot transcribes the recording and sends the transcript back to the user.
3. The bot sends a second message with meeting minutes generated from the transcript.

The workflow must support Traditional Chinese and English, keep live model calls gated by configuration, and include a repeatable accuracy check for transcription quality.

## Source Constraints

The feature relies on NVIDIA-hosted models and keeps credentials in `agent_app`.

- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` is the primary transcription candidate because NVIDIA Build lists it as an audio-capable omni model and documents transcription-oriented use.
- `nvidia/nemotron-3-super-120b-a12b` remains the meeting-minutes model because the project already uses it for text reasoning and it supports Chinese and English.
- NVIDIA audio/video requests should use `/no_think` for direct transcription-style tasks.
- Inline audio is only appropriate for small payloads. Larger audio uses NVCF asset upload before invoking the model.
- The OpenClaw tool update must follow the supported NemoClaw path: plugin code is baked into the sandbox image, while `SKILL.md` teaches workflow behavior and does not register tools.

References:

- https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning/modelcard
- https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-nano-omni-30b-a3b-reasoning-infer
- https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard
- `reference-works/NemoClaw/docs/deployment/install-openclaw-plugins.mdx`

## Scope

### In Scope

- Telegram `voice` messages, usually `ogg/opus`.
- Telegram `audio` messages with `mp3`, `wav`, or `ogg`.
- Telegram `document` messages when the MIME type or filename is an accepted audio type.
- Conversion from `ogg/opus` to `wav` before model submission.
- Transcript and minutes delivery as separate Telegram messages.
- Long Telegram responses split into safe message chunks.
- Mocked tests for routing, conversion, NIM payloads, asset upload, transcript parsing, minutes prompts, and Telegram response splitting.
- Opt-in live transcription accuracy evaluation with fixture audio and expected transcript text.

### Out Of Scope For V1

- Speaker diarization and speaker identity assignment.
- Public webhook setup. Local polling remains the demo path.
- Translation. The transcript preserves the spoken language.
- Storing transcripts or minutes in Odoo or a database.
- Audio summarization before full transcription.

## Architecture

### Telegram Input Layer

`TelegramOpsBot` gains audio routing after authorization:

- `/start` describes business-card capture, CRM lookup, and meeting audio.
- `photo` continues to route to business-card capture.
- `voice`, `audio`, and supported audio `document` route to meeting audio.
- Plain text continues to route to CRM lookup.

The bot downloads the Telegram file through the existing `TelegramHttpConnector`.
It creates a `MeetingAudioToolRequest` with:

- `run_id`: `telegram_audio_<message_id>`
- `audio_base64`
- `mime_type`
- `filename`
- `source`: `voice`, `audio`, or `document`
- `live=True`

The bot sends:

1. Transcript message, chunked as needed.
2. Meeting minutes message, chunked as needed.

### Audio Processing Layer

Add `MeetingAudioProcessor` in `agent_app/src/deal_agent/services/meeting_audio.py`.

Responsibilities:

- Validate supported MIME types and filenames.
- Convert `ogg/opus` to `wav`.
- Call the audio transcription client.
- Validate transcript output.
- Call the text model to produce meeting minutes.
- Return a typed result to both FastAPI and Telegram bot callers.

Conversion uses `ffmpeg` when needed. If `ffmpeg` is unavailable, the processor returns a non-retryable error explaining the missing dependency. The implementation should not silently send unsupported `ogg/opus` to the model.

### NIM Client Layer

Add `NimAudioClient` in `agent_app/src/deal_agent/nim_client.py`.

Methods:

- `transcribe_audio(audio_base64, mime_type, language_hint=None) -> Any`
- Internal helper for inline content when the encoded payload is below the configured threshold.
- Internal helper for NVCF asset upload when the payload is too large.

Default audio model:

```text
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
```

Prompt contract:

```text
/no_think
Transcribe this meeting audio. Return JSON only:
{
  "language": "zh-TW" | "en" | "mixed" | "unknown",
  "transcript": "...",
  "confidence": 0.0-1.0,
  "warnings": ["..."]
}
Preserve the spoken language. Do not translate.
Use Traditional Chinese for Chinese speech.
```

### Meeting Minutes Layer

Use `NimChatClient` with `NIM_MODEL`, defaulting to `nvidia/nemotron-3-super-120b-a12b`.

Prompt contract:

- Input: transcript plus detected language.
- Output: JSON with `language`, `summary`, `decisions`, `action_items`, `risks`, and `follow_up`.
- If transcript language is `zh-TW`, output Traditional Chinese.
- If transcript language is `en`, output English.
- If transcript language is `mixed`, output primarily Traditional Chinese while preserving important English names and technical terms.

The Telegram response formats JSON into readable text rather than sending raw JSON.

## Tool Gateway Surface

Add:

```text
POST /tools/meeting/audio
```

Request:

```json
{
  "run_id": "telegram_audio_123",
  "audio_base64": "...",
  "mime_type": "audio/ogg",
  "filename": "voice.ogg",
  "source": "voice",
  "language_hint": "zh-TW",
  "live": true
}
```

Dry-run behavior:

- If `live=false` or `LIVE_WORKFLOW_ENABLED=0`, return planned actions and no model calls.

Live behavior:

- Require `NVIDIA_API_KEY`.
- Require `NIM_AUDIO_MODEL` or use the default omni model.
- Require `NIM_MODEL` or use the default super model.
- Return transcript, minutes, model names, and warnings.

## OpenClaw Plugin And Skill Updates

Add a first-class plugin tool:

```text
meeting_audio_process
```

The tool calls `POST /tools/meeting/audio` through the existing host gateway base URL. It is useful for OpenClaw-initiated processing, but the local Telegram bot can call the same FastAPI route directly.

Update:

- `openclaw_plugins/solopreneur-tools/openclaw.plugin.json`
- `openclaw_plugins/solopreneur-tools/dist/index.js`
- `skills/deal-to-delivery/SKILL.md`
- `workspace/TOOLS.md`

The gateway policy already allows `POST /tools/**` to `host.openshell.internal:8088`, so no new NemoClaw network preset is required unless the implementation makes sandbox-side calls to NVIDIA. V1 keeps NVIDIA credentials and calls host-side in `agent_app`.

## Configuration

New env vars:

```text
NIM_AUDIO_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
NIM_AUDIO_INLINE_MAX_BYTES=180000
MEETING_AUDIO_MIN_CONFIDENCE=0.45
MEETING_AUDIO_MAX_TELEGRAM_CHARS=3900
```

Existing env vars:

```text
NVIDIA_API_KEY
NIM_BASE_URL
NIM_MODEL
LIVE_WORKFLOW_ENABLED
AGENT_TELEGRAM_BOT_TOKEN
AGENT_TELEGRAM_ALLOWED_USER_IDS
```

## Error Handling

- Unauthorized Telegram users receive the existing refusal and no file is downloaded.
- Unsupported audio types produce a concise Telegram error.
- Missing `ffmpeg` produces a setup error.
- Low-confidence transcripts still return the transcript only if it has usable text, but include warnings and mark confidence. If no usable text exists, return a non-retryable error.
- Retryable NIM/network errors bubble up as retryable service errors.
- Telegram message splitting must preserve order: transcript chunks first, minutes chunks second.

## Accuracy Evaluation

Add an opt-in live eval test:

```text
NVIDIA_AUDIO_LIVE_TEST=1
NVIDIA_API_KEY=...
NIM_AUDIO_MODEL=...
```

Fixtures:

- `agent_app/tests/fixtures/audio/meeting_zh_tw_short.wav`
- `agent_app/tests/fixtures/audio/meeting_en_short.wav`
- Expected transcripts or keyword sets in text/JSON files.

Metrics:

- Word error rate for English.
- Character or token-level error rate for Traditional Chinese.
- Keyword recall for both languages.

The live eval should not claim model quality from a single sample. It is a regression guard and a demo confidence check.

## Acceptance Criteria

- Sending a Telegram voice note results in transcript and meeting minutes messages.
- Sending `mp3` or `wav` audio document results in transcript and meeting minutes messages.
- Unsupported documents do not route to the meeting audio workflow.
- Transcript model requests use the audio model and `/no_think`.
- Meeting minutes requests use the transcript text and the text model.
- Traditional Chinese transcripts produce Traditional Chinese minutes.
- English transcripts produce English minutes.
- `uv run pytest -q` passes with mocked tests.
- Live audio eval remains skipped unless explicitly opted in.
