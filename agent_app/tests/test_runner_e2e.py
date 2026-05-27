import pytest

from deal_agent.connectors.base import ConnectorError
from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import ExternalRef, WorkflowState
from deal_agent.runner import DealWorkflowRunner, WorkflowRunFailed
from deal_agent.services.model_services import FakeModelServices


def test_runner_completes_happy_path_with_fakes():
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    run = runner.run("run_1", "ACME needs a two-week Odoo automation prototype.")

    assert run.state is WorkflowState.COMPLETED
    assert [step.step_name for step in run.steps] == [
        "intake",
        "odoo_lead",
        "quote",
        "odoo_quotation",
        "issue_breakdown",
        "linear",
        "github",
        "invoice",
        "telegram",
        "complete",
    ]
    assert run.intake_summary is not None
    assert run.intake_summary.customer_name == "ACME"
    assert run.quote_draft is not None
    assert run.delivery_issues
    assert [(ref.system, ref.metadata["kind"]) for ref in run.external_refs] == [
        ("odoo", "lead"),
        ("odoo", "quotation"),
        ("linear", "project"),
        ("linear", "issue"),
        ("linear", "issue"),
        ("linear", "issue"),
        ("github", "delivery_issue"),
        ("odoo", "invoice_draft"),
        ("telegram", "message"),
    ]
    linear_external_ids = [ref.external_id for ref in run.external_refs if ref.system == "linear"]
    github_ref = next(ref for ref in run.external_refs if ref.system == "github")
    assert github_ref.metadata["linear_external_ids"] == linear_external_ids


class AuditedFakeOdooConnector(FakeOdooConnector):
    def __init__(self):
        super().__init__()
        self.context_payloads = []
        self.audit_payloads = []

    def write_deal_context(self, **payload):
        self.context_payloads.append(payload)
        return ExternalRef(
            system="odoo",
            external_id="501",
            metadata={"kind": "deal_context", "model": "deal.agent.deal.context", "run_id": payload["run_id"]},
        )

    def write_audit_log(self, **payload):
        self.audit_payloads.append(payload)
        return ExternalRef(
            system="odoo",
            external_id="502",
            metadata={"kind": "audit_log", "model": "deal.agent.audit.log", "run_id": payload["run_id"]},
        )


def test_runner_writes_optional_odoo_deal_context_and_audit_records():
    odoo = AuditedFakeOdooConnector()
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=odoo,
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    run = runner.run("run_audit", "ACME needs a two-week Odoo automation prototype.")

    assert run.state is WorkflowState.COMPLETED
    assert odoo.context_payloads[0]["run_id"] == "run_audit"
    assert odoo.context_payloads[0]["customer_name"] == "ACME"
    assert odoo.context_payloads[0]["state"] == "completed"
    assert odoo.audit_payloads[0]["step_name"] == "workflow_complete"
    assert [(ref.system, ref.metadata["kind"]) for ref in run.external_refs][-2:] == [
        ("odoo", "deal_context"),
        ("odoo", "audit_log"),
    ]


class QuoteFailureModelServices(FakeModelServices):
    def draft_quote(self, summary):
        raise RuntimeError("quote service timeout")


class FailingLinearConnector(FakeLinearConnector):
    def bootstrap_project(self, run_id, summary, issues):
        raise RuntimeError("linear API timeout")


class TerminalLinearConnector(FakeLinearConnector):
    def bootstrap_project(self, run_id, summary, issues):
        raise ConnectorError("linear authentication failed", retryable=False, status_code=401)


def test_runner_raises_failed_run_with_partial_refs_when_quote_fails_after_odoo_lead():
    runner = DealWorkflowRunner(
        models=QuoteFailureModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    with pytest.raises(WorkflowRunFailed) as exc_info:
        runner.run("run_quote_failure", "ACME needs a two-week Odoo automation prototype.")

    failed = exc_info.value.run
    assert failed.state is WorkflowState.FAILED_RETRYABLE
    assert failed.last_error == "quote service timeout"
    assert [(ref.system, ref.metadata["kind"]) for ref in failed.external_refs] == [("odoo", "lead")]
    assert failed.steps[-1].step_name == "quote"
    assert failed.steps[-1].state_before is WorkflowState.ODOO_LEAD_CREATED
    assert failed.steps[-1].state_after is WorkflowState.FAILED_RETRYABLE
    assert failed.steps[-1].error == "quote service timeout"


def test_runner_raises_failed_run_with_partial_refs_when_linear_fails():
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FailingLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    with pytest.raises(WorkflowRunFailed) as exc_info:
        runner.run("run_linear_failure", "ACME needs a two-week Odoo automation prototype.")

    failed = exc_info.value.run
    assert failed.state is WorkflowState.FAILED_RETRYABLE
    assert failed.last_error == "linear API timeout"
    assert [(ref.system, ref.metadata["kind"]) for ref in failed.external_refs] == [
        ("odoo", "lead"),
        ("odoo", "quotation"),
    ]
    assert failed.delivery_issues
    assert [step.step_name for step in failed.steps][-2:] == ["issue_breakdown", "linear"]
    assert failed.steps[-1].state_before is WorkflowState.ODOO_QUOTATION_CREATED
    assert failed.steps[-1].state_after is WorkflowState.FAILED_RETRYABLE
    assert failed.steps[-1].error == "linear API timeout"


def test_runner_marks_non_retryable_connector_errors_terminal_after_partial_refs():
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=TerminalLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    with pytest.raises(WorkflowRunFailed) as exc_info:
        runner.run("run_linear_auth_failure", "ACME needs a two-week Odoo automation prototype.")

    failed = exc_info.value.run
    assert failed.state is WorkflowState.FAILED_TERMINAL
    assert failed.retry_count == 0
    assert failed.last_error == "linear authentication failed"
    assert [(ref.system, ref.metadata["kind"]) for ref in failed.external_refs] == [
        ("odoo", "lead"),
        ("odoo", "quotation"),
    ]
    assert failed.delivery_issues
    assert [step.step_name for step in failed.steps][-2:] == ["issue_breakdown", "linear"]
    assert failed.steps[-1].state_before is WorkflowState.ODOO_QUOTATION_CREATED
    assert failed.steps[-1].state_after is WorkflowState.FAILED_TERMINAL
    assert failed.steps[-1].error == "linear authentication failed"
    assert failed.steps[-1].metadata["retryable"] is False
    assert failed.steps[-1].metadata["status_code"] == 401
