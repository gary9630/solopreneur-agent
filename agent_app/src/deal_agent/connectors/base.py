from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from deal_agent.models import DealBrief, DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft


class OdooConnector(Protocol):
    def create_lead(self, run_id: str, brief: DealBrief, summary: IntakeSummary) -> ExternalRef:
        ...

    def create_quotation(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        ...

    def create_invoice_draft(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        ...


class LinearConnector(Protocol):
    def bootstrap_project(
        self,
        run_id: str,
        summary: IntakeSummary,
        issues: Sequence[DeliveryIssue],
    ) -> list[ExternalRef]:
        ...


class GitHubConnector(Protocol):
    def create_delivery_issue(
        self,
        run_id: str,
        summary: IntakeSummary,
        linear_refs: Sequence[ExternalRef],
    ) -> ExternalRef:
        ...


class TelegramConnector(Protocol):
    def send_status(self, run_id: str, message: str) -> ExternalRef:
        ...
