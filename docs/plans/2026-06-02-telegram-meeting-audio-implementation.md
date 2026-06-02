# Telegram Meeting Audio Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add complete Telegram meeting-audio support: voice/audio uploads are transcribed with NVIDIA omni audio, summarized into meeting minutes with Nemotron Super, and returned to the Telegram user as separate messages.

**Architecture:** Keep all NVIDIA credentials and model calls in `agent_app`. Add a typed meeting-audio service shared by FastAPI and the Telegram ops bot. OpenClaw gets a first-class plugin tool that calls the existing host gateway, while the Telegram bot can invoke the same route directly.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Telegram Bot API, ffmpeg CLI, NVIDIA NIM chat completions, NVCF asset upload, NemoClaw/OpenClaw plugin assets.

---

### Task 1: Meeting Audio Config And Models

**Files:**
- Modify: `agent_app/src/deal_agent/config.py`
- Modify: `agent_app/src/deal_agent/tool_models.py`
- Test: `agent_app/tests/test_tool_models.py`

**Step 1: Write the failing tests**

Add tests to `agent_app/tests/test_tool_models.py`:

```python
def test_meeting_audio_request_strips_fields_and_defaults_to_dry_run():
    request = MeetingAudioToolRequest(
        run_id="  audio_1  ",
        audio_base64="  Ynl0ZXM=  ",
        mime_type="  audio/ogg  ",
        filename="  voice.ogg  ",
        source="voice",
    )

    assert request.run_id == "audio_1"
    assert request.audio_base64 == "Ynl0ZXM="
    assert request.mime_type == "audio/ogg"
    assert request.filename == "voice.ogg"
    assert request.source == "voice"
    assert request.live is False


def test_meeting_audio_settings_defaults_are_safe():
    settings = Settings()

    assert settings.nim_audio_model == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert settings.nim_audio_inline_max_bytes == 180000
    assert settings.meeting_audio_min_confidence == 0.45
    assert settings.meeting_audio_max_telegram_chars == 3900
```

Import `MeetingAudioToolRequest` and `Settings`.

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_tool_models.py::test_meeting_audio_request_strips_fields_and_defaults_to_dry_run tests/test_tool_models.py::test_meeting_audio_settings_defaults_are_safe -v
```

Expected: fail because `MeetingAudioToolRequest` and new settings do not exist.

**Step 3: Implement minimal code**

In `config.py`, add:

```python
nim_audio_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
nim_audio_inline_max_bytes: int = 180000
meeting_audio_min_confidence: float = 0.45
meeting_audio_max_telegram_chars: int = 3900
```

In `tool_models.py`, add:

```python
from typing import Literal


class MeetingAudioToolRequest(StrictModel):
    run_id: NonBlankStr
    audio_base64: NonBlankStr
    mime_type: NonBlankStr
    filename: CleanStr | None = None
    source: Literal["voice", "audio", "document"] = "audio"
    language_hint: CleanStr | None = None
    live: bool = False


class MeetingTranscript(StrictModel):
    language: CleanStr = "unknown"
    transcript: NonBlankStr
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class MeetingMinutes(StrictModel):
    language: CleanStr = "unknown"
    summary: NonBlankStr
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)
```

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_tool_models.py -v
```

Expected: all tests pass.

---

### Task 2: NIM Audio Client For Inline And Asset Audio

**Files:**
- Modify: `agent_app/src/deal_agent/nim_client.py`
- Test: `agent_app/tests/test_meeting_audio_client.py`

**Step 1: Write the failing tests**

Create `agent_app/tests/test_meeting_audio_client.py`.

Test inline audio:

```python
def test_nim_audio_client_posts_inline_audio_and_parses_json():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://nim.test/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        seen.append(payload)
        assert payload["model"] == "nvidia/audio-test"
        assert "/no_think" in payload["messages"][0]["content"]
        assert '<audio src="data:audio/wav;base64,YXVkaW8="' in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({
                "language": "zh-TW",
                "transcript": "今天討論產品上線計畫。",
                "confidence": 0.91,
                "warnings": [],
            })}}]},
        )

    client = NimAudioClient(
        api_key="test-secret",
        model="nvidia/audio-test",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.transcribe_audio("YXVkaW8=", "audio/wav")

    assert result["language"] == "zh-TW"
    assert seen[0]["temperature"] == 0
```

Test asset upload:

