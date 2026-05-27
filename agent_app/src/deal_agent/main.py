from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints

from deal_agent.config import Settings, settings
from deal_agent.connectors import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
    OdooHttpConnector,
    TelegramHttpConnector,
)
from deal_agent.live_factory import _normalize_nim_base_url, create_live_runner
from deal_agent.models import DealBrief, WorkflowRun
from deal_agent.nim_client import NimVisionClient
from deal_agent.runner import DealWorkflowRunner, WorkflowRunFailed
from deal_agent.services import FakeModelServices
from deal_agent.services.business_card import BusinessCardExtractor
from deal_agent.tool_models import (
    BusinessCardToolRequest,
    CrmLookupRequest,
    CrmLookupResult,
    DealPrepareRequest,
    DeliveryTasksRequest,
    NotifyStakeholderRequest,
    OdooDealArtifactsRequest,
    ToolWorkflowRequest,
    ToolWorkflowResponse,
)

app = FastAPI(title="Deal Agent")

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DemoWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: NonBlankStr
    message: NonBlankStr


def create_demo_runner() -> DealWorkflowRunner:
    return DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )


def get_settings() -> Settings:
    return settings


def create_business_card_extractor(app_settings: Settings) -> BusinessCardExtractor:
    model = app_settings.nim_vision_model or app_settings.nim_model
    return BusinessCardExtractor(
        NimVisionClient(
            api_key=app_settings.nvidia_api_key or "",
            model=model,
            base_url=_normalize_nim_base_url(app_settings.nim_base_url),
        )
    )


def create_odoo_crm_connector(app_settings: Settings) -> OdooHttpConnector:
    return OdooHttpConnector(
        base_url=app_settings.odoo_url,
        token=app_settings.odoo_api_key or "",
        database=app_settings.odoo_database,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workflows/demo", response_model=WorkflowRun)
def run_demo_workflow(
    request: DemoWorkflowRequest,
    runner: DealWorkflowRunner = Depends(create_demo_runner),
) -> WorkflowRun:
    try:
        return runner.run(request.run_id, request.message)
    except WorkflowRunFailed as exc:
        return exc.run


@app.post("/tools/deal-to-delivery/run", response_model=ToolWorkflowResponse)
def run_tool_workflow(
    request: ToolWorkflowRequest,
    app_settings: Settings = Depends(get_settings),
) -> ToolWorkflowResponse:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return ToolWorkflowResponse(
            mode="dry_run",
            live_enabled=False,
            run=_run_workflow(create_demo_runner(), request.run_id, request.message),
        )

    missing_config = app_settings.missing_live_workflow_config()
    if missing_config:
        raise HTTPException(
            status_code=400,
            detail={"missing_config": missing_config},
        )

    return ToolWorkflowResponse(
        mode="live",
        live_enabled=True,
        run=_run_workflow(create_live_runner(app_settings), request.run_id, request.message),
    )


def _run_workflow(runner: DealWorkflowRunner, run_id: str, message: str) -> WorkflowRun:
    try:
        return runner.run(run_id, message)
    except WorkflowRunFailed as exc:
        return exc.run


@app.post("/tools/crm/business-card")
def run_business_card_tool(
    request: BusinessCardToolRequest,
    app_settings: Settings = Depends(get_settings),
) -> dict:
    extractor = create_business_card_extractor(app_settings)
    contact = extractor.extract(request.image_base64, request.mime_type)
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
            "mode": "dry_run",
            "live_enabled": False,
            "contact": contact.model_dump(mode="json"),
            "planned_actions": ["upsert Odoo contact", "create Odoo CRM lead"],
            "external_refs": [],
        }

    missing_config = _missing_crm_business_card_config(app_settings)
    if missing_config:
        raise HTTPException(status_code=400, detail={"missing_config": missing_config})

    odoo = create_odoo_crm_connector(app_settings)
    contact_ref = odoo.upsert_contact_from_business_card(request.run_id, contact)
    lead_ref = odoo.create_crm_lead_for_contact(request.run_id, contact_ref, contact)
    return {
        "mode": "live",
        "live_enabled": True,
        "contact": contact.model_dump(mode="json"),
        "planned_actions": [],
        "external_refs": [
            contact_ref.model_dump(mode="json"),
            lead_ref.model_dump(mode="json"),
        ],
    }


