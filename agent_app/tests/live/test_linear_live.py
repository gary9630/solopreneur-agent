import os

import httpx
import pytest

pytestmark = pytest.mark.live

REQUIRED_ENV = ("LINEAR_API_KEY",)
LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"


def test_linear_viewer_query_succeeds_without_creating_objects():
    _skip_unless_env(REQUIRED_ENV)

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            os.getenv("LINEAR_GRAPHQL_URL", LINEAR_GRAPHQL_URL),
            headers={
                "Authorization": os.environ["LINEAR_API_KEY"],
                "Content-Type": "application/json",
            },
            json={
                "operationName": "LiveViewerSmoke",
                "query": """
                query LiveViewerSmoke {
                  viewer {
                    id
                    name
                  }
                }
                """,
                "variables": {},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload
    viewer = payload["data"]["viewer"]
    assert isinstance(viewer["id"], str)
    assert viewer["id"]


def _skip_unless_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if _missing_or_placeholder(name)]
    if missing:
        pytest.skip(f"missing live Linear env vars: {', '.join(missing)}")


def _missing_or_placeholder(name: str) -> bool:
    value = os.getenv(name)
    return not value or value.startswith("replace-with-")
