# NVIDIA NemoClaw Agent MVP Design

## Goal

Build a hackathon-ready Deal-to-Delivery Agent for service-based SMEs and solo operators. The MVP must show a real, persistent workflow that turns a customer request into business and delivery artifacts across Odoo, Linear, GitHub, Telegram, and NVIDIA Nemotron through NemoClaw.

The demo target is:

```text
Customer brief -> intake summary -> Odoo lead/opportunity -> quote/SOW draft
-> Linear project/issues -> GitHub delivery trail -> Odoo invoice draft
-> Telegram status notification
```

## Product Scope

The MVP is optimized for a reliable live demo, not a full product launch. It should prove:

- The agent can autonomously advance a multi-step business workflow.
- Nemotron is the core reasoning model.
- NemoClaw provides sandboxing, inference routing, and policy-based guardrails.
- Odoo is the business source of truth.
- Linear is the engineering execution source of truth.
- GitHub captures delivery and repository-facing work.
- Telegram is the human-facing intake and notification channel.
- The workflow can be tested, replayed, and recovered after partial failure.

Out of scope for the hackathon MVP:

- Multi-tenant SaaS.
- Real payment collection.
- Production accounting compliance or Taiwan e-invoice integration.
- Full Odoo core customization.
- Full Linear Agent API usage. Use mature GraphQL APIs first.
- Direct vendoring or modifying Odoo/NemoClaw source code.

## Recommended Approach

Use a deterministic workflow core with agent reasoning at decision points.

`agent_app` owns state transitions, retries, idempotency, connector calls, audit logging, and testability. NemoClaw/OpenClaw owns the sandboxed agent experience, skill instructions, policy controls, and Nemotron-backed reasoning. This keeps the demo stable while still showing a real autonomous agent.

Rejected alternatives:

- Agent-first orchestration: impressive but too fragile for a short hackathon window.
- Scripted thin-AI demo: fastest but weak against the judging requirement for persistent working code.

## Repository Structure

```text
.
├── agent_app/
│   ├── pyproject.toml
│   ├── src/deal_agent/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── workflow.py
│   │   ├── models.py
│   │   ├── nim_client.py
│   │   ├── connectors/
│   │   │   ├── github.py
│   │   │   ├── linear.py
│   │   │   ├── odoo.py
│   │   │   └── telegram.py
│   │   └── services/
│   │       ├── intake.py
│   │       ├── quoting.py
│   │       ├── delivery.py
│   │       └── notifications.py
│   └── tests/
├── demo/
│   ├── customer_inputs/
│   └── expected_outputs/
├── docs/
│   ├── architecture.md
│   ├── demo-script.md
│   └── plans/
├── odoo_addons/
│   └── deal_to_delivery_agent/
├── presets/
├── skills/
│   └── deal-to-delivery/
├── workspace/
├── docker-compose.yml
├── Makefile
├── .env.example
└── THIRD_PARTY_NOTICES.md
```

`reference-works/` remains reference-only and should not become part of the product surface.

## Architecture

```text
Telegram/demo input
        |
        v
agent_app FastAPI / worker
        |
        +-- NVIDIA NIM Nemotron client
        +-- Odoo connector
        +-- Linear connector
        +-- GitHub connector
        +-- Telegram connector
        +-- workflow state store
        |
        v
NemoClaw/OpenClaw skill + policy guardrails
```

The agent system has three planes:

- Reasoning plane: Nemotron via NVIDIA NIM, reached through NemoClaw managed inference for the sandbox path and through a typed client for app-side tests/smoke flows.
- Execution plane: `agent_app` tool gateway performs external side effects.
- State plane: workflow run records plus external source-of-truth systems: Odoo, Linear, GitHub, Telegram.

For the MVP, SQLite can be used locally for workflow state if speed matters, but the interfaces should allow Postgres in Docker Compose. Odoo already brings Postgres for business data.

## Workflow States

Use explicit state transitions instead of a loose chain of function calls.

```text
NEW
INTAKE_SUMMARIZED
ODOO_LEAD_CREATED
QUOTE_DRAFTED
ODOO_QUOTATION_CREATED
LINEAR_BOOTSTRAPPED
GITHUB_DELIVERY_TRACKED
INVOICE_DRAFT_CREATED
TELEGRAM_NOTIFIED
COMPLETED
FAILED_RETRYABLE
FAILED_TERMINAL
```

Each step stores:

- `run_id`
- `step_name`
- `state_before`
- `state_after`
- `attempt`
- `idempotency_key`
- `external_ref`
- `input_hash`
- `result_summary`
- `error_type`
- `error_message`

## Connector Boundaries

### Odoo

