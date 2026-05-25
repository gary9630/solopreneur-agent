from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from deal_agent.models import DealBrief, DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def _digest(*values: Any) -> str:
    payload = json.dumps(
        [_normalize(value) for value in values],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _ref(system: str, kind: str, key: str, metadata: dict[str, Any]) -> ExternalRef:
    external_id = f"{kind}_{_digest(system, key)}"
    return ExternalRef(
        system=system,
        external_id=external_id,
        url=f"https://example.invalid/{system}/{external_id}",
        metadata={"kind": kind, **metadata},
    )


class FakeOdooConnector:
    def __init__(self) -> None:
        self.leads: dict[str, ExternalRef] = {}
        self.quotations: dict[str, ExternalRef] = {}
        self.invoice_drafts: dict[str, ExternalRef] = {}

    def create_lead(self, run_id: str, brief: DealBrief, summary: IntakeSummary) -> ExternalRef:
        key = f"lead:{run_id}"
        if key not in self.leads:
            self.leads[key] = _ref(
                "odoo",
                "lead",
                key,
                {
                    "run_id": run_id,
                    "customer_name": summary.customer_name or brief.customer_name,
                    "input_hash": brief.input_hash,
                    "problem_statement": summary.problem_statement,
                },
            )
        return self.leads[key]

    def create_quotation(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        key = f"quotation:{run_id}"
        if key not in self.quotations:
            self.quotations[key] = _ref(
                "odoo",
                "quotation",
                key,
                {
                    "run_id": run_id,
                    "currency": quote.currency,
                    "total": str(quote.total),
                },
            )
        return self.quotations[key]

    def create_invoice_draft(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        key = f"invoice_draft:{run_id}"
        if key not in self.invoice_drafts:
            self.invoice_drafts[key] = _ref(
                "odoo",
                "invoice_draft",
                key,
                {
                    "run_id": run_id,
                    "currency": quote.currency,
                    "total": str(quote.total),
                },
            )
        return self.invoice_drafts[key]


class FakeLinearConnector:
    def __init__(self) -> None:
        self.projects: dict[str, ExternalRef] = {}
        self.issues: dict[str, ExternalRef] = {}

    def bootstrap_project(
        self,
        run_id: str,
        summary: IntakeSummary,
        issues: Sequence[DeliveryIssue],
    ) -> list[ExternalRef]:
        project_key = f"project:{run_id}"
        if project_key not in self.projects:
            self.projects[project_key] = _ref(
                "linear",
                "project",
                project_key,
                {
                    "run_id": run_id,
                    "customer_name": summary.customer_name,
                    "problem_statement": summary.problem_statement,
                },
            )

        issue_refs: list[ExternalRef] = []
        for index, issue in enumerate(issues, start=1):
            issue_key = f"issue:{run_id}:{index}"
            if issue_key not in self.issues:
                self.issues[issue_key] = _ref(
                    "linear",
                    "issue",
                    issue_key,
                    {
                        "run_id": run_id,
                        "project_ref": self.projects[project_key].external_id,
                        "title": issue.title,
                        "labels": list(issue.labels),
                    },
                )
            issue_refs.append(self.issues[issue_key])

        return [self.projects[project_key], *issue_refs]


class FakeGitHubConnector:
    def __init__(self) -> None:
        self.delivery_issues: dict[str, ExternalRef] = {}

    def create_delivery_issue(
        self,
        run_id: str,
        summary: IntakeSummary,
        linear_refs: Sequence[ExternalRef],
    ) -> ExternalRef:
        key = f"delivery_issue:{run_id}"
        if key not in self.delivery_issues:
            self.delivery_issues[key] = _ref(
                "github",
                "delivery_issue",
                key,
                {
                    "run_id": run_id,
                    "problem_statement": summary.problem_statement,
                    "linear_ref_count": len(linear_refs),
                    "linear_external_ids": [ref.external_id for ref in linear_refs],
                },
            )
        return self.delivery_issues[key]


class FakeTelegramConnector:
    def __init__(self) -> None:
        self.messages: dict[str, ExternalRef] = {}

    def send_status(self, run_id: str, message: str) -> ExternalRef:
        key = f"status:{run_id}:{_digest(message)}"
        if key not in self.messages:
            self.messages[key] = _ref(
                "telegram",
                "message",
                key,
                {
                    "run_id": run_id,
                    "message": message,
                },
            )
        return self.messages[key]
