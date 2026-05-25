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

    try:
        response = client.post(
            "/workflows/demo",
            json={"run_id": "run_api_failure", "message": "ACME needs an Odoo prototype."},
        )
    finally:
        app.dependency_overrides.pop(create_demo_runner, None)

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run_api_failure"
    assert body["state"] == "FAILED_RETRYABLE"
    assert body["last_error"] == "quote service timeout"
    assert [(ref["system"], ref["metadata"]["kind"]) for ref in body["external_refs"]] == [
        ("odoo", "lead")
    ]