```python
def test_nim_audio_client_uploads_large_audio_as_nvcf_asset():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://api.nvcf.nvidia.com/v2/nvcf/assets":
            return httpx.Response(
                200,
                json={
                    "assetId": "asset-123",
                    "uploadUrl": "https://upload.test/asset-123",
                    "contentType": "audio/wav",
                    "description": "meeting audio",
                },
            )
        if str(request.url) == "https://upload.test/asset-123":
            assert request.method == "PUT"
            assert request.content == b"large-audio"
            return httpx.Response(200)
        payload = json.loads(request.content.decode("utf-8"))
        assert '<audio src="data:audio/wav;asset_id,asset-123"' in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({
                "language": "en",
                "transcript": "We reviewed the launch plan.",
                "confidence": 0.88,
                "warnings": [],
            })}}]},
        )

    client = NimAudioClient(
        api_key="test-secret",
        model="nvidia/audio-test",
        base_url="https://nim.test",
        inline_max_bytes=5,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.transcribe_audio(
        base64.b64encode(b"large-audio").decode("ascii"),
        "audio/wav",
    )

    assert result["transcript"] == "We reviewed the launch plan."
    assert [request.method for request in requests] == ["POST", "PUT", "POST"]
```

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_client.py -v
```

Expected: fail because `NimAudioClient` does not exist.

**Step 3: Implement minimal code**

Add `NimAudioClient` to `nim_client.py`.

Implementation notes:

- Normalize MIME format for NIM tags:
  - `audio/wav`, `audio/x-wav` -> `wav`
  - `audio/mpeg`, `audio/mp3` -> `mp3`
- Inline content string:

```python
content = (
    "/no_think\n"
    "Transcribe this meeting audio. Return JSON only with keys: "
    "language, transcript, confidence, warnings. Preserve spoken language. "
    "Use Traditional Chinese for Chinese speech.\n"
    f'<audio src="data:audio/{audio_format};base64,{audio_base64}" />'
)
```

- Asset content string:

```python
f'<audio src="data:audio/{audio_format};asset_id,{asset_id}" />'
```

- Create NVCF asset with:

```python
POST https://api.nvcf.nvidia.com/v2/nvcf/assets
Authorization: Bearer <api_key>
json={"contentType": mime_type, "description": "meeting audio"}
```

- Upload bytes to the returned `uploadUrl` with `PUT`, `Content-Type`, and `x-amz-meta-nvcf-asset-description`.
- Reuse `_extract_chat_content()` and `_strip_markdown_json_fence()`.
- Raise `NimClientError` for request errors and `NimClientResponseError` for HTTP failures.

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_client.py -v
```

Expected: pass.

---

### Task 3: Meeting Audio Service And Minutes Generation

**Files:**
- Create: `agent_app/src/deal_agent/services/meeting_audio.py`
- Modify: `agent_app/src/deal_agent/services/__init__.py`
- Test: `agent_app/tests/test_meeting_audio_service.py`

**Step 1: Write the failing tests**

Create tests for:

```python
def test_meeting_audio_processor_transcribes_and_generates_minutes_in_zh_tw():
    class StubAudioClient:
        def transcribe_audio(self, audio_base64, mime_type, language_hint=None):
            return {
                "language": "zh-TW",
                "transcript": "今天決議下週完成 Odoo demo。",
                "confidence": 0.9,
                "warnings": [],
            }

    class StubMinutesClient:
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

    assert result.transcript.transcript == "今天決議下週完成 Odoo demo。"
    assert result.minutes.summary == "討論 Odoo demo 時程。"
```

Add tests for:

- `audio/ogg` invokes a converter and changes MIME type to `audio/wav`.
- low confidence with usable transcript returns warning metadata.
- empty transcript raises `MeetingAudioProcessingError(retryable=False)`.
- NIM retryable errors become retryable service errors.

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_service.py -v
```

Expected: fail because service does not exist.

**Step 3: Implement minimal code**

Create:

```python
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
```

Protocols:

```python
class AudioTranscriptionClient(Protocol):
    model: str
    def transcribe_audio(self, audio_base64: str, mime_type: str, language_hint: str | None = None) -> Any: ...


class MinutesClient(Protocol):
    model: str
    def chat_json(self, system_prompt: str, user_prompt: str) -> Any: ...
```

Converter:

```python
class FfmpegAudioConverter:
    def convert_to_wav(self, audio_bytes: bytes) -> bytes:
        if shutil.which("ffmpeg") is None:
            raise MeetingAudioProcessingError("ffmpeg is required to convert Telegram voice audio", retryable=False)
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "wav", "pipe:1"],
                input=audio_bytes,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise MeetingAudioProcessingError("audio conversion failed", retryable=False) from exc
        return result.stdout
