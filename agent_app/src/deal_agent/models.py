from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class WorkflowState(str, Enum):
    NEW = "NEW"
    INTAKE_SUMMARIZED = "INTAKE_SUMMARIZED"
    ODOO_LEAD_CREATED = "ODOO_LEAD_CREATED"
    QUOTE_DRAFTED = "QUOTE_DRAFTED"
    ODOO_QUOTATION_CREATED = "ODOO_QUOTATION_CREATED"
    LINEAR_BOOTSTRAPPED = "LINEAR_BOOTSTRAPPED"
    GITHUB_DELIVERY_TRACKED = "GITHUB_DELIVERY_TRACKED"
    INVOICE_DRAFT_CREATED = "INVOICE_DRAFT_CREATED"
    TELEGRAM_NOTIFIED = "TELEGRAM_NOTIFIED"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class DealBrief(StrictModel):
    message: str
    customer_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    source: str = "manual"
    requested_budget: Decimal | None = None
    requested_timeline: str | None = None
    tags: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def input_hash(self) -> str:
        return self.derive_input_hash()

    def derive_input_hash(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={"input_hash"},
            exclude_none=True,
        )
        stable_json = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()[:16]


class IntakeSummary(StrictModel):
    customer_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    problem_statement: str
    scope_items: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    estimated_budget: Decimal | None = None
    timeline: str | None = None
    confidence: float | None = None


class QuoteLineItem(StrictModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    external_product_id: str | None = None

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


class QuoteDraft(StrictModel):
    currency: str = "USD"
    line_items: list[QuoteLineItem] = Field(default_factory=list)
    subtotal: Decimal
    tax: Decimal = Decimal("0")
    total: Decimal
    notes: str | None = None
    valid_until: str | None = None

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        expected_subtotal = sum(
            (item.line_total for item in self.line_items),
            Decimal("0"),
        )
        if self.subtotal != expected_subtotal:
            raise ValueError("subtotal must equal the sum of quote line item totals")

        expected_total = self.subtotal + self.tax
        if self.total != expected_total:
            raise ValueError("total must equal subtotal plus tax")

        return self


class DeliveryIssue(StrictModel):
    title: str
    description: str
    labels: list[str] = Field(default_factory=list)
    priority: str | None = None
    assignee_email: str | None = None
    estimate_points: int | None = None


class ExternalRef(StrictModel):
    system: str
    external_id: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowStep(StrictModel):
    step_name: str
    state_before: WorkflowState
    state_after: WorkflowState
    status: str = "completed"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_refs: list[ExternalRef] = Field(default_factory=list)
    error: str | None = None


class WorkflowRun(StrictModel):
    run_id: str
    brief: DealBrief
    state: WorkflowState = WorkflowState.NEW
    intake_summary: IntakeSummary | None = None
    quote_draft: QuoteDraft | None = None
    delivery_issues: list[DeliveryIssue] = Field(default_factory=list)
    external_refs: list[ExternalRef] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0
    last_error: str | None = None

    @classmethod
    def from_brief(cls, run_id: str, message: str) -> WorkflowRun:
        return cls(run_id=run_id, brief=DealBrief(message=message))
