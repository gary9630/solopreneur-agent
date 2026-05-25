from decimal import Decimal

import httpx
import pytest

from deal_agent.models import ExternalRef, WorkflowRun
from deal_agent.nim_client import NimChatClient
from deal_agent.services.model_services import FakeModelServices


def test_fake_model_services_extracts_intake():
    services = FakeModelServices()

    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")

    assert summary.customer_name == "ACME"
    assert summary.scope_items
    assert summary.risks == []


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


def test_nim_chat_client_does_not_expose_api_key_in_repr_or_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "upstream failed"})

    client = NimChatClient(
        api_key="test-secret",
        model="nvidia/test-model",
        base_url="https://nim.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert "test-secret" not in repr(client)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.chat_json("system", "user")

    assert "test-secret" not in str(exc_info.value)
