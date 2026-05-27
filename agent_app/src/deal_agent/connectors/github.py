from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from deal_agent.connectors.base import ConnectorError, request_json
from deal_agent.models import ExternalRef, IntakeSummary


class GitHubHttpConnector:
    def __init__(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        base_url: str = "https://api.github.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not token:
            raise ValueError("token is required")
        if not owner:
            raise ValueError("owner is required")
        if not repo:
            raise ValueError("repo is required")

        self.owner = owner
        self.repo = repo
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._http_client = http_client or httpx.Client(timeout=30.0)
        self._delivery_issue_refs: dict[str, ExternalRef] = {}

    def __repr__(self) -> str:
        return (
            f"GitHubHttpConnector(base_url={self.base_url!r}, "
            f"owner={self.owner!r}, repo={self.repo!r})"
        )

    def create_delivery_issue(
        self,
        run_id: str,
        summary: IntakeSummary,
        linear_refs: Sequence[ExternalRef],
    ) -> ExternalRef:
        if run_id in self._delivery_issue_refs:
            return _copy_ref(self._delivery_issue_refs[run_id])

        customer = summary.customer_name or "Customer"
        payload = request_json(
            self._http_client,
            "GitHub",
            f"{self.base_url}/repos/{self.owner}/{self.repo}/issues",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
            json={
                "title": f"[{run_id}] Deal-to-delivery: {customer}",
                "body": _issue_body(run_id, summary, linear_refs),
                "labels": ["deal-agent", "mvp"],
            },
            expected_status=201,
        )
        external_id = _required_string(payload, "id", "GitHub issue")
        ref = ExternalRef(
            system="github",
            external_id=external_id,
            url=_optional_string(payload, "html_url"),
            metadata={
                "kind": "delivery_issue",
                "run_id": run_id,
                "number": _optional_int(payload, "number"),
            },
        )
        self._delivery_issue_refs[run_id] = ref
        return _copy_ref(ref)


def _issue_body(
    run_id: str,
    summary: IntakeSummary,
    linear_refs: Sequence[ExternalRef],
) -> str:
    lines = [
        f"Run ID: {run_id}",
        "",
        summary.problem_statement,
        "",
        "Linear refs:",
    ]
    if linear_refs:
        lines.extend(
            f"- {ref.external_id}{f' ({ref.url})' if ref.url else ''}"
            for ref in linear_refs
        )
    else:
        lines.append("- None")
    return "\n".join(lines)


def _required_string(payload: dict[str, Any], key: str, label: str) -> str:
    value = _optional_string(payload, key)
    if value is None:
        raise ConnectorError(f"{label} response did not include {key}", retryable=False, status_code=200)
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    return str(value)


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    return int(value)


def _copy_ref(ref: ExternalRef) -> ExternalRef:
    return ref.model_copy(deep=True)
