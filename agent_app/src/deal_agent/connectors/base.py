from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import httpx

from deal_agent.models import DealBrief, DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft


RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})


class ConnectorError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def request_json(
    http_client: httpx.Client,
    service: str,
    url: str,
    *,
    headers: dict[str, str],
    json: dict[str, Any],
    expected_status: int | None = None,
    require_object: bool = True,
) -> Any:
    try:
        response = http_client.post(url, headers=headers, json=json)
    except httpx.RequestError:
        raise ConnectorError(
            f"{service} request failed before receiving a response",
            retryable=True,
        ) from None

    if response.status_code >= 400:
        raise ConnectorError(
            f"{service} request failed",
            retryable=is_retryable_status(response.status_code),
            status_code=response.status_code,
        )
    if expected_status is not None and response.status_code != expected_status:
        raise ConnectorError(
            f"{service} returned an unexpected status code",
            retryable=is_retryable_status(response.status_code),
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError:
        raise ConnectorError(
            f"{service} response body was not valid JSON",
            retryable=False,
            status_code=response.status_code,
        ) from None
    if require_object and not isinstance(payload, dict):
        raise ConnectorError(
            f"{service} response body was not a JSON object",
            retryable=False,
            status_code=response.status_code,
        )
    return payload


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
