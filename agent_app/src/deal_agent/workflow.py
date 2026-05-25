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
) -> WorkflowRun:
    allowed_next_states = ALLOWED_TRANSITIONS.get(run.state, set())
    if next_state not in allowed_next_states:
        raise InvalidTransition(f"Cannot transition workflow from {run.state.value} to {next_state.value}")

    now = datetime.now(UTC)
    step = WorkflowStep(
        step_name=step_name,
        state_before=run.state,
        state_after=next_state,
        started_at=now,
        completed_at=now,
        metadata=deepcopy(metadata),
    )

    updated = run.model_copy(deep=True)
    updated.state = next_state
    updated.steps.append(step)
    updated.updated_at = now
    return updated
