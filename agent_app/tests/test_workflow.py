from datetime import UTC, datetime

import pytest

from deal_agent.models import WorkflowRun, WorkflowState
from deal_agent.workflow import InvalidTransition, advance


def test_valid_transition_records_step():
    run = WorkflowRun.from_brief("run_1", "brief")

    updated = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {"summary": "ok"})

    assert updated.state is WorkflowState.INTAKE_SUMMARIZED
    assert len(updated.steps) == 1
    assert updated.steps[0].state_before is WorkflowState.NEW
    assert updated.steps[0].state_after is WorkflowState.INTAKE_SUMMARIZED


def test_invalid_transition_is_rejected():
    run = WorkflowRun.from_brief("run_1", "brief")

    with pytest.raises(InvalidTransition):
        advance(run, WorkflowState.LINEAR_BOOTSTRAPPED, "linear", {})


def test_advance_returns_copy_without_mutating_input_run():
    run = WorkflowRun.from_brief("run_1", "brief")
    original_updated_at = run.updated_at

    updated = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {"summary": "ok"})

    assert updated is not run
    assert run.state is WorkflowState.NEW
    assert run.steps == []
    assert run.updated_at == original_updated_at
    assert updated.steps[0].metadata == {"summary": "ok"}


def test_failed_terminal_can_be_reached_from_new():
    run = WorkflowRun.from_brief("run_1", "brief")

    updated = advance(run, WorkflowState.FAILED_TERMINAL, "guardrail", {"reason": "blocked"})

    assert updated.state is WorkflowState.FAILED_TERMINAL
    assert updated.steps[0].state_before is WorkflowState.NEW
    assert updated.steps[0].state_after is WorkflowState.FAILED_TERMINAL


def test_failed_retryable_can_be_reached_from_active_states():
    run = WorkflowRun.from_brief("run_1", "brief")
    summarized = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {})

    updated = advance(summarized, WorkflowState.FAILED_RETRYABLE, "odoo", {"error": "timeout"})

    assert updated.state is WorkflowState.FAILED_RETRYABLE
    assert updated.steps[-1].step_name == "odoo"
    assert updated.steps[-1].state_before is WorkflowState.INTAKE_SUMMARIZED
    assert updated.steps[-1].state_after is WorkflowState.FAILED_RETRYABLE


def test_success_path_reaches_completed_in_order():
    run = WorkflowRun.from_brief("run_1", "brief")

    for next_state in [
        WorkflowState.INTAKE_SUMMARIZED,
        WorkflowState.ODOO_LEAD_CREATED,
        WorkflowState.QUOTE_DRAFTED,
        WorkflowState.ODOO_QUOTATION_CREATED,
        WorkflowState.LINEAR_BOOTSTRAPPED,
        WorkflowState.GITHUB_DELIVERY_TRACKED,
        WorkflowState.INVOICE_DRAFT_CREATED,
        WorkflowState.TELEGRAM_NOTIFIED,
        WorkflowState.COMPLETED,
    ]:
        run = advance(run, next_state, next_state.value.lower(), {})

    assert run.state is WorkflowState.COMPLETED
    assert len(run.steps) == 9


def test_advance_refreshes_updated_at():
    run = WorkflowRun.from_brief("run_1", "brief")
    run.updated_at = datetime(2026, 1, 1, tzinfo=UTC)

    updated = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {})

    assert updated.updated_at > run.updated_at
