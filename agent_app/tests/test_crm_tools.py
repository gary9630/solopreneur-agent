from fastapi.testclient import TestClient

from deal_agent import main as main_module
from deal_agent.config import Settings
from deal_agent.main import app, get_settings
from deal_agent.models import ExternalRef
from deal_agent.tool_models import BusinessCardContact, CrmLookupResult


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def _settings(**overrides) -> Settings:
    values = {
        "live_workflow_enabled": False,
        "nvidia_api_key": "nvidia-key",
        "odoo_api_key": "odoo-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _override_settings(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings


class StubExtractor:
    def extract(self, image_base64: str, mime_type: str) -> BusinessCardContact:
        return BusinessCardContact(
            name="Ada Lovelace",
            company="Analytical Engines LLC",
            title="Founder",
            email="ada@example.com",
            confidence=0.92,
        )


class StubOdooCrm:
    def __init__(self) -> None:
        self.created = []

    def upsert_contact_from_business_card(self, run_id, contact):
        self.created.append(("contact", run_id, contact.email))
        return ExternalRef(
            system="odoo",
            external_id="77",
            metadata={"kind": "contact", "run_id": run_id, "action": "created"},
        )

    def create_crm_lead_for_contact(self, run_id, contact_ref, contact):
        self.created.append(("lead", run_id, contact_ref.external_id))
        return ExternalRef(
            system="odoo",
            external_id="99",
            metadata={"kind": "lead", "run_id": run_id},
        )

    def lookup_crm(self, query, *, limit=5):
        return CrmLookupResult(
            query=query,
            contacts=[{"id": 77, "name": "Ada Lovelace", "email": "ada@example.com"}],
            leads=[{"id": 99, "name": "ACME CRM", "email_from": "ada@example.com"}],
        )


def test_business_card_tool_dry_run_extracts_contact_without_odoo_side_effect(monkeypatch):
    odoo = StubOdooCrm()
    monkeypatch.setattr(main_module, "create_business_card_extractor", lambda settings: StubExtractor())
    monkeypatch.setattr(main_module, "create_odoo_crm_connector", lambda settings: odoo)
    _override_settings(_settings(live_workflow_enabled=False))
    client = TestClient(app)

    response = client.post(
        "/tools/crm/business-card",
        json={"run_id": "card_1", "image_base64": "abc123", "mime_type": "image/jpeg"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["contact"]["email"] == "ada@example.com"
    assert body["planned_actions"] == ["upsert Odoo contact", "create Odoo CRM lead"]
    assert odoo.created == []


def test_business_card_tool_live_creates_contact_and_lead(monkeypatch):
    odoo = StubOdooCrm()
    monkeypatch.setattr(main_module, "create_business_card_extractor", lambda settings: StubExtractor())
    monkeypatch.setattr(main_module, "create_odoo_crm_connector", lambda settings: odoo)
    _override_settings(_settings(live_workflow_enabled=True))
    client = TestClient(app)

    response = client.post(
        "/tools/crm/business-card",
        json={"run_id": "card_2", "image_base64": "abc123", "mime_type": "image/jpeg", "live": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert [(ref["system"], ref["metadata"]["kind"]) for ref in body["external_refs"]] == [
        ("odoo", "contact"),
        ("odoo", "lead"),
    ]
    assert odoo.created == [
        ("contact", "card_2", "ada@example.com"),
        ("lead", "card_2", "77"),
    ]


def test_crm_lookup_tool_requires_live_gate_for_odoo_query(monkeypatch):
    odoo = StubOdooCrm()
    monkeypatch.setattr(main_module, "create_odoo_crm_connector", lambda settings: odoo)
    _override_settings(_settings(live_workflow_enabled=False))
    client = TestClient(app)

    response = client.post("/tools/crm/lookup", json={"query": "Ada", "live": True})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dry_run"
    assert body["result"]["query"] == "Ada"
    assert body["result"]["contacts"] == []


def test_crm_lookup_tool_live_returns_odoo_results(monkeypatch):
    monkeypatch.setattr(main_module, "create_odoo_crm_connector", lambda settings: StubOdooCrm())
    _override_settings(_settings(live_workflow_enabled=True))
    client = TestClient(app)

    response = client.post("/tools/crm/lookup", json={"query": "Ada", "live": True})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["result"]["contacts"][0]["email"] == "ada@example.com"
    assert body["result"]["leads"][0]["name"] == "ACME CRM"
