import re

import pytest
from pydantic import ValidationError

from deal_agent.models import (
    DealBrief,
    DeliveryIssue,
    ExternalRef,
    IntakeSummary,
    QuoteDraft,
    WorkflowRun,
    WorkflowState,
    WorkflowStep,
)


def test_workflow_state_defines_expected_order():
    assert [state.name for state in WorkflowState] == [
        "NEW",
        "INTAKE_SUMMARIZED",
        "ODOO_LEAD_CREATED",
        "QUOTE_DRAFTED",
        "ODOO_QUOTATION_CREATED",
        "LINEAR_BOOTSTRAPPED",
        "GITHUB_DELIVERY_TRACKED",
        "INVOICE_DRAFT_CREATED",
        "TELEGRAM_NOTIFIED",
        "COMPLETED",
        "FAILED_RETRYABLE",
        "FAILED_TERMINAL",
    ]


def test_deal_brief_derives_stable_input_hash():
    brief = DealBrief(
        customer_name="ACME Studio",
        contact_name="Jane",
        contact_email="jane@example.com",
        message="Need a Shopify-to-Odoo workflow prototype.",
    )
    same_brief = DealBrief(
        message="Need a Shopify-to-Odoo workflow prototype.",
        contact_email="jane@example.com",
        contact_name="Jane",
        customer_name="ACME Studio",
    )

    assert re.fullmatch(r"[0-9a-f]{16}", brief.input_hash)
    assert same_brief.input_hash == brief.input_hash


def test_deal_brief_input_hash_tracks_copy_update_and_mutation():
    brief = DealBrief(customer_name="ACME Studio", message="Initial brief")
    original_hash = brief.input_hash

    updated = brief.model_copy(update={"message": "Updated brief"})

    assert updated.input_hash != original_hash

    brief.message = "Updated brief"

    assert brief.input_hash == updated.input_hash


def test_models_forbid_unknown_fields():
    with pytest.raises(ValidationError):
        DealBrief(message="hello", unexpected=True)


def test_workflow_run_starts_new():
    run = WorkflowRun.from_brief("run_123", "hello")

    assert run.run_id == "run_123"
    assert run.brief.message == "hello"
    assert run.state is WorkflowState.NEW
    assert run.steps == []


def test_quote_draft_rejects_invalid_subtotal():
    with pytest.raises(ValidationError, match="subtotal"):
        QuoteDraft(
            line_items=[
                {
                    "description": "Workflow prototype",
                    "quantity": 2,
                    "unit_price": 1000,
                }
            ],
            subtotal=1000,
            total=1000,
        )


def test_quote_draft_rejects_invalid_total():
    with pytest.raises(ValidationError, match="total"):
        QuoteDraft(
            line_items=[
                {
                    "description": "Workflow prototype",
                    "quantity": 2,
                    "unit_price": 1000,
                }
            ],
            subtotal=2000,
            tax=150,
            total=2000,
        )


def test_domain_models_capture_pragmatic_deal_workflow_data():
    summary = IntakeSummary(
        customer_name="ACME Studio",
        problem_statement="Manual fulfillment handoffs are slow.",
        scope_items=["Create Odoo quotation", "Bootstrap Linear delivery work"],
        risks=["Missing product catalog details"],
    )
    quote = QuoteDraft(
        currency="USD",
        line_items=[
            {
                "description": "Workflow prototype",
                "quantity": 1,
                "unit_price": 4500,
            }
        ],
        subtotal=4500,
        total=4500,
    )
    issue = DeliveryIssue(
        title="Build Telegram intake webhook",
        description="Capture customer brief and start workflow.",
        labels=["telegram", "mvp"],
    )
    ref = ExternalRef(system="linear", external_id="LIN-123", url="https://linear.app/demo/issue/LIN-123")
    step = WorkflowStep(
        step_name="linear_bootstrap",
        state_before=WorkflowState.ODOO_QUOTATION_CREATED,
        state_after=WorkflowState.LINEAR_BOOTSTRAPPED,
        metadata={"issue_count": 1},
        external_refs=[ref],
    )

    run = WorkflowRun.from_brief("run_123", "hello")
    run.intake_summary = summary
    run.quote_draft = quote
    run.delivery_issues = [issue]
    run.external_refs = [ref]
    run.steps = [step]

    assert run.intake_summary.scope_items == ["Create Odoo quotation", "Bootstrap Linear delivery work"]
    assert run.quote_draft.total == 4500
    assert run.delivery_issues[0].title == "Build Telegram intake webhook"
    assert run.steps[0].step_name == "linear_bootstrap"
    assert run.steps[0].state_before is WorkflowState.ODOO_QUOTATION_CREATED
    assert run.steps[0].state_after is WorkflowState.LINEAR_BOOTSTRAPPED
    assert run.steps[0].metadata == {"issue_count": 1}