Run Odoo as a Docker service and mount only the custom addon into `/mnt/extra-addons`.

The custom addon should provide:

- `agent.audit.log` for important agent actions.
- `deal.context` for structured scope, risks, milestones, and links.
- Demo service products, quote templates, and pipeline stages.

The app connector creates or updates:

- partner/contact
- CRM lead/opportunity
- quotation draft
- invoice draft
- audit log records

### Linear

Use GraphQL for the MVP. Required actions:

- create or find a project
- create issues from the approved scope
- write links back to workflow artifacts

Handle GraphQL `errors` even when HTTP status is 200.

### GitHub

Use API integration from `agent_app`. MVP actions:

- create a delivery tracking issue or checklist
- optionally create branch/PR metadata links
- write GitHub URLs back to Linear and workflow artifacts

No direct pushes to `main`.

### Telegram

Use Bot API integration from `agent_app` for the MVP, with NemoClaw Telegram policy available for the sandbox/channel demo.

MVP actions:

- accept demo intake payloads
- send status updates
- send quote/invoice draft notification summaries

### NVIDIA NIM / Nemotron

Use `nvidia/nemotron-3-super-120b-a12b` as the primary planning and drafting model. Keep API keys out of committed files. `.env.example` should document required variables but contain no secrets.

Model-backed operations:

- intake extraction into a structured schema
- quote/SOW draft generation
- issue breakdown
- notification wording

## NemoClaw Integration

NemoClaw is an external CLI/runtime dependency installed by setup script. The repo owns only the integration artifacts:

- `scripts/setup_nemoclaw.sh`
- `presets/`
- `skills/deal-to-delivery/SKILL.md`
- `workspace/AGENTS.md`
- `workspace/SOUL.md`
- `workspace/IDENTITY.md`
- `workspace/USER.md`
- `workspace/MEMORY.md`

Policy presets should follow least privilege:

- Allow managed inference through `inference.local`.
- Allow Telegram only when Telegram is part of the demo.
- Allow GitHub only when delivery tracking is enabled.
- Allow Linear API.
- Allow local tool gateway.
- Avoid broad internet access.

The demo should include one policy-block moment if time permits: attempt a disallowed host and show NemoClaw blocking it.

## Error Handling

Every side-effecting step must be idempotent. Re-running a workflow should reuse prior external records when the idempotency key matches.

Failure classes:

- Retryable connector error: timeout, 429, temporary 5xx.
- Terminal validation error: missing required customer fields after extraction.
- Policy block: sandbox attempted a disallowed route.
- Human-required checkpoint: quote approval or invoice finalization.

The MVP must never post a final invoice automatically. It creates invoice drafts only.

## Testing Strategy

Testing must be part of development, not a final pass.

Required tests:

- Unit tests for workflow state transitions.
- Unit tests for idempotency keys.
- Unit tests for NIM structured output parsing.
- Connector tests using mocked HTTP for Odoo, Linear, GitHub, and Telegram.
- E2E happy path with fake connectors.
- Failure test for duplicate intake payload.
- Failure test for retryable connector error.

Optional live smoke tests:

- NVIDIA NIM smoke test gated by `NVIDIA_API_KEY`.
- Telegram sendMessage smoke test gated by `TELEGRAM_BOT_TOKEN`.
- Linear issue creation smoke test gated by `LINEAR_API_KEY` or OAuth token.
- Odoo local smoke test gated by `ODOO_URL` and credentials.

Live tests must be opt-in and must not run in default CI without credentials.

## Demo Script

The shortest winning demo should show:

1. Submit a realistic customer brief from `demo/customer_inputs/`.
2. Show structured intake summary.
3. Show Odoo lead/opportunity and quote draft.
4. Show Linear project/issues.
5. Show GitHub delivery tracking artifact.
6. Show Odoo invoice draft.
7. Show Telegram notification.
8. Show workflow event log.
9. Show NemoClaw policy/skill artifacts.

## Security Notes

- Do not commit API keys.
- Keep `.env.example` secret-free.
- Treat `NIM-API-usage.md` as local-only if it contains a real key.
- Route side effects through `agent_app` so the sandbox does not need long-lived SaaS credentials.
- Document third-party dependencies and licenses.
- Do not vendor Odoo or NemoClaw source code into the product deliverable.

## Success Criteria

The MVP is done when:

- `make test` or an equivalent command runs unit and mocked integration tests.
- A fake-connector e2e test completes the full deal-to-delivery path.
- The repo contains NemoClaw presets, skill, and workspace files.
- Odoo addon skeleton installs or at least validates structurally.
- The demo can be replayed from seeded input without manual copy/paste between systems.
- README explains setup, demo, guardrails, and known limitations.