```

Minutes prompt:

```python
system_prompt = (
    "You write concise meeting minutes from transcripts. "
    "Return JSON only with keys language, summary, decisions, action_items, risks, follow_up. "
    "Use Traditional Chinese when the transcript is zh-TW or mixed. Use English when it is English."
)
```

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_service.py -v
```

Expected: pass.

---

### Task 4: FastAPI Meeting Audio Tool Endpoint

**Files:**
- Modify: `agent_app/src/deal_agent/main.py`
- Test: `agent_app/tests/test_tool_gateway.py`

**Step 1: Write the failing tests**

Add tests:

```python
def test_meeting_audio_tool_defaults_to_dry_run(monkeypatch):
    _override_settings(_settings(live_workflow_enabled=False))

    response = client.post(
        "/tools/meeting/audio",
        json={
            "run_id": "audio_1",
            "audio_base64": "YXVkaW8=",
            "mime_type": "audio/wav",
            "source": "audio",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["live_enabled"] is False
    assert "transcribe meeting audio" in body["planned_actions"]
```

Add live test with dependency monkeypatch:

```python
def test_meeting_audio_tool_live_uses_processor(monkeypatch):
    _override_settings(_settings(live_workflow_enabled=True, nvidia_api_key="secret"))

    class StubProcessor:
        def process(self, run_id, audio_base64, mime_type, filename=None, language_hint=None):
            return MeetingAudioResult(
                run_id=run_id,
                transcript=MeetingTranscript(language="en", transcript="We approved launch.", confidence=0.9),
                minutes=MeetingMinutes(language="en", summary="Launch approved."),
                audio_model="audio-model",
                minutes_model="text-model",
            )

    monkeypatch.setattr(main_module, "create_meeting_audio_processor", lambda settings: StubProcessor())

    response = client.post(
        "/tools/meeting/audio",
        json={
            "run_id": "audio_2",
            "audio_base64": "YXVkaW8=",
            "mime_type": "audio/wav",
            "source": "audio",
            "live": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["transcript"]["transcript"] == "We approved launch."
```

Add missing config test:

- `LIVE_WORKFLOW_ENABLED=1`, `live=true`, missing `NVIDIA_API_KEY` returns `400` with `["NVIDIA_API_KEY"]`.

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_tool_gateway.py::test_meeting_audio_tool_defaults_to_dry_run -v
```

Expected: fail because route does not exist.

**Step 3: Implement minimal code**

In `main.py`:

- Import meeting audio models and service.
- Add `create_meeting_audio_processor(app_settings)`.
- Add `_missing_meeting_audio_config(app_settings)`.
- Add route:

```python
@app.post("/tools/meeting/audio")
def run_meeting_audio_tool(request: MeetingAudioToolRequest, app_settings: Settings = Depends(get_settings)) -> dict:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
            "mode": "dry_run",
            "live_enabled": False,
            "planned_actions": ["transcribe meeting audio", "generate meeting minutes", "send Telegram responses"],
        }
    missing = _missing_meeting_audio_config(app_settings)
    if missing:
        raise HTTPException(status_code=400, detail={"missing_config": missing})
    result = create_meeting_audio_processor(app_settings).process(...)
    return {
        "mode": "live",
        "live_enabled": True,
        **result.model_dump(mode="json"),
    }
```

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_tool_gateway.py -v
```

Expected: pass.

---

### Task 5: Telegram Ops Bot Audio Routing And Response Chunking

**Files:**
- Modify: `agent_app/src/deal_agent/telegram_ops.py`
- Modify: `agent_app/src/deal_agent/telegram_ops_cli.py`
- Test: `agent_app/tests/test_telegram_ops.py`

**Step 1: Write the failing tests**

Add request type imports and a meeting audio callback.

Test voice note routing:

```python
def test_telegram_ops_voice_routes_to_meeting_audio_tool():
    telegram = StubTelegram()
    seen: list[MeetingAudioToolRequest] = []

    def meeting_audio(request: MeetingAudioToolRequest):
        seen.append(request)
        return {
            "transcript": {"language": "zh-TW", "transcript": "今天討論交付排程。", "confidence": 0.9, "warnings": []},
            "minutes": {"language": "zh-TW", "summary": "討論交付排程。", "decisions": [], "action_items": [], "risks": [], "follow_up": []},
            "warnings": [],
        }

    bot = TelegramOpsBot(
        telegram=telegram,
        allowed_user_ids={123456789},
        business_card_tool=lambda request: {},
        crm_lookup_tool=lambda request: {},
        meeting_audio_tool=meeting_audio,
    )

    bot.handle_update(_message_update(voice={"file_id": "voice1", "mime_type": "audio/ogg"}))

    assert telegram.downloaded == ["audio/voice1.ogg"]
    assert seen[0].run_id == "telegram_audio_10"
    assert seen[0].mime_type == "audio/ogg"
    assert seen[0].source == "voice"
    assert seen[0].live is True
    assert "逐字稿" in telegram.messages[0][1]
    assert "Meeting Minutes" in telegram.messages[1][1] or "會議紀要" in telegram.messages[1][1]
```

