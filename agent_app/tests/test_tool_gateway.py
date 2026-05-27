from fastapi.testclient import TestClient

from deal_agent import main as main_module
from deal_agent.main import app, get_settings
from deal_agent.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "live_workflow_enabled": False,
        "nvidia_api_key": None,
        "odoo_api_key": None,
        "linear_api_key": None,
        "linear_team_id": None,
        "github_token": None,
        "github_repository": None,
        "agent_telegram_bot_token": None,
        "agent_telegram_chat_id": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _override_settings(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_tool_workflow_defaults_to_dry_run_with_fakes():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/deal-to-delivery/run",
        json={"run_id": "tool_run_1", "message": "ACME needs an Odoo prototype."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["live_enabled"] is False
    assert body["run"]["run_id"] == "tool_run_1"
    assert body["run"]["state"] == "COMPLETED"


def test_tool_workflow_live_request_without_host_gate_stays_dry_run(monkeypatch):
    calls = []

    def fail_if_called(settings):
        calls.append(settings)
        raise AssertionError("live factory must not be called")

    monkeypatch.setattr(main_module, "create_live_runner", fail_if_called)
    _override_settings(_settings(live_workflow_enabled=False))
    client = TestClient(app)

    response = client.post(
        "/tools/deal-to-delivery/run",
        json={"run_id": "tool_run_2", "message": "ACME needs an Odoo prototype.", "live": True},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "dry_run"
    assert calls == []


def test_tool_workflow_live_request_with_missing_config_returns_400():
    _override_settings(_settings(live_workflow_enabled=True))
    client = TestClient(app)

    response = client.post(
        "/tools/deal-to-delivery/run",
        json={"run_id": "tool_run_3", "message": "ACME needs an Odoo prototype.", "live": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["missing_config"] == [
        "NVIDIA_API_KEY",
        "ODOO_API_KEY",
        "LINEAR_API_KEY",
        "LINEAR_TEAM_ID",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_CHAT_ID",
    ]


def test_tool_workflow_live_request_uses_live_runner(monkeypatch):
    live_settings = _settings(
        live_workflow_enabled=True,
        nvidia_api_key="nvidia-key",
        odoo_api_key="odoo-key",
        linear_api_key="linear-key",
        linear_team_id="team-id",
        github_token="github-token",
        github_repository="owner/repo",
        agent_telegram_bot_token="telegram-token",
        agent_telegram_chat_id="123456789",
    )
    calls = []

    def fake_live_runner(settings):
        calls.append(settings)
        return main_module.create_demo_runner()

    monkeypatch.setattr(main_module, "create_live_runner", fake_live_runner)
    _override_settings(live_settings)
    client = TestClient(app)

    response = client.post(
        "/tools/deal-to-delivery/run",
        json={"run_id": "tool_run_4", "message": "ACME needs an Odoo prototype.", "live": True},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "live"
    assert response.json()["live_enabled"] is True
    assert response.json()["run"]["state"] == "COMPLETED"
    assert calls == [live_settings]


def test_tool_workflow_rejects_extra_request_fields():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/deal-to-delivery/run",
        json={
            "run_id": "tool_run_extra",
            "message": "ACME needs an Odoo prototype.",
            "unexpected": True,
        },
    )

    assert response.status_code == 422


def test_atomic_deal_prepare_defaults_to_dry_run():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/deal/prepare",
        json={"run_id": "prep_1", "message": "ACME needs an Odoo CRM package."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["live_enabled"] is False
    assert body["run_id"] == "prep_1"
    assert body["intake_summary"]["customer_name"] == "ACME"
    assert body["recommended_next_tools"] == [
        "odoo_create_deal_artifacts",
        "delivery_create_tasks",
        "notify_stakeholder",
    ]


def test_atomic_odoo_deal_artifacts_dry_run_has_planned_actions():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/deal-artifacts",
        json={"run_id": "odoo_1", "message": "ACME needs an Odoo CRM package."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "mode": "dry_run",
        "live_enabled": False,
        "planned_actions": [
            "create Odoo CRM lead",
            "create Odoo quotation",
            "create Odoo draft invoice",
            "write Odoo deal context",
            "write Odoo audit log",
        ],
        "external_refs": [],
    }


def test_atomic_delivery_tasks_dry_run_has_planned_actions():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/delivery/tasks",
        json={"run_id": "delivery_1", "message": "ACME needs an Odoo CRM package."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "mode": "dry_run",
        "live_enabled": False,
        "planned_actions": [
            "create Linear delivery tasks",
            "create GitHub delivery tracking issue",
        ],
        "external_refs": [],
    }


def test_atomic_notify_stakeholder_dry_run_has_planned_actions():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/notify/stakeholder",
        json={"run_id": "notify_1", "message": "Acme delivery package is ready."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "mode": "dry_run",
        "live_enabled": False,
        "planned_actions": ["send Telegram stakeholder update"],
        "external_refs": [],
    }


def test_atomic_odoo_deal_artifacts_live_uses_runner_components(monkeypatch):
    live_settings = _settings(
        live_workflow_enabled=True,
        nvidia_api_key="nvidia-key",
        odoo_api_key="odoo-key",
    )
    calls = []

    def fake_live_runner(settings):
        calls.append(settings)
        return main_module.create_demo_runner()

    monkeypatch.setattr(main_module, "create_live_runner", fake_live_runner)
    _override_settings(live_settings)
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/deal-artifacts",
        json={"run_id": "odoo_live_1", "message": "ACME needs an Odoo CRM package.", "live": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["live_enabled"] is True
    assert [ref["metadata"]["kind"] for ref in body["external_refs"]] == [
        "lead",
        "quotation",
        "invoice_draft",
    ]
    assert calls == [live_settings]


def test_atomic_delivery_tasks_live_uses_runner_components(monkeypatch):
    live_settings = _settings(
        live_workflow_enabled=True,
        nvidia_api_key="nvidia-key",
        linear_api_key="linear-key",
        linear_team_id="team-id",
        github_token="github-token",
        github_repository="owner/repo",
    )
    calls = []

    def fake_live_runner(settings):
        calls.append(settings)
        return main_module.create_demo_runner()

    monkeypatch.setattr(main_module, "create_live_runner", fake_live_runner)
    _override_settings(live_settings)
    client = TestClient(app)

    response = client.post(
        "/tools/delivery/tasks",
        json={"run_id": "delivery_live_1", "message": "ACME needs an Odoo CRM package.", "live": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["live_enabled"] is True
    assert [ref["system"] for ref in body["external_refs"]] == [
        "linear",
        "linear",
        "linear",
        "linear",
        "github",
    ]
    assert calls == [live_settings]
