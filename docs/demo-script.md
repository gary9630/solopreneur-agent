# Hackathon Demo Script

This script shows the hackathon MVP without requiring live credentials in the repository.

## 1. Prove The Workflow Is Tested

Run the project tests:

```bash
cd agent_app && uv run pytest
```

Expected result: the local unit, workflow, connector, Odoo addon structure, NemoClaw asset, and project asset tests pass.

## 2. Replay The Deterministic Agent Demo

Run the fake-only demo CLI:

```bash
cd agent_app && uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt
```

Expected result: compact JSON showing a completed deal-to-delivery run with Odoo, Linear, GitHub, and Telegram systems represented in the external refs.

## 3. Start The Odoo Demo Surface

The Odoo 19 demo baseline matches the addon view syntax used by the bridge module. Start the local Odoo 19 stack:

```bash
docker compose up -d db odoo
```

Open Odoo 19 on `http://localhost:8069`, install the `deal_to_delivery_agent` addon, and show the Deal Agent menus, deal context records, audit logs, and demo products.

## 4. Apply NemoClaw Policies And Skills

Apply the local NemoClaw network policies:

```bash
bash scripts/apply_nemoclaw_policies.sh
```

Install the local deal-to-delivery skill:

```bash
bash scripts/install_nemoclaw_skills.sh
```

Show the guardrails in `skills/deal-to-delivery/SKILL.md`, especially invoice, deal acceptance, audit logging, and tool-gateway boundaries.

## 5. Show Artifacts

Walk through the generated and integration assets:

- `demo/expected_outputs/happy_path_summary.json` for the deterministic CLI output shape.
- `odoo_addons/deal_to_delivery_agent/` for the Odoo bridge addon mounted into `/mnt/extra-addons`.
- `presets/` for NemoClaw policies.
- `workspace/` for local agent identity, memory, and operating context.
- `THIRD_PARTY_NOTICES.md` for dependency and API references.

No real API keys are needed for this scripted path. Use `.env.example` only as a template for live integration trials.
