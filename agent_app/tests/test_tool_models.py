import pytest
from pydantic import ValidationError

from deal_agent.config import Settings
from deal_agent.tool_models import BusinessCardContact, ToolWorkflowRequest


def test_tool_workflow_request_strips_fields_and_defaults_to_dry_run():
    request = ToolWorkflowRequest(
        run_id="  live_run_1  ",
        message="  ACME needs an Odoo delivery workflow.  ",
    )

    assert request.run_id == "live_run_1"
    assert request.message == "ACME needs an Odoo delivery workflow."
    assert request.live is False


def test_tool_workflow_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ToolWorkflowRequest(run_id="run_1", message="hello", unexpected=True)


def test_business_card_contact_normalizes_optional_fields():
    contact = BusinessCardContact(
        name="  Ada Lovelace  ",
        company="  Analytical Engines LLC  ",
        title="  Founder  ",
        email="  ada@example.com  ",
        phone="  +1 555 0100  ",
        website="  https://example.com  ",
        raw_text="raw OCR",
        confidence=0.91,
    )

    assert contact.name == "Ada Lovelace"
    assert contact.company == "Analytical Engines LLC"
    assert contact.email == "ada@example.com"
    assert contact.confidence == 0.91


def test_agent_telegram_allowed_user_ids_parse_csv(monkeypatch):
    monkeypatch.setenv("AGENT_TELEGRAM_ALLOWED_USER_IDS", "123456789, 42,not-a-number")

    settings = Settings(_env_file=None)

    assert settings.agent_telegram_allowed_user_id_set() == {123456789, 42}


def test_missing_live_workflow_config_reports_names_only(monkeypatch):
    for name in [
        "NVIDIA_API_KEY",
        "ODOO_API_KEY",
        "LINEAR_API_KEY",
        "LINEAR_TEAM_ID",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_CHAT_ID",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    missing = settings.missing_live_workflow_config()

    assert missing == [
        "NVIDIA_API_KEY",
        "ODOO_API_KEY",
        "LINEAR_API_KEY",
        "LINEAR_TEAM_ID",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_CHAT_ID",
    ]
    assert all("replace-with" not in name for name in missing)


def test_missing_agent_telegram_config_reports_required_names(monkeypatch):
    monkeypatch.delenv("AGENT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_TELEGRAM_ALLOWED_USER_IDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.missing_agent_telegram_config() == [
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_ALLOWED_USER_IDS",
    ]
