from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from deal_agent.models import StrictModel, WorkflowRun


NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CleanStr = Annotated[str, StringConstraints(strip_whitespace=True)]


class ToolWorkflowRequest(StrictModel):
    run_id: NonBlankStr
    message: NonBlankStr
    live: bool = False


class ToolWorkflowResponse(StrictModel):
    mode: str
    live_enabled: bool
    run: WorkflowRun | None = None
    missing_config: list[str] = Field(default_factory=list)


class BusinessCardContact(StrictModel):
    name: CleanStr | None = None
    company: CleanStr | None = None
    title: CleanStr | None = None
    email: CleanStr | None = None
    phone: CleanStr | None = None
    website: CleanStr | None = None
    raw_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class BusinessCardToolRequest(StrictModel):
    run_id: NonBlankStr
    image_base64: NonBlankStr
    mime_type: NonBlankStr
    live: bool = False


class CrmLookupRequest(StrictModel):
    query: NonBlankStr
    live: bool = False


class CrmLookupResult(StrictModel):
    query: str
    contacts: list[dict[str, str | int | None]] = Field(default_factory=list)
    leads: list[dict[str, str | int | None]] = Field(default_factory=list)


class DealPrepareRequest(StrictModel):
    run_id: NonBlankStr
    message: NonBlankStr
    live: bool = False


class OdooDealArtifactsRequest(StrictModel):
    run_id: NonBlankStr
    message: NonBlankStr
    deal_brief: dict = Field(default_factory=dict)
    quote_draft: dict = Field(default_factory=dict)
    live: bool = False


class OdooContactRequest(StrictModel):
    run_id: NonBlankStr
    customer_name: CleanStr | None = None
    contact_name: CleanStr | None = None
    contact_email: CleanStr | None = None
    phone: CleanStr | None = None
    live: bool = False


class OdooCrmLeadRequest(StrictModel):
    run_id: NonBlankStr
    partner_id: NonBlankStr
    customer_name: CleanStr | None = None
    contact_name: CleanStr | None = None
    contact_email: CleanStr | None = None
    phone: CleanStr | None = None
    problem_statement: CleanStr | None = None
    live: bool = False


class OdooSaleOrderRequest(StrictModel):
    run_id: NonBlankStr
    partner_id: NonBlankStr
    quote_draft: dict = Field(default_factory=dict)
    live: bool = False


class OdooDraftInvoiceRequest(StrictModel):
    run_id: NonBlankStr
    partner_id: NonBlankStr
    quote_draft: dict = Field(default_factory=dict)
    live: bool = False


class DeliveryTasksRequest(StrictModel):
    run_id: NonBlankStr
    message: NonBlankStr
    deal_brief: dict = Field(default_factory=dict)
    delivery_issues: list[dict] = Field(default_factory=list)
    live: bool = False


class NotifyStakeholderRequest(StrictModel):
    run_id: NonBlankStr
    message: NonBlankStr
    external_refs: list[dict] = Field(default_factory=list)
    live: bool = False
