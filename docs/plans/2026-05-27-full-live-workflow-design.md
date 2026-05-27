# Full-Live Workflow Demo Design

## Goal

Build a championship-grade live demo that shows a solopreneur assistant performing real daily business work through guarded tools:

- OpenClaw triggers the deal-to-delivery workflow through NemoClaw-approved `/tools/**` gateway routes.
- The workflow creates real Odoo CRM/Sales/Invoice artifacts, Linear project/issues, GitHub delivery tracking, and Telegram updates.
- A separate Agent App Telegram bot handles practical solopreneur tasks: business-card photo intake into Odoo CRM and CRM contact lookup while away from the laptop.

## Demo Story

The demo should feel like a working operator assistant, not a scripted chatbot.

1. The operator uses OpenClaw to process a customer request into a full deal-to-delivery run.
2. The operator shows Odoo CRM lead, quotation, invoice draft, Linear work, GitHub issue, and Telegram notification.
3. The operator sends a business-card photo to the Agent App Telegram bot. The bot extracts contact details and creates or updates Odoo contact plus CRM lead.
4. The operator asks Telegram, "Find Acme contact info." The bot queries Odoo and responds with contact details and CRM context.
5. The operator shows NemoClaw blocking a disallowed egress request.

## Bot Separation

Use two Telegram bots.

- `TELEGRAM_BOT_TOKEN`: OpenClaw / NemoClaw channel, pairing, sandbox chat.
- `AGENT_TELEGRAM_BOT_TOKEN`: Agent App business workflow bot for CRM capture, lookup, and notifications.

The private chat id may be the same for both bots because it is the operator's Telegram user id. Access for the Agent App bot is controlled by `AGENT_TELEGRAM_ALLOWED_USER_IDS`.

## Architecture

### Reasoning Plane

OpenClaw inside NemoClaw owns operator-facing reasoning and invokes the local tool gateway. The skill must explicitly prefer `http://host.openshell.internal:8088/tools/**` for side effects.

NVIDIA NIM is used in two places:

- Existing text workflow services for intake, quote, issue breakdown, and notifications.
- Business-card extraction from Telegram photos, using a configurable multimodal model.

### Execution Plane

`agent_app` is the Tool Gateway. It owns credentials and all side effects.

Routes:

- `GET /health`
- `POST /tools/deal-to-delivery/run`
- `POST /tools/crm/business-card`
- `POST /tools/crm/lookup`

Telegram polling runs in `agent_app` and dispatches updates to the same CRM services used by the `/tools/**` routes.

### State Plane

The first live implementation uses external systems as source of truth plus the in-memory response body for demo traceability.

- Odoo: contacts, CRM leads, quotations, draft invoices, deal context, audit logs.
- Linear: project and implementation issues.
- GitHub: delivery tracking issue.
- Telegram: operator/customer-facing updates.

A later product version should persist workflow runs in Postgres. That is not required for this live demo because Odoo custom records and external refs provide visible traceability.

## Safety Model

Live side effects require double opt-in:

- Host env: `LIVE_WORKFLOW_ENABLED=1`
- Request body: `live=true`

If either is missing, `/tools/deal-to-delivery/run` must return a non-side-effect dry-run response.

The Agent App Telegram bot has a separate allowlist:

- `AGENT_TELEGRAM_ALLOWED_USER_IDS=<your_telegram_user_id>`

Unauthorized Telegram users receive a refusal and no side effects.

Invoices are always draft invoices. The workflow must never post/finalize an invoice or mark a deal won.

## Odoo Scope

Use Odoo's existing business modules visibly:

- CRM: `crm.lead`
- Contacts: `res.partner`
- Sales: `sale.order`
- Invoicing: `account.move` draft invoice
- Custom addon: `deal.context` and `agent.audit.log`

The business-card flow creates or updates `res.partner` and creates a CRM lead tagged as Telegram business-card intake.

The CRM lookup flow searches Odoo contacts/leads and returns compact contact information.

## Telegram Ops Bot

Polling is preferred for the local hackathon demo because it avoids public HTTPS webhook setup.

Commands:

- `/start`: confirms bot is available and names capabilities.
- text lookup: "查 Acme 聯絡方式" or "find Acme contact"
- photo: download highest-resolution Telegram photo, extract business-card fields, create/update Odoo contact and CRM lead.

The bot should respond with concise, demo-friendly messages and Odoo ids/links where available.

## Configuration

New env vars:

- `LIVE_WORKFLOW_ENABLED`
- `AGENT_TELEGRAM_BOT_TOKEN`
- `AGENT_TELEGRAM_CHAT_ID`
- `AGENT_TELEGRAM_ALLOWED_USER_IDS`
- `NIM_VISION_MODEL`

Existing env vars remain:

- `NVIDIA_API_KEY`
- `NIM_BASE_URL`
- `NIM_MODEL`
- `ODOO_URL`
- `ODOO_DATABASE`
- `ODOO_API_KEY`
- `LINEAR_API_KEY`
- `LINEAR_TEAM_ID`
- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY`

## Testing

Use TDD and keep live calls gated.

Unit tests:

- `/tools/deal-to-delivery/run` returns dry-run unless double opt-in is present.
- live runner factory refuses missing credentials with clear non-secret errors.
- CRM business-card extraction validates structured fields.
- Telegram update router rejects unauthorized user ids.
- CRM lookup formats empty and successful Odoo results.

Connector tests:

- Odoo contact upsert and CRM lookup with mocked JSON-2 responses.
- Telegram getUpdates, getFile/download, and sendMessage with mocked HTTP.
- NIM multimodal client sends image content and parses JSON.

Live smoke tests:

- Keep existing `pytest -m live`.
- Add opt-in-only Telegram agent bot smoke.
- Add optional Odoo contact lookup smoke.

## Demo Acceptance Criteria

The live demo is ready when:

- OpenClaw can call `/tools/deal-to-delivery/run` through the NemoClaw policy-allowed gateway.
- With `LIVE_WORKFLOW_ENABLED=1` and `live=true`, the run creates real Odoo, Linear, GitHub, and Telegram refs.
- Odoo UI shows CRM/Sales/Invoice/custom audit artifacts from the run.
- Sending a business-card photo to the Agent App bot creates or updates Odoo CRM data.
- Asking the Agent App bot for a CRM contact returns useful data from Odoo.
- A disallowed sandbox network request still returns a policy denial.