Update `StubTelegram.get_file()` so audio file ids return `audio/<id>.ogg`.

Add tests:

- supported `audio` message routes with filename/MIME.
- unsupported `document` falls through to text lookup only when text exists, otherwise sends no meeting audio call.
- long transcript is split into multiple messages below the configured chunk size.
- `/start` mentions meeting audio.

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_telegram_ops.py::test_telegram_ops_voice_routes_to_meeting_audio_tool -v
```

Expected: fail because constructor and routing do not support meeting audio.

**Step 3: Implement minimal code**

In `telegram_ops.py`:

- Add `MeetingAudioTool` callback protocol.
- Add `meeting_audio_tool` constructor argument.
- Route order:
  1. unauthorized
  2. `/start`
  3. photo -> business card
  4. voice/audio/supported document -> meeting audio
  5. text -> CRM lookup

Add helpers:

```python
def _audio_payload(message: dict[str, Any]) -> tuple[str, str, str | None, str] | None:
    ...


def _is_supported_audio(mime_type: str | None, filename: str | None) -> bool:
    ...


def _chunk_text(text: str, max_chars: int) -> list[str]:
    ...
```

Format responses:

- Transcript header: `逐字稿 / Transcript`
- Minutes header: `會議紀要 / Meeting Minutes`
- For `MeetingMinutes`, include summary, decisions, action items, risks, and follow-up.

In `telegram_ops_cli.py`:

- Pass `run_meeting_audio_tool` into `TelegramOpsBot`.

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_telegram_ops.py -v
```

Expected: pass.

---

### Task 6: OpenClaw Plugin Tool And Workspace Instructions

**Files:**
- Modify: `openclaw_plugins/solopreneur-tools/openclaw.plugin.json`
- Modify: `openclaw_plugins/solopreneur-tools/dist/index.js`
- Modify: `skills/deal-to-delivery/SKILL.md`
- Modify: `workspace/TOOLS.md`
- Test: `agent_app/tests/test_nemoclaw_assets.py`

**Step 1: Write the failing tests**

In `test_nemoclaw_assets.py`, add:

```python
def test_solopreneur_plugin_exposes_meeting_audio_tool():
    manifest = json.loads((REPO_ROOT / "openclaw_plugins" / "solopreneur-tools" / "openclaw.plugin.json").read_text())
    runtime = (REPO_ROOT / "openclaw_plugins" / "solopreneur-tools" / "dist" / "index.js").read_text()

    assert "meeting_audio_process" in manifest["contracts"]["tools"]
    assert "meeting_audio_process" in runtime
    assert "/tools/meeting/audio" in runtime
```

Add tests that `skills/deal-to-delivery/SKILL.md` and `workspace/TOOLS.md` mention the meeting audio workflow and double live gate.

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_nemoclaw_assets.py::test_solopreneur_plugin_exposes_meeting_audio_tool -v
```

Expected: fail because plugin does not mention the tool.

**Step 3: Implement minimal code**

Add `meeting_audio_process` to manifest `contracts.tools`.

In `dist/index.js`, add:

```javascript
tool({
  name: "meeting_audio_process",
  label: "Meeting Audio",
  description: "Transcribe meeting audio and generate meeting minutes from Telegram or operator-provided audio.",
  parameters: strictObject({
    run_id: stringField("Stable id for this meeting audio run."),
    audio_base64: stringField("Base64-encoded audio bytes."),
    mime_type: stringField("Audio MIME type such as audio/wav, audio/mpeg, or audio/ogg."),
    filename: stringField("Optional filename from Telegram or upload source."),
    source: stringField("voice, audio, or document."),
    language_hint: stringField("Optional language hint such as zh-TW or en."),
    live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
  }, ["run_id", "audio_base64", "mime_type"]),
  execute: ({ run_id, audio_base64, mime_type, filename = null, source = "audio", language_hint = null, live = false }, config, context) => postGateway(
    "/tools/meeting/audio",
    { run_id, audio_base64, mime_type, filename, source, language_hint, live },
    config,
    context,
  ),
})
```

Update skill/workspace docs:

- Agent should use meeting audio only for user-provided recordings.
- Transcript must be sent before minutes.
- Do not claim high accuracy without live eval evidence.
- For Chinese audio, use Traditional Chinese transcript/minutes.

**Step 4: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_nemoclaw_assets.py -v
```

