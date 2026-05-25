from decimal import Decimal

import pytest

from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import DealBrief, DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft


def sample_summary() -> IntakeSummary:
    return IntakeSummary(
        customer_name="ACME",
        problem_statement="Manual deal handoff is slowing delivery.",
        scope_items=["Build an app"],
        risks=[],
    )


def sample_quote() -> QuoteDraft:
    return QuoteDraft(
        line_items=[
            {
                "description": "Hackathon MVP implementation",
                "quantity": Decimal("1"),
                "unit_price": Decimal("4500"),
            }
        ],
        subtotal=Decimal("4500"),
        total=Decimal("4500"),
    )


def sample_issues() -> list[DeliveryIssue]:
    return [
        DeliveryIssue(
            title="Build intake flow",
            description="Capture the customer brief and summarize it.",
            labels=["mvp", "intake"],
        ),
        DeliveryIssue(
            title="Create delivery tracking",
            description="Link Linear and GitHub artifacts for the run.",
            labels=["mvp", "delivery"],
        ),
    ]


def assert_external_ref_shape(ref: ExternalRef, system: str, kind: str) -> None:
    assert ref.system == system
    assert ref.external_id
    assert ref.metadata["kind"] == kind


def test_fake_odoo_connector_is_idempotent_for_leads():
    connector = FakeOdooConnector()
    brief = DealBrief(customer_name="ACME", message="Build an app")
    summary = sample_summary()

    first = connector.create_lead("run_1", brief, summary)
    second = connector.create_lead("run_1", brief, summary)

    assert first == second
    assert len(connector.leads) == 1
    assert_external_ref_shape(first, "odoo", "lead")
    assert first.metadata["run_id"] == "run_1"


def test_fake_odoo_connector_is_idempotent_for_quotations_and_invoice_drafts():
    connector = FakeOdooConnector()
    brief = DealBrief(customer_name="ACME", message="Build an app")
    summary = sample_summary()
    quote = sample_quote()

    connector.create_lead("run_1", brief, summary)
    first_quote = connector.create_quotation("run_1", quote)
    second_quote = connector.create_quotation("run_1", quote)
    first_invoice = connector.create_invoice_draft("run_1", quote)
    second_invoice = connector.create_invoice_draft("run_1", quote)

    assert first_quote == second_quote
    assert first_invoice == second_invoice
    assert len(connector.quotations) == 1
    assert len(connector.invoice_drafts) == 1
    assert_external_ref_shape(first_quote, "odoo", "quotation")
    assert_external_ref_shape(first_invoice, "odoo", "invoice_draft")


def test_fake_odoo_connector_rejects_quotation_without_lead():
    connector = FakeOdooConnector()

    with pytest.raises(ValueError, match="lead"):
        connector.create_quotation("run_1", sample_quote())


def test_fake_odoo_connector_rejects_invoice_without_quotation():
    connector = FakeOdooConnector()
    brief = DealBrief(customer_name="ACME", message="Build an app")
    summary = sample_summary()

    connector.create_lead("run_1", brief, summary)

    with pytest.raises(ValueError, match="quotation"):
        connector.create_invoice_draft("run_1", sample_quote())


def test_fake_linear_connector_bootstraps_project_and_issues_idempotently():
    connector = FakeLinearConnector()
    summary = sample_summary()
    issues = sample_issues()

    first = connector.bootstrap_project("run_1", summary, issues)
    second = connector.bootstrap_project("run_1", summary, issues)

    assert first == second
    assert len(first) == 3
    assert len(connector.projects) == 1
    assert len(connector.issues) == 2
    assert_external_ref_shape(first[0], "linear", "project")
    assert [ref.metadata["kind"] for ref in first[1:]] == ["issue", "issue"]


def test_fake_linear_connector_keys_issues_by_content_while_preserving_order():
    connector = FakeLinearConnector()
    summary = sample_summary()
    issues = sample_issues()

    first = connector.bootstrap_project("run_1", summary, issues)
    reordered = connector.bootstrap_project("run_1", summary, list(reversed(issues)))
    changed = connector.bootstrap_project(
        "run_1",
        summary,
        [
            issues[0],
            DeliveryIssue(
                title="Create delivery tracking",
                description="Link Linear, GitHub, and Odoo artifacts for the run.",
                labels=["mvp", "delivery"],
            ),
        ],
    )

    assert {ref.external_id for ref in first[1:]} == {ref.external_id for ref in reordered[1:]}
    assert [ref.metadata["title"] for ref in reordered[1:]] == [
        "Create delivery tracking",
        "Build intake flow",
    ]
    assert len(connector.issues) == 3
    assert changed[2].external_id not in {ref.external_id for ref in first[1:]}


def test_fake_github_connector_creates_delivery_issue_idempotently():
    connector = FakeGitHubConnector()
    summary = sample_summary()
    linear_refs = [
        ExternalRef(system="linear", external_id="LIN-1", metadata={"kind": "project"}),
        ExternalRef(system="linear", external_id="LIN-2", metadata={"kind": "issue"}),
    ]

    first = connector.create_delivery_issue("run_1", summary, linear_refs)
    second = connector.create_delivery_issue("run_1", summary, linear_refs)

    assert first == second
    assert len(connector.delivery_issues) == 1
    assert_external_ref_shape(first, "github", "delivery_issue")
    assert first.metadata["linear_ref_count"] == 2


def test_fake_telegram_connector_sends_status_idempotently():
    connector = FakeTelegramConnector()

    first = connector.send_status("run_1", "Deal-to-delivery run complete.")
    second = connector.send_status("run_1", "Deal-to-delivery run complete.")

    assert first == second
    assert len(connector.messages) == 1
    assert_external_ref_shape(first, "telegram", "message")
    assert first.metadata["message"] == "Deal-to-delivery run complete."


def test_fake_connectors_return_copies_of_stored_refs():
    connector = FakeTelegramConnector()

    first = connector.send_status("run_1", "Deal-to-delivery run complete.")
    first.metadata["message"] = "corrupted by caller"
    second = connector.send_status("run_1", "Deal-to-delivery run complete.")

    assert second is not first
    assert second.metadata["message"] == "Deal-to-delivery run complete."
