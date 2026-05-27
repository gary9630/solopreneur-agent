import json
from decimal import Decimal

import httpx
import pytest

from deal_agent.connectors import ConnectorError
from deal_agent.connectors.github import GitHubHttpConnector
from deal_agent.connectors.linear import LinearHttpConnector
from deal_agent.connectors.odoo import OdooHttpConnector
from deal_agent.connectors.telegram import TelegramHttpConnector
from deal_agent.models import DealBrief, DeliveryIssue, ExternalRef, IntakeSummary, QuoteDraft
from deal_agent.tool_models import BusinessCardContact


def sample_summary() -> IntakeSummary:
    return IntakeSummary(
        customer_name="ACME",
        contact_name="Ada Lovelace",
        contact_email="ada@example.com",
        problem_statement="Manual deal handoff is slowing delivery.",
        scope_items=["Build an MVP agent", "Connect delivery tools"],
        risks=["External API availability"],
    )


def sample_quote() -> QuoteDraft:
    return QuoteDraft(
        currency="USD",
        line_items=[
            {
                "description": "Hackathon MVP implementation",
                "quantity": Decimal("1"),
                "unit_price": Decimal("4500"),
            }
        ],
        subtotal=Decimal("4500"),
        total=Decimal("4500"),
        notes="Valid for demo use.",
    )


def sample_issues() -> list[DeliveryIssue]:
    return [
        DeliveryIssue(
            title="Build intake flow",
            description="Capture a customer brief and summarize it.",
            labels=["mvp", "intake"],
            priority="High",
        ),
        DeliveryIssue(
            title="Create delivery tracking",
            description="Link Linear and GitHub artifacts.",
            labels=["mvp", "delivery"],
        ),
    ]


def test_odoo_http_connector_posts_json2_payloads_with_auth_and_database_header():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer odoo-secret"
        assert request.headers["X-Odoo-Database"] == "hackathon"
        payload = request.read()
        assert b"odoo-secret" not in payload

        if request.url.path == "/json/2/res.partner/create":
            body = json.loads(payload.decode("utf-8"))
            assert body == {
                "name": "ACME",
                "email": "ada@example.com",
                "comment": "Created by deal-agent run run_1",
            }
            return httpx.Response(200, json={"result": {"id": 1001}})

        if request.url.path == "/json/2/crm.lead/create":
            body = json.loads(payload.decode("utf-8"))
            assert body == {
                "name": "ACME - run_1",
                "partner_id": 1001,
                "contact_name": "Ada Lovelace",
                "email_from": "ada@example.com",
                "description": "Manual deal handoff is slowing delivery.",
            }
            return httpx.Response(200, json={"result": {"id": 101}})

        if request.url.path == "/json/2/sale.order/create":
            body = json.loads(payload.decode("utf-8"))
            assert body == {
                "partner_id": 1001,
                "client_order_ref": "run_1",
                "note": "Valid for demo use.",
                "order_line": [
                    [
                        0,
                        0,
                        {
                            "name": "Hackathon MVP implementation",
                            "product_uom_qty": "1",
                            "price_unit": "4500",
                        },
                    ]
                ],
            }
            return httpx.Response(200, json={"result": {"id": 202}})

        if request.url.path == "/json/2/account.move/create":
            body = json.loads(payload.decode("utf-8"))
            assert body == {
                "partner_id": 1001,
                "move_type": "out_invoice",
                "ref": "run_1",
                "invoice_line_ids": [
                    [
                        0,
                        0,
                        {
                            "name": "Hackathon MVP implementation",
                            "quantity": "1",
                            "price_unit": "4500",
                        },
                    ]
                ],
            }
            return httpx.Response(200, json={"result": {"id": 303}})

        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        database="hackathon",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    lead = connector.create_lead("run_1", DealBrief(message="Build it"), sample_summary())
    quotation = connector.create_quotation("run_1", sample_quote())
    invoice = connector.create_invoice_draft("run_1", sample_quote())

    assert [request.url.path for request in seen] == [
        "/json/2/res.partner/create",
        "/json/2/crm.lead/create",
        "/json/2/sale.order/create",
        "/json/2/account.move/create",
    ]
    assert lead == ExternalRef(
        system="odoo",
        external_id="101",
        metadata={"kind": "lead", "model": "crm.lead", "run_id": "run_1"},
    )
    assert quotation.metadata["kind"] == "quotation"
    assert quotation.external_id == "202"
    assert invoice.metadata["kind"] == "invoice_draft"
    assert invoice.external_id == "303"


