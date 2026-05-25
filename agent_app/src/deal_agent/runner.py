from __future__ import annotations

from typing import Protocol

from deal_agent.connectors.base import GitHubConnector, LinearConnector, OdooConnector, TelegramConnector
from deal_agent.models import DeliveryIssue, IntakeSummary, QuoteDraft, WorkflowRun, WorkflowState
from deal_agent.workflow import advance


class ModelServices(Protocol):
    def extract_intake(self, message: str) -> IntakeSummary:
        ...

    def draft_quote(self, summary: IntakeSummary) -> QuoteDraft:
        ...

    def break_down_issues(self, summary: IntakeSummary) -> list[DeliveryIssue]:
        ...

    def compose_notification(self, run: WorkflowRun) -> str:
        ...


class DealWorkflowRunner:
    def __init__(
        self,
        *,
        models: ModelServices,
        odoo: OdooConnector,
        linear: LinearConnector,
        github: GitHubConnector,
        telegram: TelegramConnector,
    ) -> None:
        self.models = models
        self.odoo = odoo
        self.linear = linear
        self.github = github
        self.telegram = telegram

    def run(self, run_id: str, message: str) -> WorkflowRun:
        run = WorkflowRun.from_brief(run_id, message)

        summary = self.models.extract_intake(message)
        run.intake_summary = summary
        run = advance(
            run,
            WorkflowState.INTAKE_SUMMARIZED,
            "intake",
            {
                "customer_name": summary.customer_name,
                "scope_item_count": len(summary.scope_items),
            },
        )

        lead_ref = self.odoo.create_lead(run.run_id, run.brief, summary)
        run.external_refs = [*run.external_refs, lead_ref]
        run = advance(
            run,
            WorkflowState.ODOO_LEAD_CREATED,
            "odoo_lead",
            {"external_id": lead_ref.external_id},
        )

        quote = self.models.draft_quote(summary)
        run.quote_draft = quote
        run = advance(
            run,
            WorkflowState.QUOTE_DRAFTED,
            "quote",
            {
                "currency": quote.currency,
                "total": str(quote.total),
            },
        )

        quotation_ref = self.odoo.create_quotation(run.run_id, quote)
        run.external_refs = [*run.external_refs, quotation_ref]
        run = advance(
            run,
            WorkflowState.ODOO_QUOTATION_CREATED,
            "odoo_quotation",
            {"external_id": quotation_ref.external_id},
        )

        issues = self.models.break_down_issues(summary)
        run.delivery_issues = issues
        linear_refs = self.linear.bootstrap_project(run.run_id, summary, issues)
        run.external_refs = [*run.external_refs, *linear_refs]
        run = advance(
            run,
            WorkflowState.LINEAR_BOOTSTRAPPED,
            "linear",
            {"external_ids": [ref.external_id for ref in linear_refs]},
        )

        github_ref = self.github.create_delivery_issue(run.run_id, summary, linear_refs)
        run.external_refs = [*run.external_refs, github_ref]
        run = advance(
            run,
            WorkflowState.GITHUB_DELIVERY_TRACKED,
            "github",
            {"external_id": github_ref.external_id},
        )

        invoice_ref = self.odoo.create_invoice_draft(run.run_id, quote)
        run.external_refs = [*run.external_refs, invoice_ref]
        run = advance(
            run,
            WorkflowState.INVOICE_DRAFT_CREATED,
            "invoice",
            {"external_id": invoice_ref.external_id},
        )

        notification = self.models.compose_notification(run)
        telegram_ref = self.telegram.send_status(run.run_id, notification)
        run.external_refs = [*run.external_refs, telegram_ref]
        run = advance(
            run,
            WorkflowState.TELEGRAM_NOTIFIED,
            "telegram",
            {"external_id": telegram_ref.external_id},
        )

        return advance(
            run,
            WorkflowState.COMPLETED,
            "complete",
            {"external_ref_count": len(run.external_refs)},
        )
