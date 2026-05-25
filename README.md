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

Start Postgres and Odoo:

```bash
docker compose up -d db odoo
```

The compose file mounts the local addon directory:

```text
./odoo_addons:/mnt/extra-addons
```

After Odoo starts, install the `deal_to_delivery_agent` addon to inspect deal contexts, audit logs, and demo products.

## NemoClaw Demo Assets

Apply the local policies and install the deal-to-delivery skill:

```bash
bash scripts/apply_nemoclaw_policies.sh
bash scripts/install_nemoclaw_skills.sh
```

The scripts use `SANDBOX=deal-demo` by default. Copy `.env.example` to `.env` only for local live integration trials, and keep real API keys out of git.

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
