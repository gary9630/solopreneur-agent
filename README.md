# Solopreneur Agent

Deal-to-delivery agentic workflow for the NVIDIA NemoClaw hackathon MVP.

The MVP demonstrates a guarded agent that can turn a customer request into a validated deal brief, quote draft, delivery issue plan, Odoo-facing records, Linear work items, GitHub delivery tracking, and Telegram stakeholder updates. The default demo path is deterministic and fake-only, so it can be shown without live credentials.

Odoo and NemoClaw source code is not vendored. This repository includes integration assets only: an Odoo custom addon, NemoClaw policy presets, a NemoClaw skill, workspace files, connector code, and demo fixtures.

## Quickstart

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

After Odoo 19 starts, install the `deal_to_delivery_agent` addon to inspect deal contexts, audit logs, and demo products.

## NemoClaw Demo Assets

Create or refresh the solopreneur sandbox with the official NemoClaw image, then install the local OpenClaw plugin into the sandbox state:

```bash
make nemoclaw-solopreneur-sandbox
```

The default path intentionally does not build from `Dockerfile.nemoclaw-solopreneur`. The official NemoClaw sandbox image carries startup preloads and OpenClaw patches needed for proxied NVIDIA inference. The custom Dockerfile is kept as an experimental path for later image baking and can be selected with `USE_CUSTOM_IMAGE=1`.

Apply the local policies and install the deal-to-delivery skill:

```bash
bash scripts/apply_nemoclaw_policies.sh
bash scripts/install_nemoclaw_skills.sh
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

## Full-Live Tool Gateway

Start the local execution gateway on port `8088`:

```bash
make tool-gateway
```

OpenClaw should call the policy-approved route:

```text
POST http://host.openshell.internal:8088/tools/deal-to-delivery/run
```

Live side effects require both host opt-in and request opt-in:

```bash
LIVE_WORKFLOW_ENABLED=1
```

and request body `live=true`. Without both, `/tools/deal-to-delivery/run` stays in dry-run mode.

Start the second Telegram bot for business-card intake and CRM lookup:

```bash
make telegram-ops
```

Configure it with `AGENT_TELEGRAM_BOT_TOKEN`, `AGENT_TELEGRAM_CHAT_ID`, and `AGENT_TELEGRAM_ALLOWED_USER_IDS`.

## Project Layout

- `agent_app/`: FastAPI app, workflow runner, model services, live/fake connectors, tests, and demo CLI.
- `demo/`: replayable customer input and expected output summary.
- `odoo_addons/`: custom Odoo bridge addon mounted into `/mnt/extra-addons`.
- `presets/`: NemoClaw network policy presets.
- `skills/`: OpenClaw/NemoClaw skill instructions for the deal-to-delivery workflow.
- `workspace/`: local agent context files for sandboxed execution.
- `docs/demo-script.md`: hackathon demo flow and talking points.
- `THIRD_PARTY_NOTICES.md`: external dependency and API notices.

## Live Integrations

Live connector configuration is intentionally placeholder-only in `.env.example`:

- NVIDIA NIM Serverless Inference
- Odoo
- Linear API
- GitHub API
- Telegram Bot API
- NemoClaw `SANDBOX`

The automated tests do not make live network calls.