@app.post("/tools/deal/prepare")
def run_deal_prepare_tool(request: DealPrepareRequest) -> dict:
    runner = create_demo_runner()
    summary = runner.models.extract_intake(request.message)
    quote = runner.models.draft_quote(summary)
    issues = runner.models.break_down_issues(summary)
    return {
        "mode": "dry_run",
        "live_enabled": False,
        "run_id": request.run_id,
        "intake_summary": summary.model_dump(mode="json"),
        "quote_draft": quote.model_dump(mode="json"),
        "delivery_issues": [issue.model_dump(mode="json") for issue in issues],
        "recommended_next_tools": [
            "odoo_create_deal_artifacts",
            "delivery_create_tasks",
            "notify_stakeholder",
        ],
    }


@app.post("/tools/odoo/deal-artifacts")
def run_odoo_deal_artifacts_tool(
    request: OdooDealArtifactsRequest,
    app_settings: Settings = Depends(get_settings),
) -> dict:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
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

    missing_config = _missing_odoo_deal_artifacts_config(app_settings)
    if missing_config:
        raise HTTPException(status_code=400, detail={"missing_config": missing_config})

    runner = create_live_runner(app_settings)
    summary = runner.models.extract_intake(request.message)
    quote = runner.models.draft_quote(summary)
    brief = DealBrief(message=request.message)
    refs = [
        runner.odoo.create_lead(request.run_id, brief, summary),
        runner.odoo.create_quotation(request.run_id, quote),
        runner.odoo.create_invoice_draft(request.run_id, quote),
    ]
    refs.extend(_write_optional_atomic_odoo_trace(runner.odoo, request.run_id, request.message, summary, refs))
    return {
        "mode": "live",
        "live_enabled": True,
        "external_refs": [ref.model_dump(mode="json") for ref in refs],
    }


@app.post("/tools/delivery/tasks")
def run_delivery_tasks_tool(
    request: DeliveryTasksRequest,
    app_settings: Settings = Depends(get_settings),
) -> dict:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
            "mode": "dry_run",
            "live_enabled": False,
            "planned_actions": [
                "create Linear delivery tasks",
                "create GitHub delivery tracking issue",
            ],
            "external_refs": [],
        }

    missing_config = _missing_delivery_tasks_config(app_settings)
    if missing_config:
        raise HTTPException(status_code=400, detail={"missing_config": missing_config})

    runner = create_live_runner(app_settings)
    summary = runner.models.extract_intake(request.message)
    issues = runner.models.break_down_issues(summary)
    linear_refs = runner.linear.bootstrap_project(request.run_id, summary, issues)
    github_ref = runner.github.create_delivery_issue(request.run_id, summary, linear_refs)
    refs = [*linear_refs, github_ref]
    return {
        "mode": "live",
        "live_enabled": True,
        "external_refs": [ref.model_dump(mode="json") for ref in refs],
    }


@app.post("/tools/notify/stakeholder")
def run_notify_stakeholder_tool(
    request: NotifyStakeholderRequest,
    app_settings: Settings = Depends(get_settings),
) -> dict:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
            "mode": "dry_run",
            "live_enabled": False,
            "planned_actions": ["send Telegram stakeholder update"],
            "external_refs": [],
        }

    if not app_settings.agent_telegram_bot_token or not app_settings.agent_telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail={"missing_config": ["AGENT_TELEGRAM_BOT_TOKEN", "AGENT_TELEGRAM_CHAT_ID"]},
        )

    telegram_ref = TelegramHttpConnector(
        token=app_settings.agent_telegram_bot_token,
        chat_id=app_settings.agent_telegram_chat_id,
    ).send_status(request.run_id, request.message)
    return {
        "mode": "live",
        "live_enabled": True,
        "external_refs": [telegram_ref.model_dump(mode="json")],
    }


