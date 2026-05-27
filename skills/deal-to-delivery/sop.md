# Deal-to-Delivery SOP

This SOP keeps the hackathon demo repeatable and safe inside a NemoClaw sandbox.

## Inputs

- Customer request text.
- Operator confirmation for deal acceptance or invoice finalization.
- Environment variables and secrets supplied outside the repository.

## Steps

1. Parse the request into customer, contact, scope, urgency, budget, and delivery expectations.
2. Summarize uncertainty instead of inventing missing commercial terms.
3. Check safety boundaries:
   - Do not finalize invoices.
   - Do not mark a deal won without explicit acceptance.
   - Do not skip audit logs for external side effects.
4. Use the tool gateway for Odoo lead, quote, and draft invoice creation:
   - dry-run or planning: `POST http://host.openshell.internal:8088/tools/deal-to-delivery/run` with `live=false`.
   - live demo: same route with `live=true`, only after the operator confirms `LIVE_WORKFLOW_ENABLED=1` is set on the host.
5. Use Linear for engineering execution tasks, each with owner intent and acceptance criteria.
6. Use GitHub for a delivery tracking issue that links back to Linear and Odoo.
7. Use Telegram for a concise stakeholder update after all references are available.
8. Return a compact run summary with final state, created references, and follow-up questions.

## OpenClaw Tool Boundary

Skills are instructions, not tool registration. The dashboard agent needs the first-class OpenClaw `solopreneur-tools` plugin to run this workflow from chat.

Do not guess missing shell tools. If `crm_lookup`, `business_card_capture`, `deal_prepare`, `odoo_create_deal_artifacts`, `delivery_create_tasks`, and `notify_stakeholder` are not visible, stop and tell the operator that the OpenClaw project tool/plugin is not installed for this sandbox.

Use these routing examples:

- customer asks for a CRM contact, email, or phone number: call `crm_lookup`.
- user provides a business-card photo: call `business_card_capture` with the image payload.
- user describes a new deal or sales opportunity: call `deal_prepare` first.
- operator approves draft Odoo records: call `odoo_create_deal_artifacts` with `"live": true`.
- operator asks to set up delivery execution: call `delivery_create_tasks` after Odoo refs exist.
- operator asks to update a customer or stakeholder: call `notify_stakeholder` after relevant refs exist.

For a live run, the relevant tool schema is used with `"live": true`. Normal operator prompts should not name tool APIs; they should describe the business request and whether the run is dry-run or live.

The tools call host gateway endpoints internally and return gateway JSON. Afterward, summarize `mode`, `live_enabled`, final workflow state, and every external reference.

The Telegram ops bot is the preferred mobile demo surface for business-card capture, CRM lookup, and quick stakeholder updates. Operator fallback commands such as host-side curl are acceptable for troubleshooting, but they should not appear in the judge-facing chat prompt.

## Failure Handling

- If a side effect fails before a reference is returned, mark the step retryable.
- If a side effect succeeds but the confirmation response is unclear, ask the operator to inspect the external system before retrying.
- If a safety rule blocks the run, stop before the side effect and explain the exact missing approval.
