from datetime import UTC, datetime

import pytest

import deal_agent.workflow as workflow
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


def test_failed_retryable_can_be_reached_from_new_for_intake_transient_failure():
    run = WorkflowRun.from_brief("run_1", "brief")

    updated = advance(run, WorkflowState.FAILED_RETRYABLE, "intake", {"error": "nim timeout"})

    assert updated.state is WorkflowState.FAILED_RETRYABLE
    assert updated.steps[-1].state_before is WorkflowState.NEW
    assert updated.steps[-1].state_after is WorkflowState.FAILED_RETRYABLE


def test_failure_transition_records_error_and_retry_bookkeeping():
    run = WorkflowRun.from_brief("run_1", "brief")
    summarized = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {})

    updated = advance(
        summarized,
        WorkflowState.FAILED_RETRYABLE,
        "odoo",
        {"error": "odoo timeout"},
    )

    assert updated.steps[-1].error == "odoo timeout"
    assert updated.last_error == "odoo timeout"
    assert updated.retry_count == 1


def test_failure_transition_accepts_explicit_error():
    run = WorkflowRun.from_brief("run_1", "brief")

    updated = advance(
        run,
        WorkflowState.FAILED_TERMINAL,
        "guardrail",
        {"error": "metadata error"},
        error="policy denied",
    )

    assert updated.steps[-1].error == "policy denied"
    assert updated.last_error == "policy denied"


def test_resume_retryable_returns_to_last_failed_step_state_without_mutating_input():
    run = WorkflowRun.from_brief("run_1", "brief")
    failed = advance(run, WorkflowState.FAILED_RETRYABLE, "intake", {"error": "nim timeout"})

    resumed = workflow.resume_retryable(failed, metadata={"attempt": 2})

    assert resumed is not failed
    assert resumed.state is WorkflowState.NEW
    assert resumed.last_error is None
    assert resumed.retry_count == failed.retry_count
    assert resumed.steps[-1].step_name == "retry_resume"
    assert resumed.steps[-1].state_before is WorkflowState.FAILED_RETRYABLE
    assert resumed.steps[-1].state_after is WorkflowState.NEW
    assert resumed.steps[-1].metadata == {"attempt": 2}
    assert failed.state is WorkflowState.FAILED_RETRYABLE
    assert failed.last_error == "nim timeout"


def test_resume_retryable_rejects_non_retryable_run():
    run = WorkflowRun.from_brief("run_1", "brief")

    with pytest.raises(InvalidTransition):
        workflow.resume_retryable(run)


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


def test_record_step_appends_audit_step_without_changing_state_or_input_run():
    run = WorkflowRun.from_brief("run_1", "brief")
    for next_state, step_name in [
        (WorkflowState.INTAKE_SUMMARIZED, "intake"),
        (WorkflowState.ODOO_LEAD_CREATED, "odoo_lead"),
        (WorkflowState.QUOTE_DRAFTED, "quote"),
        (WorkflowState.ODOO_QUOTATION_CREATED, "odoo_quotation"),
    ]:
        run = advance(run, next_state, step_name, {})
    original_updated_at = run.updated_at

    updated = workflow.record_step(run, "issue_breakdown", {"issue_count": 3})

    assert updated is not run
    assert updated.state is WorkflowState.ODOO_QUOTATION_CREATED
    assert run.steps[-1].step_name == "odoo_quotation"
    assert len(updated.steps) == len(run.steps) + 1
    assert updated.steps[-1].step_name == "issue_breakdown"
    assert updated.steps[-1].state_before is WorkflowState.ODOO_QUOTATION_CREATED
    assert updated.steps[-1].state_after is WorkflowState.ODOO_QUOTATION_CREATED
    assert updated.steps[-1].metadata == {"issue_count": 3}
    assert updated.updated_at > original_updated_at
