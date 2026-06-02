import base64
import json

import httpx

from deal_agent.nim_client import NimAudioClient


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
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "language": "zh-TW",
                                    "transcript": "今天討論產品上線計畫。",
                                    "confidence": 0.91,
                                    "warnings": [],
                                }
                            )
                        }
                    }
                ]
            },
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
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "language": "en",
                                    "transcript": "We reviewed the launch plan.",
                                    "confidence": 0.88,
                                    "warnings": [],
                                }
                            )
                        }
                    }
                ]
            },
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
