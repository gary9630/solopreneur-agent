from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from deal_agent.connectors.base import ConnectorError, request_json
from deal_agent.models import DealBrief, ExternalRef, IntakeSummary, QuoteDraft, QuoteLineItem


class OdooHttpConnector:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        database: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not token:
            raise ValueError("token is required")

        self.base_url = base_url.rstrip("/")
        self._token = token
        self.database = database
        self._http_client = http_client or httpx.Client(timeout=30.0)
        self._partner_ids: dict[str, int] = {}
        self._lead_refs: dict[str, ExternalRef] = {}
        self._quotation_refs: dict[str, ExternalRef] = {}
        self._invoice_refs: dict[str, ExternalRef] = {}

    def __repr__(self) -> str:
        return f"OdooHttpConnector(base_url={self.base_url!r}, database={self.database!r})"

    def create_lead(self, run_id: str, brief: DealBrief, summary: IntakeSummary) -> ExternalRef:
        if run_id in self._lead_refs:
            return _copy_ref(self._lead_refs[run_id])

        partner_id = self._ensure_partner(run_id, brief, summary)
        payload = {
            "name": f"{summary.customer_name or brief.customer_name or 'Deal'} - {run_id}",
            "partner_id": partner_id,
            "contact_name": summary.contact_name or brief.contact_name,
            "email_from": summary.contact_email or brief.contact_email,
            "description": summary.problem_statement,
        }
        lead_ref = self._create(
            "crm.lead",
            "create",
            _drop_none(payload),
            kind="lead",
            run_id=run_id,
        )
        self._lead_refs[run_id] = lead_ref
        return _copy_ref(lead_ref)

    def create_quotation(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        if run_id in self._quotation_refs:
            return _copy_ref(self._quotation_refs[run_id])

        partner_id = self._require_partner(run_id, "quotation")
        payload = {
            "partner_id": partner_id,
            "client_order_ref": run_id,
            "note": quote.notes,
            "order_line": [_sale_line_command(item) for item in quote.line_items],
        }
        quotation_ref = self._create(
            "sale.order",
            "create",
            _drop_none(payload),
            kind="quotation",
            run_id=run_id,
        )
        self._quotation_refs[run_id] = quotation_ref
        return _copy_ref(quotation_ref)

    def create_invoice_draft(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        if run_id in self._invoice_refs:
            return _copy_ref(self._invoice_refs[run_id])

        partner_id = self._require_partner(run_id, "invoice draft")
        payload = {
            "partner_id": partner_id,
            "move_type": "out_invoice",
            "ref": run_id,
            "invoice_line_ids": [_invoice_line_command(item) for item in quote.line_items],
        }
        invoice_ref = self._create(
            "account.move",
            "create",
            _drop_none(payload),
            kind="invoice_draft",
            run_id=run_id,
        )
        self._invoice_refs[run_id] = invoice_ref
        return _copy_ref(invoice_ref)

    def _ensure_partner(self, run_id: str, brief: DealBrief, summary: IntakeSummary) -> int:
        if run_id in self._partner_ids:
            return self._partner_ids[run_id]

        payload = {
            "name": summary.customer_name
            or brief.customer_name
            or summary.contact_name
            or brief.contact_name
            or summary.contact_email
            or brief.contact_email
            or f"Deal {run_id}",
            "email": summary.contact_email or brief.contact_email,
            "comment": f"Created by deal-agent run {run_id}",
        }
        partner_id = self._create_id("res.partner", "create", _drop_none(payload))
        self._partner_ids[run_id] = partner_id
        return partner_id

    def _require_partner(self, run_id: str, artifact: str) -> int:
        partner_id = self._partner_ids.get(run_id)
        if partner_id is None:
            raise ConnectorError(
                f"Odoo partner is required before creating a {artifact}",
                retryable=False,
            )
        return partner_id

    def _create(
        self,
        model: str,
        method: str,
        payload: dict[str, Any],
        *,
        kind: str,
        run_id: str,
    ) -> ExternalRef:
        external_id = self._create_id(model, method, payload)
        return ExternalRef(
            system="odoo",
            external_id=str(external_id),
            metadata={"kind": kind, "model": model, "run_id": run_id},
        )

    def _create_id(self, model: str, method: str, payload: dict[str, Any]) -> int:
        result = request_json(
            self._http_client,
            "Odoo",
            f"{self.base_url}/json/2/{model}/{method}",
            headers=self._headers(),
            json=payload,
            require_object=False,
        )
        return _extract_odoo_id(result)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if self.database:
            headers["X-Odoo-Database"] = self.database
        return headers


def _sale_line_command(item: QuoteLineItem) -> list[Any]:
    payload: dict[str, str] = {
        "name": item.description,
        "product_uom_qty": _decimal_string(item.quantity),
        "price_unit": _decimal_string(item.unit_price),
    }
    return [0, 0, payload]


def _invoice_line_command(item: QuoteLineItem) -> list[Any]:
    payload: dict[str, str] = {
        "name": item.description,
        "quantity": _decimal_string(item.quantity),
        "price_unit": _decimal_string(item.unit_price),
    }
    return [0, 0, payload]


def _extract_odoo_id(payload: Any) -> int:
    result = payload.get("result", payload) if isinstance(payload, dict) else payload
    if isinstance(result, list):
        if not result:
            raise ConnectorError("Odoo response did not include an id", retryable=False, status_code=200)
        result = result[0]
    if isinstance(result, dict):
        external_id = result.get("id")
    else:
        external_id = result

    if external_id is None:
        raise ConnectorError("Odoo response did not include an id", retryable=False, status_code=200)
    try:
        return int(external_id)
    except (TypeError, ValueError):
        raise ConnectorError("Odoo response id was not an integer", retryable=False, status_code=200) from None


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _copy_ref(ref: ExternalRef) -> ExternalRef:
    return ref.model_copy(deep=True)