def test_odoo_http_connector_accepts_raw_json2_create_results():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/json/2/res.partner/create":
            return httpx.Response(200, json=1001)
        if request.url.path == "/json/2/crm.lead/create":
            return httpx.Response(200, json=[101])
        if request.url.path == "/json/2/sale.order/create":
            return httpx.Response(200, json=202)
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    lead = connector.create_lead("run_1", DealBrief(message="Build it"), sample_summary())
    quotation = connector.create_quotation("run_1", sample_quote())

    assert seen_paths == [
        "/json/2/res.partner/create",
        "/json/2/crm.lead/create",
        "/json/2/sale.order/create",
    ]
    assert lead.external_id == "101"
    assert quotation.external_id == "202"


def test_odoo_http_connector_caches_successful_refs_and_requires_partner_for_later_steps():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request.url.path == "/json/2/res.partner/create":
            return httpx.Response(200, json=1001)
        if request.url.path == "/json/2/crm.lead/create":
            return httpx.Response(200, json=101)
        if request.url.path == "/json/2/sale.order/create":
            return httpx.Response(200, json=202)
        if request.url.path == "/json/2/account.move/create":
            return httpx.Response(200, json=303)
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ConnectorError, match="partner"):
        connector.create_quotation("run_missing", sample_quote())

    first_lead = connector.create_lead("run_1", DealBrief(message="Build it"), sample_summary())
    second_lead = connector.create_lead("run_1", DealBrief(message="Build it"), sample_summary())
    first_quote = connector.create_quotation("run_1", sample_quote())
    second_quote = connector.create_quotation("run_1", sample_quote())
    first_invoice = connector.create_invoice_draft("run_1", sample_quote())
    second_invoice = connector.create_invoice_draft("run_1", sample_quote())

    assert first_lead == second_lead
    assert first_quote == second_quote
    assert first_invoice == second_invoice
    assert request_count == 4


def test_odoo_http_connector_upserts_existing_business_card_contact():
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append((request.url.path, body))
        if request.url.path == "/json/2/res.partner/search_read":
            assert body["domain"] == [["email", "=", "ada@example.com"]]
            return httpx.Response(200, json=[{"id": 77, "name": "Ada Old"}])
        if request.url.path == "/json/2/res.partner/write":
            assert body == {
                "ids": [77],
                "values": {
                    "name": "Ada Lovelace",
                    "email": "ada@example.com",
                    "phone": "+1 555 0100",
                    "website": "https://example.com",
                    "function": "Founder",
                    "company_name": "Analytical Engines LLC",
                    "comment": "Business card captured by deal-agent run card_1",
                },
            }
            return httpx.Response(200, json=True)
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ref = connector.upsert_contact_from_business_card(
        "card_1",
        BusinessCardContact(
            name="Ada Lovelace",
            company="Analytical Engines LLC",
            title="Founder",
            email="ada@example.com",
            phone="+1 555 0100",
            website="https://example.com",
        ),
    )

    assert [path for path, _ in seen] == [
        "/json/2/res.partner/search_read",
        "/json/2/res.partner/write",
    ]
    assert ref == ExternalRef(
        system="odoo",
        external_id="77",
        metadata={"kind": "contact", "model": "res.partner", "run_id": "card_1", "action": "updated"},
    )


