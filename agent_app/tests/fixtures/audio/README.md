# Meeting Audio Live Fixtures

Place only short synthetic or consented recordings in this directory.

Default opt-in live eval fixture names:

- `meeting_zh_tw_short.wav`
- `meeting_zh_tw_short.expected.json`

Expected JSON shape:

```json
{
  "language": "zh-TW",
  "transcript": "Expected transcript text.",
  "keywords": ["Odoo", "Telegram"],
  "min_keyword_recall": 0.8,
  "max_normalized_error_rate": 0.4
}
```

The default test suite skips live audio evaluation unless `NVIDIA_AUDIO_LIVE_TEST=1`,
`NVIDIA_API_KEY` is set, and fixture files exist.
