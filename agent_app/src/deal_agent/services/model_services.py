from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError

from deal_agent.nim_client import NimClientError
from deal_agent.models import DeliveryIssue, IntakeSummary, QuoteDraft, QuoteLineItem, WorkflowRun

COMMON_ACRONYMS = frozenset({"AI", "API", "CLI", "CRM", "ERP", "MVP", "NIM", "POC", "UI", "UX"})
CUSTOMER_PATTERN = r"(?P<customer>[A-Z][A-Z0-9&.-]{1,})"


class JsonChatClient(Protocol):
    def chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        ...


class ModelServiceError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class FakeModelServices:
    def extract_intake(self, message: str) -> IntakeSummary:
        customer_name = _extract_customer_name(message)
        return IntakeSummary(
            customer_name=customer_name,
            problem_statement=message.strip(),
            scope_items=[
                "Build a two-week Odoo automation prototype",
                "Create quote and invoice draft artifacts",
                "Set up Linear and GitHub delivery tracking",
            ],
            goals=[
                "Turn an inbound brief into a demo-ready deal workflow",
                "Keep external writes auditable and idempotent",
            ],
            assumptions=[
                "Fake connectors are used unless live integration credentials are configured",
            ],
            risks=[],
            estimated_budget=Decimal("4500"),
            timeline="two weeks",
            confidence=0.92,
        )

    def draft_quote(self, summary: IntakeSummary) -> QuoteDraft:
        line_items = [
            QuoteLineItem(
                description="Deal-to-delivery MVP workflow",
                quantity=Decimal("1"),
                unit_price=Decimal("3000"),
            ),
            QuoteLineItem(
                description="Odoo, Linear, GitHub, and Telegram integrations",
                quantity=Decimal("1"),
                unit_price=Decimal("1500"),
            ),
        ]
        subtotal = sum((item.line_total for item in line_items), Decimal("0"))
        return QuoteDraft(
            currency="USD",
            line_items=line_items,
            subtotal=subtotal,
            tax=Decimal("0"),
            total=subtotal,
            notes=f"Demo quote for {summary.customer_name or 'the customer'} based on the captured scope.",
        )

    def break_down_issues(self, summary: IntakeSummary) -> list[DeliveryIssue]:
        customer = summary.customer_name or "customer"
        return [
            DeliveryIssue(
                title="Capture intake and summarize scope",
                description=f"Parse the {customer} brief into structured scope, goals, assumptions, and risks.",
                labels=["mvp", "intake"],
                priority="high",
                estimate_points=2,
            ),
            DeliveryIssue(
                title="Create Odoo deal artifacts",
                description="Create the lead, quotation, and invoice draft through the Odoo connector.",
                labels=["mvp", "odoo"],
                priority="high",
                estimate_points=3,
            ),
            DeliveryIssue(
                title="Bootstrap delivery tracking",
                description="Create Linear work items and a GitHub delivery issue linked to the workflow run.",
                labels=["mvp", "delivery"],
                priority="medium",
                estimate_points=3,
            ),
        ]

    def compose_notification(self, run: WorkflowRun) -> str:
        customer = _customer_from_run(run)
        quote = run.quote_draft
        quote_text = "quote pending"
        if quote is not None:
            quote_text = f"{quote.currency} {_format_decimal(quote.total)}"

        refs = ", ".join(f"{ref.system}:{ref.external_id}" for ref in run.external_refs)
        refs_text = refs or "no external refs yet"

        return (
            f"{customer} deal-to-delivery run {run.run_id} is ready. "
            f"Quote: {quote_text}. Refs: {refs_text}."
        )


class NimModelServices:
    def __init__(self, client: JsonChatClient) -> None:
        self._client = client

    def extract_intake(self, message: str) -> IntakeSummary:
        payload = self._chat_json(
            "Return JSON only. Extract an SME deal intake into fields accepted by IntakeSummary: "
            "customer_name, contact_name, contact_email, problem_statement, scope_items, goals, "
            "assumptions, risks, estimated_budget, timeline, confidence.",
            message,
        )
        return _validate_model(IntakeSummary, payload, "NIM intake output")

    def draft_quote(self, summary: IntakeSummary) -> QuoteDraft:
        payload = self._chat_json(
            "Return JSON only. Draft a quote with currency, line_items, subtotal, tax, total, notes. "
            "Each line item needs description, quantity, unit_price. Never create a finalized invoice.",
            summary.model_dump_json(exclude_none=True),
        )
        return _validate_model(QuoteDraft, payload, "NIM quote output")

    def break_down_issues(self, summary: IntakeSummary) -> list[DeliveryIssue]:
        payload = self._chat_json(
            "Return JSON only. Break the delivery work into an array of Linear issue objects. "
            "Each object needs title, description, labels, priority, assignee_email, estimate_points.",
            summary.model_dump_json(exclude_none=True),
        )
        return _validate_delivery_issues(payload)

    def compose_notification(self, run: WorkflowRun) -> str:
        payload = self._chat_json(
            "Return JSON only with one key, message. Compose a concise Telegram status update for this run.",
            run.model_dump_json(exclude_none=True),
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
            raise ModelServiceError("NIM notification output was invalid", retryable=False)
        return payload["message"].strip()

    def _chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        try:
            return self._client.chat_json(system_prompt, user_prompt)
        except NimClientError as exc:
            raise ModelServiceError(str(exc), retryable=exc.retryable) from exc


def _extract_customer_name(message: str) -> str | None:
    preferred_patterns = [
        rf"\bfor\s+{CUSTOMER_PATTERN}\b",
        rf"\b(?:at|from|with)\s+{CUSTOMER_PATTERN}\b",
        rf"\b{CUSTOMER_PATTERN}\s+(?:needs|wants|requires|asked|is|has)\b",
    ]
    for pattern in preferred_patterns:
        match = re.search(pattern, message)
        if match is not None:
            return match.group("customer")

    for candidate in re.findall(r"\b[A-Z][A-Z0-9&.-]{1,}\b", message):
        if candidate not in COMMON_ACRONYMS:
            return candidate
    return None


def _customer_from_run(run: WorkflowRun) -> str:
    if run.intake_summary and run.intake_summary.customer_name:
        return run.intake_summary.customer_name
    if run.brief.customer_name:
        return run.brief.customer_name
    return "Customer"


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _validate_model(model_type, payload: Any, label: str):
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise ModelServiceError(f"{label} failed validation", retryable=False) from exc


def _validate_delivery_issues(payload: Any) -> list[DeliveryIssue]:
    try:
        return TypeAdapter(list[DeliveryIssue]).validate_python(payload)
    except ValidationError as exc:
        raise ModelServiceError("NIM issue output failed validation", retryable=False) from exc