@app.post("/tools/crm/lookup")
def run_crm_lookup_tool(
    request: CrmLookupRequest,
    app_settings: Settings = Depends(get_settings),
) -> dict:
    live_enabled = bool(request.live and app_settings.live_workflow_enabled)
    if not live_enabled:
        return {
            "mode": "dry_run",
            "live_enabled": False,
            "result": CrmLookupResult(query=request.query).model_dump(mode="json"),
        }

    missing_config = _missing_odoo_config(app_settings)
    if missing_config:
        raise HTTPException(status_code=400, detail={"missing_config": missing_config})

    result = create_odoo_crm_connector(app_settings).lookup_crm(request.query)
    return {
        "mode": "live",
        "live_enabled": True,
        "result": result.model_dump(mode="json"),
    }


def _missing_crm_business_card_config(app_settings: Settings) -> list[str]:
    missing = _missing_odoo_config(app_settings)
    if not app_settings.nvidia_api_key:
        missing.insert(0, "NVIDIA_API_KEY")
    return missing


def _missing_odoo_deal_artifacts_config(app_settings: Settings) -> list[str]:
    missing = _missing_odoo_config(app_settings)
    if not app_settings.nvidia_api_key:
        missing.insert(0, "NVIDIA_API_KEY")
    return missing


def _missing_delivery_tasks_config(app_settings: Settings) -> list[str]:
    missing = []
    if not app_settings.nvidia_api_key:
        missing.append("NVIDIA_API_KEY")
    if not app_settings.linear_api_key:
        missing.append("LINEAR_API_KEY")
    if not app_settings.linear_team_id:
        missing.append("LINEAR_TEAM_ID")
    if not app_settings.github_token:
        missing.append("GITHUB_TOKEN")
    if not app_settings.github_repository:
        missing.append("GITHUB_REPOSITORY")
    return missing


def _write_optional_atomic_odoo_trace(
    odoo: object,
    run_id: str,
    message: str,
    summary: object,
    refs: list,
) -> list:
    write_deal_context = getattr(odoo, "write_deal_context", None)
    write_audit_log = getattr(odoo, "write_audit_log", None)
    if not callable(write_deal_context) or not callable(write_audit_log):
        return []

    lead_ref = _first_ref_kind(refs, "lead")
    quotation_ref = _first_ref_kind(refs, "quotation")
    invoice_ref = _first_ref_kind(refs, "invoice_draft")
    customer_name = getattr(summary, "customer_name", None) or "Customer"
    contact_email = getattr(summary, "contact_email", None)
    context_ref = write_deal_context(
        run_id=run_id,
        customer_name=customer_name,
        contact_email=contact_email,
        source_message=message,
        state="odoo_artifacts_created",
        crm_lead_id=_safe_int(getattr(lead_ref, "external_id", None)),
        sale_order_id=_safe_int(getattr(quotation_ref, "external_id", None)),
        invoice_id=_safe_int(getattr(invoice_ref, "external_id", None)),
    )
    audit_ref = write_audit_log(
        run_id=run_id,
        step_name="odoo_create_deal_artifacts",
        state_before="deal_prepared",
        state_after="odoo_artifacts_created",
        service="odoo",
        external_ref=context_ref.external_id,
        payload_summary="Created atomic Odoo lead, quotation, draft invoice, and deal context.",
        deal_context_id=_safe_int(context_ref.external_id),
    )
    return [context_ref, audit_ref]


def _first_ref_kind(refs: list, kind: str):
    for ref in refs:
        metadata = getattr(ref, "metadata", {})
        if isinstance(metadata, dict) and metadata.get("kind") == kind:
            return ref
    return None


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _missing_odoo_config(app_settings: Settings) -> list[str]:
    if not app_settings.odoo_api_key:
        return ["ODOO_API_KEY"]
    return []
