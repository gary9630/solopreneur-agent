import json

import httpx
import pytest

from deal_agent.nim_client import NimVisionClient
from deal_agent.services.business_card import BusinessCardExtractionError, BusinessCardExtractor


def test_nim_vision_client_posts_image_content_and_parses_json():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://nim.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-secret"
        payload = json.loads(request.content.decode("utf-8"))
        seen.append(payload)
        content = payload["messages"][0]["content"]
        assert content[0]["type"] == "text"
        assert content[1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,abc123"},
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "name": "Ada Lovelace",
                                    "company": "Analytical Engines LLC",
                                    "title": "Founder",
                                    "email": "ada@example.com",
                                    "phone": "+1 555 0100",
                                    "website": "https://example.com",
                                    "raw_text": "Ada Lovelace Founder",
                                    "confidence": 0.94,
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = NimVisionClient(
        api_key="test-secret",
        model="nvidia/vision-test",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.extract_business_card("abc123", "image/jpeg")

    assert result["email"] == "ada@example.com"
    assert seen[0]["model"] == "nvidia/vision-test"


def test_business_card_extractor_validates_contact_output():
    class StubVisionClient:
        def extract_business_card(self, image_base64: str, mime_type: str):
            return {
                "name": "Ada Lovelace",
                "company": "Analytical Engines LLC",
                "email": "ada@example.com",
                "confidence": 0.91,
            }

    extractor = BusinessCardExtractor(StubVisionClient())

    contact = extractor.extract("abc123", "image/jpeg")

    assert contact.name == "Ada Lovelace"
    assert contact.email == "ada@example.com"
    assert contact.confidence == 0.91


@pytest.mark.parametrize(
    "payload",
    [
        {"confidence": 0.1, "raw_text": "unclear"},
        {"name": None, "email": None, "phone": None, "confidence": 0.9},
    ],
)
def test_business_card_extractor_rejects_low_value_output(payload):
    class StubVisionClient:
        def extract_business_card(self, image_base64: str, mime_type: str):
            return payload

    extractor = BusinessCardExtractor(StubVisionClient())

    with pytest.raises(BusinessCardExtractionError) as exc_info:
        extractor.extract("abc123", "image/jpeg")

    assert exc_info.value.retryable is False