def test_odoo_http_connector_creates_business_card_contact_and_lead():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/json/2/res.partner/search_read":
            return httpx.Response(200, json=[])
        if request.url.path == "/json/2/res.partner/create":
            return httpx.Response(200, json=88)
        if request.url.path == "/json/2/crm.lead/create":
            body = json.loads(request.content.decode("utf-8"))
            assert body["partner_id"] == 88
            assert body["contact_name"] == "Ada Lovelace"
            assert body["email_from"] == "ada@example.com"
            return httpx.Response(200, json=99)
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    contact = BusinessCardContact(
        name="Ada Lovelace",
        company="Analytical Engines LLC",
        title="Founder",
        email="ada@example.com",
    )

    contact_ref = connector.upsert_contact_from_business_card("card_2", contact)
    lead_ref = connector.create_crm_lead_for_contact("card_2", contact_ref, contact)

    assert seen_paths == [
        "/json/2/res.partner/search_read",
        "/json/2/res.partner/create",
        "/json/2/crm.lead/create",
    ]
    assert contact_ref.metadata["action"] == "created"
    assert lead_ref == ExternalRef(
        system="odoo",
        external_id="99",
        metadata={"kind": "lead", "model": "crm.lead", "run_id": "card_2"},
    )


def test_odoo_http_connector_looks_up_contacts_and_leads():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/json/2/res.partner/search_read":
            body = json.loads(request.content.decode("utf-8"))
            assert "mobile" not in body["fields"]
            return httpx.Response(200, json=[{"id": 77, "name": "Ada Lovelace", "email": "ada@example.com"}])
        if request.url.path == "/json/2/crm.lead/search_read":
            return httpx.Response(200, json=[{"id": 99, "name": "ACME CRM", "email_from": "ada@example.com"}])
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = connector.lookup_crm("Ada", limit=3)

    assert result.query == "Ada"
    assert result.contacts == [{"id": 77, "name": "Ada Lovelace", "email": "ada@example.com"}]
    assert result.leads == [{"id": 99, "name": "ACME CRM", "email_from": "ada@example.com"}]


def test_odoo_http_connector_writes_deal_context_and_audit_log():
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append((request.url.path, body))
        if request.url.path == "/json/2/deal.agent.deal.context/create":
            return httpx.Response(200, json=501)
        if request.url.path == "/json/2/deal.agent.audit.log/create":
            assert body["deal_context_id"] == 501
            return httpx.Response(200, json=502)
        raise AssertionError(f"unexpected path {request.url.path}")

    connector = OdooHttpConnector(
        base_url="https://odoo.test/",
        token="odoo-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    context_ref = connector.write_deal_context(
        run_id="run_1",
        customer_name="ACME",
        contact_email="ada@example.com",
        source_message="ACME needs Odoo automation.",
        state="quoted",
        crm_lead_id=101,
        sale_order_id=202,
        invoice_id=303,
    )
    audit_ref = connector.write_audit_log(
        run_id="run_1",
        step_name="odoo_lead",
        state_before="NEW",
        state_after="ODOO_LEAD_CREATED",
        service="odoo",
        external_ref="101",
        payload_summary="Created CRM lead",
        deal_context_id=int(context_ref.external_id),
    )

    assert [path for path, _ in seen] == [
        "/json/2/deal.agent.deal.context/create",
        "/json/2/deal.agent.audit.log/create",
    ]
    assert context_ref.metadata["kind"] == "deal_context"
    assert audit_ref.metadata["kind"] == "audit_log"


