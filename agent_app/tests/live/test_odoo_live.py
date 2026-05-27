import os

import httpx
import pytest

pytestmark = pytest.mark.live

REQUIRED_ENV = ("ODOO_URL", "ODOO_API_KEY", "ODOO_DATABASE")


def test_odoo_version_endpoint_succeeds_without_creating_records():
    _skip_unless_env(REQUIRED_ENV)

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{os.environ['ODOO_URL'].rstrip('/')}/web/webclient/version_info",
            headers={
                "Authorization": f"Bearer {os.environ['ODOO_API_KEY']}",
                "Content-Type": "application/json",
                "X-Odoo-Database": os.environ["ODOO_DATABASE"],
            },
            json={},
        )

    assert response.status_code == 200
    payload = response.json()
    version_info = payload.get("result", payload)
    assert isinstance(version_info, dict)
    assert any(
        key in version_info
        for key in ("server_version", "server_version_info", "version")
    )


def _skip_unless_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if _missing_or_placeholder(name)]
    if missing:
        pytest.skip(f"missing live Odoo env vars: {', '.join(missing)}")


def _missing_or_placeholder(name: str) -> bool:
    value = os.getenv(name)
    return not value or value.startswith("replace-with-")
