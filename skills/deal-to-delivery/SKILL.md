---
name: deal-to-delivery
description: Operate the NVIDIA hackathon MVP agent that turns SME requests into audited Odoo, Linear, GitHub, and Telegram handoffs. In compact catalogs, use tool_search_code with openclaw.tools.search("tool") and openclaw.tools.call("tool", args).
---

# Deal-to-Delivery Skill

Use this skill inside a NemoClaw/OpenClaw sandbox when the user asks the hackathon MVP agent to process a customer request, prepare fulfillment work, or coordinate the demo workflow.

## Mission

Turn a customer request into a safe delivery package:

- Understand the deal and produce a concise brief.
- Draft Odoo CRM, quote, and draft invoice records through the local tool gateway.
- Break the work into Linear engineering issues.
- Create a GitHub delivery tracking issue.
- Send a Telegram stakeholder update.
- Record every high-impact action in the local audit trail.

## Hard Rules

- never finalize invoices; only create draft invoices or request human review.
- never mark a deal won without explicit acceptance from the customer or operator.
- always log high-impact actions before and after tool calls that create or change external records.
- prefer tool gateway for side effects; do not call Odoo, Linear, GitHub, or Telegram directly when the gateway is available.
- for live workflow side effects, require both `LIVE_WORKFLOW_ENABLED=1` on the host and the selected tool argument `live=true`.
- use Linear for engineering execution; keep GitHub focused on delivery traceability and code/PR coordination.
- skills are instructions, not tool registration. This skill does not create a shell, HTTP, or project tool in OpenClaw.
- use the first-class OpenClaw tools from the `solopreneur-tools` plugin when they are available. If they are not available, stop and say the project OpenClaw tool/plugin is missing.
- do not guess missing shell tools such as `bash`, `exec`, `read`, or `fetch`.
- in NemoClaw compact tool-catalog mode, the visible tool may be only `tool_search_code`; use it with JavaScript code that calls `openclaw.tools.search("crm_lookup")`, `openclaw.tools.describe("crm_lookup")`, or `openclaw.tools.call("crm_lookup", { query: "...", live: false })`. Do not pass `require(...)` code, and do not call `openclaw.tools.search({ query: "..." })`.
- normal operator prompts should not name tool APIs, URLs, curl commands, or JSON payloads.

## Operating Flow

1. Use the injected workspace context if present. Do not call `read` to inspect workspace files.
2. Convert the customer message into a `DealBrief` with assumptions called out plainly.
3. Run policy checks against the hard rules before any external side effect.
4. Choose the smallest atomic tool sequence that satisfies the request.
5. Create Linear issues for implementation and operations tasks only when the operator asks to move from preparation to delivery execution.
6. Create a GitHub delivery issue only after Odoo deal artifacts or Linear delivery tasks exist.
7. Send a Telegram update only after relevant records above exist.
8. Write an audit summary that names every external system touched.

## OpenClaw Tool Boundary

The intended OpenClaw dashboard integration is a first-class OpenClaw tool/plugin, not a prompt that asks the model to find a shell. The `solopreneur-tools` plugin exposes these atomic tools:

- `crm_lookup`: search Odoo contacts and CRM leads.
- `business_card_capture`: extract a business-card image and write the contact/lead when live mode is approved.
- `deal_prepare`: turn a customer message into a deal brief, assumptions, quote draft, and delivery plan with no external side effects.
- `odoo_upsert_contact`: create or update the Odoo `res.partner` contact/customer after approval.
- `odoo_create_crm_lead`: create an Odoo CRM lead for the contact after approval.
- `odoo_create_sale_order`: create an Odoo `sale.order` quotation after approval.
- `odoo_create_draft_invoice`: create a draft Odoo invoice after approval. Never finalize invoices.
- `odoo_create_deal_artifacts`: convenience fallback that creates contact, CRM lead, sale order quotation, draft invoice, deal context, and audit records after approval.
- `delivery_create_tasks`: create Linear delivery tasks and GitHub delivery tracking after approval.
- `notify_stakeholder`: send a Telegram update after relevant external refs exist.

Each tool calls a host gateway endpoint behind the scenes. The user-facing chat should stay natural; the operator should not paste URLs or JSON payloads.

NemoClaw may compact the full tool catalog behind `tool_search_code`. When that happens, search and call the project tools like this:

```js
const matches = await openclaw.tools.search("crm_lookup");
return matches;
```

```js
return await openclaw.tools.call("crm_lookup", { query: "Ada Lovelace", live: false });
```

The first argument to `openclaw.tools.search` and `openclaw.tools.describe` is a string. The first argument to `openclaw.tools.call` is the exact tool name, and the second argument is the tool arguments object.

Common tool arguments are `"run_id"` and `"message"`. Use `"live": false` only for dry-run preparation.
For full live mode, every tool call in the sequence, including `deal_prepare`, must include exactly `"live": true`; the host must also set `LIVE_WORKFLOW_ENABLED=1`.

After the tool response, summarize `mode`, `live_enabled`, final workflow state, and every external reference returned. If the gateway returns `missing_config`, stop and tell the operator which environment variables are missing.

## Demo Prompts

Good operator prompts describe business intent only:

```text
Acme Studio wants a two-week Odoo CRM automation package starting next Monday.
Scope: lead capture, quote generation, delivery task tracking, and stakeholder update when delivery is ready.
Budget is USD 8000. Contact is Ada Lovelace, ada@example.com.
Prepare the deal-to-delivery workflow as a dry run.
```

Use `deal_prepare` only.

```text
Looks good. Create the Odoo deal records as draft artifacts, but do not mark won or finalize the invoice.
```

Preferred live sequence after confirming approval:

1. Use `odoo_upsert_contact` with customer/contact/email from `deal_prepare`.
2. Use `odoo_create_crm_lead` with the returned contact `external_id` as `partner_id`.
3. Use `odoo_create_sale_order` with the returned contact `external_id` and prepared `quote_draft`.
4. Use `odoo_create_draft_invoice` with the returned contact `external_id` and prepared `quote_draft`.

Use `odoo_create_deal_artifacts` only as a convenience fallback when the operator needs one-shot Odoo draft artifacts.

```text
Create the delivery work items and tracking issue for the approved Acme package.
```

Use `delivery_create_tasks` after Odoo refs exist.

```text
Tell the stakeholder the Acme delivery package is ready for review.
```

Use `notify_stakeholder` only after relevant external refs exist.

```text
Find Acme's contact info in CRM.
```

Use `crm_lookup`.

```text
I just uploaded a business card. Extract it and create the CRM contact.
```

Use `business_card_capture` when image data is available from the channel.

For the mobile solopreneur demo, the Telegram ops bot is the better live surface for photo intake, CRM lookup, and quick customer updates. The Telegram bot and the OpenClaw tool should both call the same host gateway so audit logs and safety gates stay consistent.

## Fallbacks

Operator fallback paths are for diagnostics, not normal chat prompts: use host-side `curl`, `make tool-gateway`, `make telegram-ops`, or `nemoclaw deal-demo exec -- curl ...` outside the dashboard to verify connectivity and policy. Do not expose these mechanics to the judge-facing prompt.

For the detailed checklist, follow `sop.md` in this skill directory.
