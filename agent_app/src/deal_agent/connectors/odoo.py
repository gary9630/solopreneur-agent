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

    def __repr__(self) -> str:
        return f"OdooHttpConnector(base_url={self.base_url!r}, database={self.database!r})"

    def create_lead(self, run_id: str, brief: DealBrief, summary: IntakeSummary) -> ExternalRef:
        payload = {
            "name": f"{summary.customer_name or brief.customer_name or 'Deal'} - {run_id}",
            "contact_name": summary.contact_name or brief.contact_name,
            "email_from": summary.contact_email or brief.contact_email,
            "description": summary.problem_statement,
            "x_agent_run_id": run_id,
            "x_agent_input_hash": brief.input_hash,
        }
        return self._create(
            "crm.lead",
            "create",
            _drop_none(payload),
            kind="lead",
            run_id=run_id,
        )

    def create_quotation(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        payload = {
            "client_order_ref": run_id,
            "note": quote.notes,
            "currency": quote.currency,
            "amount_untaxed": _decimal_string(quote.subtotal),
            "amount_tax": _decimal_string(quote.tax),
            "amount_total": _decimal_string(quote.total),
            "order_line": [_line_item_payload(item) for item in quote.line_items],
        }
        return self._create(
            "sale.order",
            "create",
            _drop_none(payload),
            kind="quotation",
            run_id=run_id,
        )

    def create_invoice_draft(self, run_id: str, quote: QuoteDraft) -> ExternalRef:
        payload = {
            "move_type": "out_invoice",
            "ref": run_id,
            "currency": quote.currency,
            "state": "draft",
            "invoice_line_ids": [_line_item_payload(item) for item in quote.line_items],
        }
        return self._create(
            "account.move",
            "create",
            _drop_none(payload),
            kind="invoice_draft",
            run_id=run_id,
        )

    def _create(
        self,
        model: str,
        method: str,
        payload: dict[str, Any],
        *,
        kind: str,
        run_id: str,
    ) -> ExternalRef:
        result = request_json(
            self._http_client,
            "Odoo",
            f"{self.base_url}/json/2/{model}/{method}",
            headers=self._headers(),
            json=payload,
        )
        external_id = _extract_odoo_id(result)
        return ExternalRef(
            system="odoo",
            external_id=external_id,
            metadata={"kind": kind, "model": model, "run_id": run_id},
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if self.database:
            headers["X-Odoo-Database"] = self.database
        return headers


def _line_item_payload(item: QuoteLineItem) -> dict[str, str]:
    payload = {
        "name": item.description,
        "quantity": _decimal_string(item.quantity),
        "price_unit": _decimal_string(item.unit_price),
        "external_product_id": item.external_product_id,
    }
    return _drop_none(payload)


def _extract_odoo_id(payload: dict[str, Any]) -> str:
    result = payload.get("result", payload)
    if isinstance(result, dict):
        external_id = result.get("id")
    else:
        external_id = result

    if external_id is None:
        raise ConnectorError("Odoo response did not include an id", retryable=False, status_code=200)
    return str(external_id)


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
