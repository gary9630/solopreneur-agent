from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from deal_agent.models import WorkflowRun, WorkflowState, WorkflowStep


class InvalidTransition(ValueError):
    """Raised when a workflow state transition is not allowed."""


ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.NEW: {
        WorkflowState.INTAKE_SUMMARIZED,
        WorkflowState.FAILED_RETRYABLE,
        WorkflowState.FAILED_TERMINAL,
    },
    WorkflowState.INTAKE_SUMMARIZED: {
        WorkflowState.ODOO_LEAD_CREATED,
        WorkflowState.FAILED_RETRYABLE,
        WorkflowState.FAILED_TERMINAL,
    },
    WorkflowState.ODOO_LEAD_CREATED: {
        WorkflowState.QUOTE_DRAFTED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.QUOTE_DRAFTED: {
        WorkflowState.ODOO_QUOTATION_CREATED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.ODOO_QUOTATION_CREATED: {
        WorkflowState.LINEAR_BOOTSTRAPPED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.LINEAR_BOOTSTRAPPED: {
        WorkflowState.GITHUB_DELIVERY_TRACKED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.GITHUB_DELIVERY_TRACKED: {
        WorkflowState.INVOICE_DRAFT_CREATED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.INVOICE_DRAFT_CREATED: {
        WorkflowState.TELEGRAM_NOTIFIED,
        WorkflowState.FAILED_RETRYABLE,
    },
    WorkflowState.TELEGRAM_NOTIFIED: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED_RETRYABLE,
    },
}


def advance(
    run: WorkflowRun,
    next_state: WorkflowState,
    step_name: str,
    metadata: dict[str, Any],
    error: str | None = None,
) -> WorkflowRun:
    allowed_next_states = ALLOWED_TRANSITIONS.get(run.state, set())
    if next_state not in allowed_next_states:
        raise InvalidTransition(f"Cannot transition workflow from {run.state.value} to {next_state.value}")

    now = datetime.now(UTC)
    step_metadata = deepcopy(metadata)
    is_failure = next_state in {WorkflowState.FAILED_RETRYABLE, WorkflowState.FAILED_TERMINAL}
    step_error = error or step_metadata.get("error") if is_failure else None
    step = WorkflowStep(
        step_name=step_name,
        state_before=run.state,
        state_after=next_state,
        started_at=now,
        completed_at=now,
        metadata=step_metadata,
        error=step_error,
    )

    updated = run.model_copy(deep=True)
    updated.state = next_state
    updated.steps.append(step)
    updated.updated_at = now
    if is_failure:
        updated.last_error = step_error
    if next_state is WorkflowState.FAILED_RETRYABLE:
        updated.retry_count += 1
    return updated


def resume_retryable(
    run: WorkflowRun,
    step_name: str = "retry_resume",
    metadata: dict[str, Any] | None = None,
) -> WorkflowRun:
    if run.state is not WorkflowState.FAILED_RETRYABLE:
        raise InvalidTransition(f"Cannot resume workflow from {run.state.value}")

    failed_step = next(
        (step for step in reversed(run.steps) if step.state_after is WorkflowState.FAILED_RETRYABLE),
        None,
    )
    if failed_step is None:
        raise InvalidTransition("Cannot resume retryable workflow without a failed step")

    now = datetime.now(UTC)
    step = WorkflowStep(
        step_name=step_name,
        state_before=WorkflowState.FAILED_RETRYABLE,
        state_after=failed_step.state_before,
        started_at=now,
        completed_at=now,
        metadata=deepcopy(metadata or {}),
    )

    updated = run.model_copy(deep=True)
    updated.state = failed_step.state_before
    updated.steps.append(step)
    updated.updated_at = now
    updated.last_error = None
    return updated
