from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import WorkflowState
from deal_agent.runner import DealWorkflowRunner
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
    assert [ref.metadata["kind"] for ref in run.external_refs] == [
        "lead",
        "quotation",
        "project",
        "issue",
        "issue",
        "issue",
        "delivery_issue",
        "invoice_draft",
        "message",
    ]
