from decimal import Decimal

import httpx
import pytest

import deal_agent.nim_client as nim_client
from deal_agent.models import ExternalRef, WorkflowRun
from deal_agent.nim_client import NimChatClient
from deal_agent.services.model_services import FakeModelServices, ModelServiceError, NimModelServices


def test_fake_model_services_extracts_intake():
    services = FakeModelServices()

    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")

    assert summary.customer_name == "ACME"
    assert summary.scope_items
    assert summary.risks == []


def test_fake_model_services_extracts_customer_from_for_pattern_before_acronym_fallback():
    services = FakeModelServices()

    summary = services.extract_intake("Need an MVP for ACME with Odoo automation.")

    assert summary.customer_name == "ACME"


def test_fake_model_services_drafts_quote_with_valid_totals():
    services = FakeModelServices()
    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")

    quote = services.draft_quote(summary)

    assert quote.currency == "USD"
    assert quote.line_items
    assert quote.subtotal == sum((item.line_total for item in quote.line_items), Decimal("0"))
    assert quote.total == quote.subtotal + quote.tax
    assert quote.total == Decimal("4500")


def test_fake_model_services_breaks_down_delivery_issues_deterministically():
    services = FakeModelServices()
    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")

    first = services.break_down_issues(summary)
    second = services.break_down_issues(summary)

    assert first == second
    assert [issue.title for issue in first] == [
        "Capture intake and summarize scope",
        "Create Odoo deal artifacts",
        "Bootstrap delivery tracking",
    ]
    assert all("mvp" in issue.labels for issue in first)


def test_fake_model_services_composes_run_notification():
    services = FakeModelServices()
    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")
    quote = services.draft_quote(summary)
    run = WorkflowRun.from_brief("run_123", "ACME needs a two-week Odoo automation prototype.")
    run.intake_summary = summary
    run.quote_draft = quote
    run.external_refs = [
        ExternalRef(system="odoo", external_id="odoo-quote-1", metadata={"kind": "quotation"}),
        ExternalRef(system="linear", external_id="LIN-1", metadata={"kind": "project"}),
    ]

    message = services.compose_notification(run)

    assert "ACME" in message
    assert "run_123" in message
    assert "USD 4500" in message
    assert "odoo:odoo-quote-1" in message
    assert "linear:LIN-1" in message


class StubNimJsonClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, system_prompt: str, user_prompt: str):
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_nim_model_services_extracts_intake_from_structured_json():
    client = StubNimJsonClient(
        [
            {
                "customer_name": "ACME",
                "contact_name": "Ada Lovelace",
                "contact_email": "ada@example.com",
                "problem_statement": "Manual deal handoff is slow.",
                "scope_items": ["Create Odoo CRM lead"],
                "goals": ["Shorten response time"],
                "assumptions": ["Budget is draft"],
                "risks": [],
                "estimated_budget": "8000",
                "timeline": "two weeks",
                "confidence": 0.88,
            }
        ],
    )
    services = NimModelServices(client)

    summary = services.extract_intake("ACME needs a two-week Odoo automation package.")

    assert summary.customer_name == "ACME"
    assert summary.estimated_budget == Decimal("8000")
    assert "Return JSON only" in client.calls[0][0]


def test_nim_model_services_drafts_quote_and_issues_from_structured_json():
    client = StubNimJsonClient(
        [
            {
                "currency": "USD",
                "line_items": [
                    {"description": "CRM automation", "quantity": "1", "unit_price": "8000"}
                ],
                "subtotal": "8000",
                "tax": "0",
                "total": "8000",
                "notes": "Draft only.",
            },
            [
                {
                    "title": "Configure CRM lead intake",
                    "description": "Set up Odoo CRM intake workflow.",
                    "labels": ["crm", "mvp"],
                    "priority": "high",
                }
            ],
        ],
    )
    services = NimModelServices(client)
    summary = FakeModelServices().extract_intake("ACME needs Odoo automation.")

    quote = services.draft_quote(summary)
    issues = services.break_down_issues(summary)

    assert quote.total == Decimal("8000")
    assert issues[0].title == "Configure CRM lead intake"


def test_nim_model_services_composes_notification_from_json_text():
    client = StubNimJsonClient([{"message": "ACME run run_1 is ready."}])
    services = NimModelServices(client)
    run = WorkflowRun.from_brief("run_1", "ACME needs Odoo automation.")

    message = services.compose_notification(run)

    assert message == "ACME run run_1 is ready."


def test_nim_model_services_wraps_validation_errors_as_terminal():
    client = StubNimJsonClient([{"customer_name": "ACME"}])
    services = NimModelServices(client)

    with pytest.raises(ModelServiceError) as exc_info:
        services.extract_intake("ACME needs Odoo automation.")

    assert exc_info.value.retryable is False


def test_nim_chat_client_posts_completion_and_parses_json():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://nim.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-secret"
        payload = request.read().decode("utf-8")
        assert "test-secret" not in payload
        assert "Extract intake" in payload
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"customer_name": "ACME", "risks": []}',
                        }
                    }
                ]
            },
        )

    client = NimChatClient(
        api_key="test-secret",
        model="nvidia/test-model",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.chat_json("Extract intake", "ACME needs an automation prototype.")

    assert result == {"customer_name": "ACME", "risks": []}
    assert len(requests) == 1


def test_nim_chat_client_parses_fenced_json_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"ok": true}\n```',
                        }
                    }
                ]
            },
        )

    client = NimChatClient(
        api_key="test-secret",
        model="nvidia/test-model",
        base_url="https://nim.test/",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.chat_json("system", "user") == {"ok": True}


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [
        (400, False),
        (408, True),
        (409, True),
        (425, True),
        (429, True),
        (500, True),
        (503, True),
    ],
)
def test_nim_chat_client_wraps_http_errors_with_retryability(status_code: int, retryable: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "upstream failed"})

    client = NimChatClient(
        api_key="test-secret",
        model="nvidia/test-model",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert "test-secret" not in repr(client)
    with pytest.raises(nim_client.NimClientResponseError) as exc_info:
        client.chat_json("system", "user")

    error = exc_info.value
    assert error.status_code == status_code
    assert error.retryable is retryable
    assert "test-secret" not in str(error)


@pytest.mark.parametrize(
    ("response_payload", "content_type"),
    [
        ("not json", "text/plain"),
        ({"choices": []}, "application/json"),
        ({"choices": [{"message": {}}]}, "application/json"),
        ({"choices": [{"message": {"content": None}}]}, "application/json"),
        ({"choices": [{"message": {"content": 123}}]}, "application/json"),
        ({"choices": [{"message": {"content": "not json"}}]}, "application/json"),
    ],
)
def test_nim_chat_client_wraps_malformed_success_responses(response_payload, content_type: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if content_type == "application/json":
            return httpx.Response(200, json=response_payload)
        return httpx.Response(200, content=str(response_payload), headers={"Content-Type": content_type})

    client = NimChatClient(
        api_key="test-secret",
        model="nvidia/test-model",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(nim_client.NimClientResponseError) as exc_info:
        client.chat_json("system", "user")

    error = exc_info.value
    assert error.status_code == 200
    assert error.retryable is False
    assert "test-secret" not in str(error)
