from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from deal_agent.connectors.base import ConnectorError, request_json
from deal_agent.models import DeliveryIssue, ExternalRef, IntakeSummary


class LinearHttpConnector:
    def __init__(
        self,
        *,
        api_key: str,
        team_id: str,
        base_url: str = "https://api.linear.app/graphql",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not team_id:
            raise ValueError("team_id is required")

        self.base_url = base_url
        self.team_id = team_id
        self._api_key = api_key
        self._http_client = http_client or httpx.Client(timeout=30.0)

    def __repr__(self) -> str:
        return f"LinearHttpConnector(base_url={self.base_url!r}, team_id={self.team_id!r})"

    def bootstrap_project(
        self,
        run_id: str,
        summary: IntakeSummary,
        issues: Sequence[DeliveryIssue],
    ) -> list[ExternalRef]:
        project = self._create_project(run_id, summary)
        project_id = project.external_id
        issue_refs = [
            self._create_issue(run_id, project_id, issue)
            for issue in issues
        ]
        return [project, *issue_refs]

    def _create_project(self, run_id: str, summary: IntakeSummary) -> ExternalRef:
        customer = summary.customer_name or "Customer"
        payload = self._graphql(
            "CreateProject",
            """
            mutation CreateProject($input: ProjectCreateInput!) {
              projectCreate(input: $input) {
                project { id url }
              }
            }
            """,
            {
                "input": {
                    "name": f"{customer} deal-to-delivery run {run_id}",
                    "description": summary.problem_statement,
                    "teamIds": [self.team_id],
                }
            },
        )
        project = _dig(payload, "data", "projectCreate", "project")
        external_id = _required_string(project, "id", "Linear project")
        return ExternalRef(
            system="linear",
            external_id=external_id,
            url=_optional_string(project, "url"),
            metadata={"kind": "project", "run_id": run_id},
        )

    def _create_issue(self, run_id: str, project_id: str, issue: DeliveryIssue) -> ExternalRef:
        description = issue.description
        if issue.labels:
            description = f"{description}\n\nLabels: {', '.join(issue.labels)}"
        if issue.priority:
            description = f"{description}\nPriority: {issue.priority}"

        payload = self._graphql(
            "CreateIssue",
            """
            mutation CreateIssue($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                issue { id identifier url }
              }
            }
            """,
            {
                "input": {
                    "teamId": self.team_id,
                    "projectId": project_id,
                    "title": issue.title,
                    "description": description,
                }
            },
        )
        created_issue = _dig(payload, "data", "issueCreate", "issue")
        external_id = _required_string(created_issue, "id", "Linear issue")
        return ExternalRef(
            system="linear",
            external_id=external_id,
            url=_optional_string(created_issue, "url"),
            metadata={
                "kind": "issue",
                "run_id": run_id,
                "project_ref": project_id,
                "identifier": _optional_string(created_issue, "identifier"),
                "title": issue.title,
            },
        )

    def _graphql(
        self,
        operation_name: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        payload = request_json(
            self._http_client,
            "Linear",
            self.base_url,
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
            json={
                "operationName": operation_name,
                "query": query,
                "variables": variables,
            },
        )
        if payload.get("errors"):
            raise ConnectorError(
                "Linear GraphQL request returned errors",
                retryable=False,
                status_code=200,
            )
        return payload


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise ConnectorError("Linear response was missing expected data", retryable=False, status_code=200)
        current = current[key]
    return current


def _required_string(payload: Any, key: str, label: str) -> str:
    value = _optional_string(payload, key)
    if value is None:
        raise ConnectorError(f"{label} response did not include {key}", retryable=False, status_code=200)
    return value


def _optional_string(payload: Any, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if value is None:
        return None
    return str(value)