Expected: pass.

---

### Task 7: Live Audio Eval Harness

**Files:**
- Create: `agent_app/tests/live/test_meeting_audio_live.py`
- Create: `agent_app/tests/test_meeting_audio_eval.py`
- Create: `agent_app/tests/fixtures/audio/README.md`
- Optional user-supplied fixtures:
  - `agent_app/tests/fixtures/audio/meeting_zh_tw_short.wav`
  - `agent_app/tests/fixtures/audio/meeting_zh_tw_short.expected.json`
  - `agent_app/tests/fixtures/audio/meeting_en_short.wav`
  - `agent_app/tests/fixtures/audio/meeting_en_short.expected.json`

**Step 1: Write failing metric tests**

Create `test_meeting_audio_eval.py`:

```python
def test_keyword_recall_counts_expected_keywords():
    assert keyword_recall("今天討論 Odoo demo 和 Telegram 錄音", ["Odoo", "Telegram"]) == 1.0
    assert keyword_recall("今天討論 Odoo demo", ["Odoo", "Telegram"]) == 0.5


def test_normalized_error_rate_handles_exact_match():
    assert normalized_error_rate("We approved launch", "We approved launch") == 0.0
```

**Step 2: Run tests to verify RED**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_eval.py -v
```

Expected: fail because metric helpers do not exist.

**Step 3: Implement minimal metric helpers**

Create helpers inside the test file or a small module if reuse is cleaner. Keep them dependency-free:

- `keyword_recall(transcript, keywords)`
- `normalized_error_rate(expected, actual)` using `difflib.SequenceMatcher` or a simple Levenshtein implementation.

**Step 4: Add live skipped test**

`test_meeting_audio_live.py`:

- Mark with `pytestmark = pytest.mark.live`.
- Skip unless:
  - `NVIDIA_AUDIO_LIVE_TEST=1`
  - `NVIDIA_API_KEY`
  - fixture audio file exists
- Use `NimAudioClient` and `MeetingAudioProcessor`.
- Assert:
  - transcript is non-empty.
  - keyword recall meets fixture threshold.
  - confidence/warnings are printed in assertion context.

**Step 5: Verify GREEN**

Run:

```bash
cd agent_app && uv run pytest tests/test_meeting_audio_eval.py tests/live/test_meeting_audio_live.py -q -rs
```

Expected: metric tests pass; live test skips unless explicitly opted in and fixtures exist.

---

### Task 8: Documentation, Env Example, And Final Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `Install.md`
- Test: repository-level verification

**Step 1: Write/update docs**

Add `.env.example` entries:

```text
NIM_AUDIO_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
NIM_AUDIO_INLINE_MAX_BYTES=180000
MEETING_AUDIO_MIN_CONFIDENCE=0.45
MEETING_AUDIO_MAX_TELEGRAM_CHARS=3900
```

Update README/Install with:

- Telegram supported audio types.
- `ffmpeg` requirement for Telegram voice notes.
- Live eval command.
- Warning that transcription accuracy must be checked with local fixtures before demo claims.

**Step 2: Run final verification**

Run:

```bash
cd agent_app && uv run pytest -q
git diff --check
```

Expected:

- All default tests pass.
- Live tests skip unless opted in.
- No whitespace errors.

**Step 3: If NemoClaw/OpenClaw assets changed, run focused tests**

Run:

```bash
cd agent_app && uv run pytest tests/test_nemoclaw_assets.py -q
```

Expected: pass.

**Step 4: Manual smoke after implementation**

With services running:

```bash
LIVE_WORKFLOW_ENABLED=1 make tool-gateway
make telegram-ops
```

Send a Telegram voice note from an allowlisted user. Expected:

1. Transcript message arrives.
2. Meeting minutes message arrives.
3. Tool gateway logs show `/tools/meeting/audio`.
4. No Odoo/Linear/GitHub side effects occur.

---

## Notes For Execution

- Do not write production code before the corresponding failing test.
- Do not batch-delete generated files or directories.
- Do not commit `.env` or any audio fixture containing private meeting content.
- If adding real audio fixtures, use short synthetic or consented recordings only.
- Keep live eval opt-in; default `uv run pytest -q` must not call NVIDIA or Telegram.
