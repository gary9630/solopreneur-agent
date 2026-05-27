# Solopreneur Agent

Deal-to-delivery agentic workflow for the NVIDIA NemoClaw hackathon MVP.

The MVP demonstrates a guarded agent that can turn a customer request into a validated deal brief, Odoo CRM/Sales draft artifacts, Linear work items, GitHub delivery tracking, Telegram stakeholder updates, and Telegram-based CRM/business-card operations. The default demo path is deterministic and fake-only, so it can be shown without live credentials.

Odoo and NemoClaw source code is not vendored. This repository includes integration assets only: an Odoo custom addon, NemoClaw policy presets, a NemoClaw skill, workspace files, connector code, and demo fixtures.

## Quickstart

For the full local setup flow, see [Install.md](Install.md).

The GitHub Pages slide deck for the hackathon pitch is [docs/index.html](docs/index.html). Configure Pages from the repository settings:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

After this branch is merged into `main`, the static deck can be served directly by GitHub Pages without a build step.

Install the Python app dependencies:

```bash
cd agent_app
uv sync
```

Run the test suite:

```bash
uv run pytest
```

Replay the deterministic demo CLI:

```bash
uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt
```

From the repository root, the same commands are available through Make:

```bash
make test
make demo
```

## Odoo Demo

The Odoo 19 demo baseline is intentional: the custom addon uses Odoo 19 view syntax, including list views. Start Postgres and Odoo 19:

```bash
docker compose up -d db odoo
```

The compose file mounts the local addon directory:

```text
./odoo_addons:/mnt/extra-addons
```

After Odoo 19 starts, install the `deal_to_delivery_agent` addon to inspect deal contexts, audit logs, and demo products. The live Odoo path creates or updates:

- `res.partner` contact/customer records
- `crm.lead` opportunities
- `sale.order` quotation drafts
- `account.move` customer invoice drafts
- `deal.agent.deal.context` records
- `deal.agent.audit.log` records

If the addon code or security CSV changes after installation, upgrade the addon:

```bash
docker compose -f docker-compose.yml exec odoo bash -lc 'odoo -d odoo -u deal_to_delivery_agent --stop-after-init --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
```

## NemoClaw Demo Assets

Create or refresh the solopreneur sandbox with the project OpenClaw plugin baked into a custom NemoClaw sandbox image:

```bash
make nemoclaw-solopreneur-sandbox
```

This follows the supported NemoClaw plugin path: OpenClaw plugins are code packages loaded by OpenClaw, so they must be baked into the sandbox image before onboarding. `SKILL.md` files only teach the agent workflow, and policy presets only control sandbox network egress.

`USE_CUSTOM_IMAGE=0 make nemoclaw-solopreneur-sandbox` is kept only as a local debugging fallback. It installs the plugin after the sandbox is already running, which can leave the dashboard tool catalog stale until OpenClaw is repaired and restarted.

Apply the local policies, skill, and workspace files:

```bash
make nemoclaw-policies
make nemoclaw-skills
make nemoclaw-workspace
```

If you used `USE_CUSTOM_IMAGE=0` or need to refresh an already-running sandbox, install and refresh the plugin explicitly:

```bash
make nemoclaw-solopreneur-plugin-install
```

Start the OpenClaw dashboard forward when you want to use the browser UI:

```bash
make nemoclaw-dashboard
```

Keep that terminal open, then fetch the tokenized dashboard URL in another terminal:

```bash
nemoclaw deal-demo dashboard-url
```

The scripts use `SANDBOX=deal-demo` by default. Copy `.env.example` to `.env` only for local live integration trials, and keep real API keys out of git.

## OpenClaw Tools And Full-Live Gateway

Start the local execution gateway on port `8088`:

```bash
make tool-gateway
```

The OpenClaw dashboard should use the first-class `solopreneur-tools` plugin tools, not shell or ad-hoc HTTP calls:

```text
crm_lookup
business_card_capture
deal_prepare
odoo_upsert_contact
odoo_create_crm_lead
odoo_create_sale_order
odoo_create_draft_invoice
odoo_create_deal_artifacts
delivery_create_tasks
notify_stakeholder
```

Live side effects require both host opt-in and request opt-in:

```bash
LIVE_WORKFLOW_ENABLED=1
```

and the selected tool arguments must include `live=true`. Without both, live-capable tools stay in dry-run mode.

For a judge-facing Odoo live demo, prefer the atomic sequence:

1. `deal_prepare`
2. `odoo_upsert_contact`
3. `odoo_create_crm_lead`
4. `odoo_create_sale_order`
5. `odoo_create_draft_invoice`
6. `delivery_create_tasks`
7. `notify_stakeholder`

`odoo_create_deal_artifacts` remains a one-shot compatibility fallback.

Start the second Telegram bot for business-card intake and CRM lookup:

```bash
make telegram-ops
```

Configure it with `AGENT_TELEGRAM_BOT_TOKEN`, `AGENT_TELEGRAM_CHAT_ID`, and `AGENT_TELEGRAM_ALLOWED_USER_IDS`. Business-card capture also needs `NIM_VISION_MODEL`.

## Project Layout

- `agent_app/`: FastAPI app, workflow runner, model services, live/fake connectors, tests, and demo CLI.
- `demo/`: replayable customer input and expected output summary.
- `odoo_addons/`: custom Odoo bridge addon mounted into `/mnt/extra-addons`.
- `presets/`: NemoClaw network policy presets.
- `skills/`: OpenClaw/NemoClaw skill instructions for the deal-to-delivery workflow.
- `openclaw_plugins/`: the OpenClaw `solopreneur-tools` plugin that exposes the first-class dashboard tools.
- `workspace/`: local agent context files for sandboxed execution.
- `docs/index.html`: GitHub Pages-ready HTML slide deck for the hackathon pitch and technical documentation.
- `docs/demo-script.md`: hackathon demo flow and talking points.
- `THIRD_PARTY_NOTICES.md`: external dependency and API notices.

## Live Integrations

Live connector configuration is intentionally placeholder-only in `.env.example`:

- NVIDIA NIM Serverless Inference
- Odoo
- Linear API
- GitHub API
- Telegram Bot API
- NVIDIA vision model for business-card capture
- NemoClaw `SANDBOX`

The automated tests do not make live network calls.
