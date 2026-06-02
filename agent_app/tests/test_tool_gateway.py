from fastapi.testclient import TestClient

from deal_agent import main as main_module
from deal_agent.main import app, get_settings
from deal_agent.config import Settings
from deal_agent.models import ExternalRef
from deal_agent.services.meeting_audio import MeetingAudioResult
from deal_agent.tool_models import MeetingMinutes, MeetingTranscript


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


def test_atomic_deal_prepare_echoes_live_gate_without_side_effects():
    _override_settings(_settings(live_workflow_enabled=True))
    client = TestClient(app)

    response = client.post(
        "/tools/deal/prepare",
        json={
            "run_id": "prep_live_1",
            "message": "Acme Studio wants a two-week Odoo CRM automation package.",
            "live": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["live_enabled"] is True
    assert body["side_effects"] is False


def test_atomic_deal_prepare_extracts_realistic_brief_fields():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/deal/prepare",
        json={
            "run_id": "prep_acme_1",
            "message": (
                "Customer: Acme Studio. Need a two-week Odoo CRM automation package starting next Monday. "
                "Scope: lead capture, quote generation, delivery task tracking, and stakeholder update when "
                "delivery is ready. Budget: USD 8000. Contact: Ada Lovelace, ada@example.com."
            ),
            "live": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["live_enabled"] is False
    assert body["intake_summary"]["customer_name"] == "Acme Studio"
    assert body["intake_summary"]["contact_name"] == "Ada Lovelace"
    assert body["intake_summary"]["contact_email"] == "ada@example.com"
    assert body["intake_summary"]["estimated_budget"] == "8000"
    assert body["quote_draft"]["total"] == "8000"


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
            "create or update Odoo contact",
            "create Odoo CRM lead",
            "create Odoo sale order quotation",
            "create Odoo draft invoice",
            "write Odoo deal context",
            "write Odoo audit log",
        ],
        "external_refs": [],
    }


def test_atomic_odoo_contact_dry_run_has_planned_actions():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/contact",
        json={
            "run_id": "odoo_contact_1",
            "customer_name": "Acme Studio",
            "contact_name": "Ada Lovelace",
            "contact_email": "ada@example.com",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "mode": "dry_run",
        "live_enabled": False,
        "planned_actions": ["create or update Odoo contact"],
        "external_refs": [],
    }


def test_atomic_odoo_sale_order_dry_run_has_planned_actions():
    _override_settings(_settings())
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/sale-order",
        json={
            "run_id": "odoo_sale_1",
            "partner_id": "1001",
            "quote_draft": {
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Odoo CRM automation package",
                        "quantity": "1",
                        "unit_price": "8000",
                    }
                ],
                "subtotal": "8000",
                "tax": "0",
                "total": "8000",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "mode": "dry_run",
        "live_enabled": False,
        "planned_actions": ["create Odoo sale order quotation"],
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
        "contact",
        "lead",
        "quotation",
        "invoice_draft",
    ]
    assert calls == [live_settings]


def test_atomic_odoo_deal_artifacts_live_uses_prepared_inputs_without_nim_reparse(monkeypatch):
    live_settings = _settings(
        live_workflow_enabled=True,
        nvidia_api_key="nvidia-key",
        odoo_api_key="odoo-key",
    )
    runner = main_module.create_demo_runner()

    class FailingModels:
        def extract_intake(self, message):
            raise AssertionError("prepared deal inputs should avoid NIM reparse")

        def draft_quote(self, summary):
            raise AssertionError("prepared quote inputs should avoid NIM reparse")

    runner.models = FailingModels()
    monkeypatch.setattr(main_module, "create_live_runner", lambda settings: runner)
    _override_settings(live_settings)
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/deal-artifacts",
        json={
            "run_id": "odoo_live_prepared_1",
            "message": "Original operator approval.",
            "deal_brief": {
                "customer_name": "Acme Studio",
                "contact_name": "Ada Lovelace",
                "contact_email": "ada@example.com",
                "problem_statement": "Acme Studio needs Odoo CRM automation.",
                "scope_items": ["lead capture", "quote generation"],
                "goals": ["prepare Odoo draft artifacts"],
                "assumptions": [],
                "risks": [],
                "estimated_budget": "8000",
                "timeline": "two weeks",
                "confidence": 0.9,
            },
            "quote_draft": {
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Odoo CRM automation package",
                        "quantity": "1",
                        "unit_price": "8000",
                    }
                ],
                "subtotal": "8000",
                "tax": "0",
                "total": "8000",
            },
            "live": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert [ref["metadata"]["kind"] for ref in body["external_refs"]][:4] == [
        "contact",
        "lead",
        "quotation",
        "invoice_draft",
    ]