def test_linear_http_connector_bootstraps_project_and_issues_with_graphql():
    operations: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://linear.test/graphql"
        assert request.headers["Authorization"] == "lin-secret"
        payload = json.loads(request.content.decode("utf-8"))
        operations.append(payload)

        if "projectCreate" in payload["query"]:
            assert payload["variables"]["input"]["teamIds"] == ["team_123"]
            assert payload["variables"]["input"]["name"] == "ACME deal-to-delivery run run_1"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "projectCreate": {
                            "success": True,
                            "project": {
                                "id": "project_1",
                                "url": "https://linear.app/acme/project/project_1",
                            }
                        }
                    }
                },
            )

        if "issueCreate" in payload["query"]:
            issue_input = payload["variables"]["input"]
            assert issue_input["teamId"] == "team_123"
            assert issue_input["projectId"] == "project_1"
            assert issue_input["title"] in {"Build intake flow", "Create delivery tracking"}
            return httpx.Response(
                200,
                json={
                    "data": {
                        "issueCreate": {
                            "success": True,
                            "issue": {
                                "id": f"issue_{len(operations)}",
                                "identifier": f"ACME-{len(operations)}",
                                "url": f"https://linear.app/acme/issue/ACME-{len(operations)}",
                            }
                        }
                    }
                },
            )

        raise AssertionError("unexpected Linear operation")

    connector = LinearHttpConnector(
        api_key="lin-secret",
        team_id="team_123",
        base_url="https://linear.test/graphql",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    refs = connector.bootstrap_project("run_1", sample_summary(), sample_issues())

    assert [operation["operationName"] for operation in operations] == [
        "CreateProject",
        "CreateIssue",
        "CreateIssue",
    ]
    assert refs[0].system == "linear"
    assert refs[0].external_id == "project_1"
    assert refs[0].url == "https://linear.app/acme/project/project_1"
    assert refs[0].metadata == {"kind": "project", "run_id": "run_1"}
    assert [ref.metadata["kind"] for ref in refs[1:]] == ["issue", "issue"]
    assert [ref.external_id for ref in refs[1:]] == ["issue_2", "issue_3"]


def test_linear_http_connector_caches_successful_bootstrap_refs():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content.decode("utf-8"))
        if "projectCreate" in payload["query"]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "projectCreate": {
                            "success": True,
                            "project": {"id": "project_1", "url": "https://linear.test/project_1"},
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {
                            "id": f"issue_{request_count}",
                            "identifier": f"ACME-{request_count}",
                            "url": f"https://linear.test/ACME-{request_count}",
                        },
                    }
                }
            },
        )

    connector = LinearHttpConnector(
        api_key="lin-secret",
        team_id="team_123",
        base_url="https://linear.test/graphql",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    first = connector.bootstrap_project("run_1", sample_summary(), sample_issues())
    second = connector.bootstrap_project("run_1", sample_summary(), sample_issues())

    assert first == second
    assert request_count == 3


def test_linear_http_connector_uses_successful_data_even_with_graphql_errors():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        payload = json.loads(request.content.decode("utf-8"))
        mutation_key = "projectCreate" if "projectCreate" in payload["query"] else "issueCreate"
        entity_key = "project" if mutation_key == "projectCreate" else "issue"
        entity = (
            {"id": "project_1", "url": "https://linear.test/project_1"}
            if entity_key == "project"
            else {"id": f"issue_{call_count}", "identifier": f"ACME-{call_count}", "url": None}
        )
        return httpx.Response(
            200,
            json={
                "errors": [{"message": "non-fatal resolver warning"}],
                "data": {
                    mutation_key: {
                        "success": True,
                        entity_key: entity,
                    }
                },
            },
        )

    connector = LinearHttpConnector(
        api_key="lin-secret",
        team_id="team_123",
        base_url="https://linear.test/graphql",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    refs = connector.bootstrap_project("run_1", sample_summary(), sample_issues())

    assert refs[0].external_id == "project_1"
    assert all(ref.metadata["graphql_errors"] is True for ref in refs)


def test_linear_http_connector_raises_when_mutation_success_is_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"projectCreate": {"success": False, "project": None}}},
        )

    connector = LinearHttpConnector(
        api_key="lin-secret",
        team_id="team_123",
        base_url="https://linear.test/graphql",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ConnectorError) as exc_info:
        connector.bootstrap_project("run_1", sample_summary(), sample_issues())

    assert exc_info.value.status_code == 200
    assert exc_info.value.retryable is False


