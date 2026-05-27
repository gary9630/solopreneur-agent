# Solopreneur Agent Project Instructions

This repo is the NVIDIA NemoClaw hackathon MVP for a solopreneur deal-to-delivery agent. Prioritize a demonstrable, reliable live workflow over broad feature work.

## Safety Rules

- Do not batch-delete files or directories.
- Do not use `del /s`, `rd /s`, `rmdir /s`, `Remove-Item -Recurse`, or `rm -rf`.
- If deletion is required, delete only one explicit file path at a time.
- If a task appears to require batch deletion, stop and ask the user to delete the files manually.
- Never commit secrets. `.env` is local-only; keep API keys, bot tokens, Odoo credentials, GitHub tokens, and Linear tokens out of git.
- Live side effects must remain gated. A request is live only when the host has `LIVE_WORKFLOW_ENABLED=1` and the request explicitly sets `live=true`.
- Never finalize invoices or mark deals won unless the operator gives explicit acceptance.
- High-impact external writes must have an audit trail naming every external system touched.

## Project Shape

- `agent_app/`: FastAPI tool gateway, workflow runner, model services, fake/live connectors, Telegram ops bot, tests, and demo CLI.
- `odoo_addons/`: Odoo 19 custom addon mounted into `/mnt/extra-addons`.
- `openclaw_plugins/solopreneur-tools/`: OpenClaw plugin code that exposes first-class tools to OpenClaw.
- `skills/`: OpenClaw/NemoClaw skill instructions. Skills are workflow guidance, not tool registration.
- `presets/`: NemoClaw network policy presets.
- `workspace/`: OpenClaw workspace context files synced into `/sandbox/.openclaw/workspace`.
- `reference-works/`: Local reference source for Odoo and NemoClaw/OpenClaw behavior.
- `Install.md`: Full local install, rebuild, and demo setup guide.

## Development Principles

- Optimize for the hackathon live demo: reliable Odoo CRM/Sales artifacts, Linear/GitHub delivery tracking, Telegram notifications, and business-card/CRM lookup flows.
- Prefer atomic tools for flexible agent behavior:
  - `deal_prepare`
  - `crm_lookup`
  - `business_card_capture`
  - `odoo_upsert_contact`
  - `odoo_create_crm_lead`
  - `odoo_create_sale_order`
  - `odoo_create_draft_invoice`
  - `delivery_create_tasks`
  - `notify_stakeholder`
- Treat any composite end-to-end route as compatibility or demo support. For intelligent assistant behavior, teach OpenClaw when to call atomic tools through `skills/deal-to-delivery/SKILL.md` and `workspace/TOOLS.md`.
- Keep fake-only deterministic paths working by default. Live integrations should be opt-in and testable without real credentials.
- Use the repo's existing connector/service patterns before adding abstractions.

## NemoClaw / OpenClaw Rules

- Before adding new tools/plugins or changing anything related to NemoClaw, verify the supported approach in official docs first.
- Prefer local docs under `reference-works/NemoClaw/docs`; if they do not answer the question, check `https://docs.nvidia.com/nemoclaw/latest/home`.
- OpenClaw plugins are runtime code packages. Bake `openclaw_plugins/solopreneur-tools` into the custom sandbox image with `nemoclaw onboard --from`; do not expect `SKILL.md` to register tools.
- The solopreneur OpenClaw plugin imports `openclaw/plugin-sdk/tool-plugin`; make that SDK resolvable from the extension by providing `node_modules/openclaw -> /usr/local/lib/node_modules/openclaw`, matching the NemoClaw reference pattern for extension-local OpenClaw SDK access.
- Keep `tools.toolSearch` enabled unless there is a model-specific compatibility reason to disable it. If plugin tools do not appear in the OpenClaw agent Tools UI, first verify the plugin has a formal install record from `openclaw plugins install` and is enabled; do not treat `toolSearch=true` as the root cause.
- Do not run in-sandbox OpenClaw model/config mutation commands from scripts, such as `openclaw models set`, `openclaw models auth`, or `openclaw config set`, because they can rewrite `/sandbox/.openclaw/openclaw.json` and break NemoClaw-managed gateway config.
- Per official NemoClaw plugin docs, the custom Dockerfile may run `openclaw doctor --fix --non-interactive` after copying the plugin so OpenClaw refreshes its config before NemoClaw starts the sandbox. Validate plugins after onboarding, not during image build.
- If the sandbox reports `gateway.mode` missing, treat the sandbox state as clobbered. Recreate it with:

```bash
make nemoclaw-dashboard-stop
make nemoclaw-solopreneur-sandbox-recreate
```

If gateway state is also broken, use the heavier cleanup path documented in `Install.md`.

## Odoo Rules

- The demo targets Odoo 19. Use Odoo 19 view/model syntax.
- When an Odoo field or behavior is uncertain, verify against `reference-works/odoo/odoo/` before changing addon data or connector calls.
- The addon is `deal_to_delivery_agent`; it should expose `Deal Agent`, `Deal Contexts`, and `Audit Logs`.
- Live Odoo deal creation should create or update contact/customer data, create CRM lead/opportunity records, create sale order/quotation draft artifacts, and create draft invoices only. Do not final-post invoices.

## Local Commands

- Install Python dependencies: `cd agent_app && uv sync`
- Run tests: `cd agent_app && uv run pytest -q`
- Run root test target: `make test`
- Start Odoo: `make odoo-up`
- Create or refresh NemoClaw sandbox: `make nemoclaw-solopreneur-sandbox`
- Force fresh recreate of the sandbox: `make nemoclaw-solopreneur-sandbox-recreate`
- Start dashboard forward: `make nemoclaw-dashboard`
- Stop dashboard forward: `make nemoclaw-dashboard-stop`
- Start tool gateway: `make tool-gateway`
- Start Telegram ops bot: `make telegram-ops`

## Verification Expectations

- For code changes under `agent_app/`, run `cd agent_app && uv run pytest -q` unless the change is explicitly docs-only.
- For docs/script/Makefile changes, at minimum run `git diff --check`.
- For NemoClaw/OpenClaw integration changes, run the focused asset tests:

```bash
cd agent_app && uv run pytest tests/test_nemoclaw_assets.py -q
```

- Do not claim a sandbox, dashboard, or live workflow is fixed without checking the actual command output.
