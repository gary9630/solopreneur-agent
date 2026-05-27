from __future__ import annotations

from typing import NoReturn, Protocol

from deal_agent.connectors.base import GitHubConnector, LinearConnector, OdooConnector, TelegramConnector
from deal_agent.models import DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft, WorkflowRun, WorkflowState
from deal_agent.workflow import advance, record_step


class ModelServices(Protocol):
    def extract_intake(self, message: str) -> IntakeSummary:
        ...

    def draft_quote(self, summary: IntakeSummary) -> QuoteDraft:
        ...

    def break_down_issues(self, summary: IntakeSummary) -> list[DeliveryIssue]:
        ...

    def compose_notification(self, run: WorkflowRun) -> str:
        ...


class WorkflowRunFailed(RuntimeError):
    def __init__(self, run: WorkflowRun, original_error: Exception) -> None:
        message = str(original_error) or original_error.__class__.__name__
        super().__init__(message)
        self.run = run
        self.original_error = original_error


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

        try:
            summary = self.models.extract_intake(message)
        except Exception as exc:
            self._fail(run, "intake", exc)
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

        try:
            lead_ref = self.odoo.create_lead(run.run_id, run.brief, summary)
        except Exception as exc:
            self._fail(run, "odoo_lead", exc)
        run.external_refs = [*run.external_refs, lead_ref]
        run = advance(
            run,
            WorkflowState.ODOO_LEAD_CREATED,
            "odoo_lead",
            {"external_id": lead_ref.external_id},
        )

        try:
            quote = self.models.draft_quote(summary)
        except Exception as exc:
            self._fail(run, "quote", exc)
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

        try:
            quotation_ref = self.odoo.create_quotation(run.run_id, quote)
        except Exception as exc:
            self._fail(run, "odoo_quotation", exc)
        run.external_refs = [*run.external_refs, quotation_ref]
        run = advance(
            run,
            WorkflowState.ODOO_QUOTATION_CREATED,
            "odoo_quotation",
            {"external_id": quotation_ref.external_id},
        )

        try:
            issues = self.models.break_down_issues(summary)
        except Exception as exc:
            self._fail(run, "issue_breakdown", exc)
        run.delivery_issues = issues
        run = record_step(
            run,
            "issue_breakdown",
            {"issue_count": len(issues)},
        )
        try:
            linear_refs = self.linear.bootstrap_project(run.run_id, summary, issues)
        except Exception as exc:
            self._fail(run, "linear", exc)
        run.external_refs = [*run.external_refs, *linear_refs]
        run = advance(
            run,
            WorkflowState.LINEAR_BOOTSTRAPPED,
            "linear",
            {"external_ids": [ref.external_id for ref in linear_refs]},
        )

        try:
            github_ref = self.github.create_delivery_issue(run.run_id, summary, linear_refs)
        except Exception as exc:
            self._fail(run, "github", exc)
        run.external_refs = [*run.external_refs, github_ref]
        run = advance(
            run,
            WorkflowState.GITHUB_DELIVERY_TRACKED,
            "github",
            {"external_id": github_ref.external_id},
        )

        try:
            invoice_ref = self.odoo.create_invoice_draft(run.run_id, quote)
        except Exception as exc:
            self._fail(run, "invoice", exc)
        run.external_refs = [*run.external_refs, invoice_ref]
        run = advance(
            run,
            WorkflowState.INVOICE_DRAFT_CREATED,
            "invoice",
            {"external_id": invoice_ref.external_id},
        )

        try:
            notification = self.models.compose_notification(run)
        except Exception as exc:
            self._fail(run, "telegram", exc)
        try:
            telegram_ref = self.telegram.send_status(run.run_id, notification)
        except Exception as exc:
            self._fail(run, "telegram", exc)
        run.external_refs = [*run.external_refs, telegram_ref]
        run = advance(
            run,
            WorkflowState.TELEGRAM_NOTIFIED,
            "telegram",
            {"external_id": telegram_ref.external_id},
        )

        try:
            odoo_trace_refs = self._write_optional_odoo_trace(run)
        except Exception as exc:
            self._fail(run, "odoo_audit", exc)
        if odoo_trace_refs:
            run.external_refs = [*run.external_refs, *odoo_trace_refs]
            run = record_step(
                run,
                "odoo_audit",
                {"external_ids": [ref.external_id for ref in odoo_trace_refs]},
            )

        return advance(
            run,
            WorkflowState.COMPLETED,
            "complete",
            {"external_ref_count": len(run.external_refs)},
        )

    def _write_optional_odoo_trace(self, run: WorkflowRun) -> list[ExternalRef]:
        write_deal_context = getattr(self.odoo, "write_deal_context", None)
        write_audit_log = getattr(self.odoo, "write_audit_log", None)
        if not callable(write_deal_context) or not callable(write_audit_log):
            return []

        customer_name = "Customer"
        contact_email = None
        if run.intake_summary is not None:
            customer_name = run.intake_summary.customer_name or customer_name
            contact_email = run.intake_summary.contact_email
        elif run.brief.customer_name:
            customer_name = run.brief.customer_name
            contact_email = run.brief.contact_email

        context_ref = write_deal_context(
            run_id=run.run_id,
            customer_name=customer_name,
            contact_email=contact_email,
            source_message=run.brief.message,
            state="completed",
            crm_lead_id=_numeric_ref_for_kind(run, "lead"),
            sale_order_id=_numeric_ref_for_kind(run, "quotation"),
            invoice_id=_numeric_ref_for_kind(run, "invoice_draft"),
        )
        audit_ref = write_audit_log(
            run_id=run.run_id,
            step_name="workflow_complete",
            state_before=WorkflowState.TELEGRAM_NOTIFIED.value,
            state_after=WorkflowState.COMPLETED.value,
            service="agent",
            external_ref=context_ref.external_id,
            payload_summary=f"Completed workflow with {len(run.external_refs)} external refs.",
            deal_context_id=_safe_int(context_ref.external_id),
        )
        return [context_ref, audit_ref]

    def _fail(self, run: WorkflowRun, step_name: str, exc: Exception) -> NoReturn:
        error_message = str(exc) or exc.__class__.__name__
        retryable = getattr(exc, "retryable", True)
        failure_state = WorkflowState.FAILED_RETRYABLE if retryable else WorkflowState.FAILED_TERMINAL
        metadata = {
            "error": error_message,
            "exception_type": exc.__class__.__name__,
            "retryable": retryable,
        }
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            metadata["status_code"] = status_code
        failed_run = advance(
            run,
            failure_state,
            step_name,
            metadata,
            error=error_message,
        )
        raise WorkflowRunFailed(failed_run, exc) from exc


def _numeric_ref_for_kind(run: WorkflowRun, kind: str) -> int | None:
    for ref in run.external_refs:
        if ref.system == "odoo" and ref.metadata.get("kind") == kind:
            return _safe_int(ref.external_id)
    return None


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