def test_github_http_connector_creates_issue_ref():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/repos/acme/demo/issues"
        assert request.headers["Authorization"] == "Bearer gh-secret"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["title"] == "[run_1] Deal-to-delivery: ACME"
        assert "Manual deal handoff" in payload["body"]
        assert "LIN-1" in payload["body"]
        assert payload["labels"] == ["deal-agent", "mvp"]
        return httpx.Response(
            201,
            json={
                "id": 987,
                "number": 42,
                "html_url": "https://github.com/acme/demo/issues/42",
            },
        )

    connector = GitHubHttpConnector(
        token="gh-secret",
        owner="acme",
        repo="demo",
        base_url="https://api.github.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ref = connector.create_delivery_issue(
        "run_1",
        sample_summary(),
        [ExternalRef(system="linear", external_id="LIN-1", url="https://linear.test/LIN-1")],
    )

    assert ref == ExternalRef(
        system="github",
        external_id="987",
        url="https://github.com/acme/demo/issues/42",
        metadata={"kind": "delivery_issue", "run_id": "run_1", "number": 42},
    )


def test_github_http_connector_caches_successful_delivery_issue_ref():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            201,
            json={
                "id": 987,
                "number": 42,
                "html_url": "https://github.com/acme/demo/issues/42",
            },
        )

    connector = GitHubHttpConnector(
        token="gh-secret",
        owner="acme",
        repo="demo",
        base_url="https://api.github.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    first = connector.create_delivery_issue("run_1", sample_summary(), [])
    second = connector.create_delivery_issue("run_1", sample_summary(), [])

    assert first == second
    assert request_count == 1


def test_telegram_http_connector_sends_message_ref_without_leaking_token():
    token = "telegram-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/bot{token}/sendMessage"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {
            "chat_id": "chat_123",
            "text": "Deal-to-delivery run complete.",
            "disable_web_page_preview": True,
        }
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 555, "chat": {"id": "chat_123"}}},
        )

    connector = TelegramHttpConnector(
        token=token,
        chat_id="chat_123",
        base_url="https://telegram.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ref = connector.send_status("run_1", "Deal-to-delivery run complete.")

    assert token not in repr(connector)
    assert ref == ExternalRef(
        system="telegram",
        external_id="555",
        metadata={"kind": "message", "run_id": "run_1", "chat_id": "chat_123"},
    )


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [
        (400, False),
        (408, True),
        (409, True),
        (425, True),
        (429, True),
        (500, True),
    ],
)
def test_http_connectors_wrap_http_failures_with_retryability(status_code: int, retryable: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "upstream failed"})

    connector = GitHubHttpConnector(
        token="gh-secret",
        owner="acme",
        repo="demo",
        base_url="https://api.github.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ConnectorError) as exc_info:
        connector.create_delivery_issue("run_1", sample_summary(), [])

    error = exc_info.value
    assert error.status_code == status_code
    assert error.retryable is retryable
    assert "gh-secret" not in str(error)


def test_http_connectors_wrap_request_errors_as_retryable_without_token_leak():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom telegram-secret", request=request)

    connector = TelegramHttpConnector(
        token="telegram-secret",
        chat_id="chat_123",
        base_url="https://telegram.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ConnectorError) as exc_info:
        connector.send_status("run_1", "Deal-to-delivery run complete.")

    error = exc_info.value
    assert error.status_code is None
    assert error.retryable is True
    assert "telegram-secret" not in str(error)


def test_linear_http_connector_treats_unusable_graphql_errors_as_terminal():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "invalid team"}]})

    connector = LinearHttpConnector(
        api_key="lin-secret",
        team_id="team_123",
        base_url="https://linear.test/graphql",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ConnectorError) as exc_info:
        connector.bootstrap_project("run_1", sample_summary(), sample_issues())

    error = exc_info.value
    assert error.status_code == 200
    assert error.retryable is False
    assert "lin-secret" not in str(error)
    assert "invalid team" not in str(error)