def test_atomic_odoo_deal_artifacts_live_with_prepared_inputs_does_not_require_nvidia(monkeypatch):
    live_settings = _settings(
        live_workflow_enabled=True,
        nvidia_api_key=None,
        odoo_api_key="odoo-key",
    )
    monkeypatch.setattr(main_module, "create_live_runner", lambda settings: main_module.create_demo_runner())
    _override_settings(live_settings)
    client = TestClient(app)

    response = client.post(
        "/tools/odoo/deal-artifacts",
        json={
            "run_id": "odoo_live_prepared_no_nim_1",
            "message": "Original operator approval.",
            "deal_brief": {
                "customer_name": "Acme Studio",
                "contact_name": "Ada Lovelace",
                "contact_email": "ada@example.com",
                "problem_statement": "Acme Studio needs Odoo CRM automation.",
                "scope_items": ["lead capture", "quote generation"],
                "goals": ["prepare Odoo draft artifacts"],
                "assumptions": [],
                "risks": [],
                "estimated_budget": "8000",
                "timeline": "two weeks",
                "confidence": 0.9,
            },
            "quote_draft": {
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Odoo CRM automation package",
                        "quantity": "1",
                        "unit_price": "8000",
                    }
                ],
                "subtotal": "8000",
                "tax": "0",
                "total": "8000",
            },
            "live": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "live"


def test_atomic_odoo_trace_uses_odoo_addon_state_selection():
    captured: dict[str, dict] = {}

    class TraceOdoo:
        def write_deal_context(self, **payload):
            captured["context"] = payload
            return ExternalRef(
                system="odoo",
                external_id="501",
                metadata={"kind": "deal_context", "run_id": payload["run_id"]},
            )

        def write_audit_log(self, **payload):
            captured["audit"] = payload
            return ExternalRef(
                system="odoo",
                external_id="502",
                metadata={"kind": "audit_log", "run_id": payload["run_id"]},
            )

    refs = [
        ExternalRef(system="odoo", external_id="101", metadata={"kind": "lead"}),
        ExternalRef(system="odoo", external_id="202", metadata={"kind": "quotation"}),
        ExternalRef(system="odoo", external_id="303", metadata={"kind": "invoice_draft"}),
    ]
    summary = main_module.IntakeSummary(
        customer_name="Acme Studio",
        contact_email="ada@example.com",
        problem_statement="Acme needs Odoo automation.",
    )

    trace_refs = main_module._write_optional_atomic_odoo_trace(
        TraceOdoo(),
        "run_1",
        "Acme needs Odoo automation.",
        summary,
        refs,
    )

    assert captured["context"]["state"] == "quoted"
    assert captured["audit"]["state_after"] == "quoted"
    assert [ref.metadata["kind"] for ref in trace_refs] == ["deal_context", "audit_log"]


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


def test_meeting_audio_tool_defaults_to_dry_run():
    _override_settings(_settings(live_workflow_enabled=False))
    client = TestClient(app)

    response = client.post(
        "/tools/meeting/audio",
        json={
            "run_id": "audio_1",
            "audio_base64": "YXVkaW8=",
            "mime_type": "audio/wav",
            "source": "audio",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["live_enabled"] is False
    assert "transcribe meeting audio" in body["planned_actions"]


def test_meeting_audio_tool_live_uses_processor(monkeypatch):
    _override_settings(_settings(live_workflow_enabled=True, nvidia_api_key="secret"))

    class StubProcessor:
        def process(self, run_id, audio_base64, mime_type, filename=None, language_hint=None):
            return MeetingAudioResult(
                run_id=run_id,
                transcript=MeetingTranscript(language="en", transcript="We approved launch.", confidence=0.9),
                minutes=MeetingMinutes(language="en", summary="Launch approved."),
                audio_model="audio-model",
                minutes_model="text-model",
            )

    monkeypatch.setattr(main_module, "create_meeting_audio_processor", lambda settings: StubProcessor())
    client = TestClient(app)

    response = client.post(
        "/tools/meeting/audio",
        json={
            "run_id": "audio_2",
            "audio_base64": "YXVkaW8=",
            "mime_type": "audio/wav",
            "source": "audio",
            "live": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["live_enabled"] is True
    assert body["transcript"]["transcript"] == "We approved launch."
    assert body["minutes"]["summary"] == "Launch approved."


def test_meeting_audio_tool_live_with_missing_config_returns_400():
    _override_settings(_settings(live_workflow_enabled=True))
    client = TestClient(app)

    response = client.post(
        "/tools/meeting/audio",
        json={
            "run_id": "audio_3",
            "audio_base64": "YXVkaW8=",
            "mime_type": "audio/wav",
            "source": "audio",
            "live": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["missing_config"] == ["NVIDIA_API_KEY"]
