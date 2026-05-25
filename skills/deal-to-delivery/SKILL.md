---
name: deal-to-delivery
description: Operate the NVIDIA hackathon MVP agent that turns accepted SME deal requests into audited Odoo, Linear, GitHub, and Telegram handoffs.
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
- use Linear for engineering execution; keep GitHub focused on delivery traceability and code/PR coordination.

## Operating Flow

1. Read `workspace/IDENTITY.md`, `workspace/USER.md`, and `workspace/MEMORY.md` before acting.
2. Convert the customer message into a `DealBrief` with assumptions called out plainly.
3. Run policy checks against the hard rules before any external side effect.
4. Use the local tool gateway to create Odoo lead, quote, and draft invoice records.
5. Create Linear issues for implementation and operations tasks.
6. Create a GitHub delivery issue that links the Odoo and Linear references.
7. Send a Telegram update only after the records above exist.
8. Write an audit summary that names every external system touched.

For the detailed checklist, follow `sop.md` in this skill directory.
