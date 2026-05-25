import pytest

from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import WorkflowState
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


class QuoteFailureModelServices(FakeModelServices):
    def draft_quote(self, summary):
        raise RuntimeError("quote service timeout")


class FailingLinearConnector(FakeLinearConnector):
    def bootstrap_project(self, run_id, summary, issues):
        raise RuntimeError("linear API timeout")


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
