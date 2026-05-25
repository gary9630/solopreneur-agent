import pytest
from fastapi.testclient import TestClient

from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.main import app, create_demo_runner
from deal_agent.runner import DealWorkflowRunner
from deal_agent.services.model_services import FakeModelServices


@pytest.fixture(autouse=True)
def isolate_dependency_overrides():
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


class QuoteFailureModelServices(FakeModelServices):
    def draft_quote(self, summary):
        raise RuntimeError("quote service timeout")


def test_demo_workflow_endpoint_completes_with_fakes():
    client = TestClient(app)

    response = client.post(
        "/workflows/demo",
        json={"run_id": "run_api_1", "message": "ACME needs an Odoo prototype."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run_api_1"
    assert body["state"] == "COMPLETED"


def test_demo_workflow_endpoint_strips_request_fields():
    client = TestClient(app)

    response = client.post(
        "/workflows/demo",
        json={
            "run_id": "  run_api_strip  ",
            "message": "  ACME needs an Odoo prototype.  ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run_api_strip"
    assert body["brief"]["message"] == "ACME needs an Odoo prototype."


@pytest.mark.parametrize(
    "payload",
    [
        {"run_id": "   ", "message": "ACME needs an Odoo prototype."},
        {"run_id": "run_api_blank_message", "message": "\t\n"},
    ],
)
def test_demo_workflow_endpoint_rejects_blank_request_fields(payload):
    client = TestClient(app)

    response = client.post("/workflows/demo", json=payload)

    assert response.status_code == 422


def test_demo_workflow_endpoint_rejects_extra_request_fields():
    client = TestClient(app)

    response = client.post(
        "/workflows/demo",
        json={
            "run_id": "run_api_extra",
            "message": "ACME needs an Odoo prototype.",
            "live": True,
        },
    )

    assert response.status_code == 422


def test_demo_workflow_endpoint_returns_failed_run_for_known_runner_failure():
    def failing_runner():
        return DealWorkflowRunner(
            models=QuoteFailureModelServices(),
            odoo=FakeOdooConnector(),
            linear=FakeLinearConnector(),
            github=FakeGitHubConnector(),
            telegram=FakeTelegramConnector(),
        )

    app.dependency_overrides[create_demo_runner] = failing_runner
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/workflows/demo",
        json={"run_id": "run_api_failure", "message": "ACME needs an Odoo prototype."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run_api_failure"
    assert body["state"] == "FAILED_RETRYABLE"
    assert body["last_error"] == "quote service timeout"
    assert [(ref["system"], ref["metadata"]["kind"]) for ref in body["external_refs"]] == [
        ("odoo", "lead")
    ]
