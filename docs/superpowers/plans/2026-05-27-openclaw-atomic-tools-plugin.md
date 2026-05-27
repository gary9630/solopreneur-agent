# OpenClaw Atomic Tools Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class OpenClaw plugin scaffold that exposes composable solopreneur business tools instead of a hard-coded full workflow.

**Architecture:** OpenClaw receives small atomic tools with clear schemas. Each tool calls the existing host `agent_app` gateway route for its domain action, while the `deal-to-delivery` skill teaches the LLM when to combine tools from natural user intent. The plugin is packaged with a Dockerfile context so it can be baked into a NemoClaw sandbox later.

**Tech Stack:** OpenClaw plugin JavaScript, NemoClaw custom sandbox Dockerfile assets, Python pytest asset tests, existing FastAPI tool gateway routes.

---

### Task 1: Plugin Asset Contract

**Files:**
- Modify: `agent_app/tests/test_nemoclaw_assets.py`
- Create: `openclaw_plugins/solopreneur-tools/openclaw.plugin.json`
- Create: `openclaw_plugins/solopreneur-tools/index.js`

- [x] **Step 1: Write failing tests** for plugin manifest, exported atomic tool names, and absence of `deal_to_delivery_run`.
- [x] **Step 2: Run focused pytest** and verify it fails because plugin files do not exist.
- [x] **Step 3: Implement minimal plugin files** with tool declarations for `crm_lookup`, `business_card_capture`, `deal_prepare`, `odoo_create_deal_artifacts`, `delivery_create_tasks`, and `notify_stakeholder`.
- [x] **Step 4: Run focused pytest** and verify it passes.

### Task 2: Skill Routing Examples

**Files:**
- Modify: `skills/deal-to-delivery/SKILL.md`
- Modify: `skills/deal-to-delivery/sop.md`
- Modify: `agent_app/tests/test_nemoclaw_assets.py`

- [x] **Step 1: Write failing tests** that require natural-language routing examples and forbid `deal_to_delivery_run` in the skill.
- [x] **Step 2: Update skill docs** so they describe which atomic tools to call for CRM lookup, business-card capture, deal preparation, Odoo artifacts, delivery task creation, and stakeholder notification.
- [x] **Step 3: Run focused pytest** and verify it passes.

### Task 3: Bake Context Assets

**Files:**
- Create: `openclaw_plugins/solopreneur-tools/package.json`
- Create: `sandbox/solopreneur-tools/Dockerfile`
- Create: `scripts/build_solopreneur_openclaw_sandbox.sh`
- Modify: `Makefile`
- Modify: `agent_app/tests/test_project_assets.py`

- [x] **Step 1: Write failing tests** for a Makefile target and Dockerfile that copies the plugin into `/sandbox/.openclaw/extensions/solopreneur-tools`.
- [x] **Step 2: Implement the package metadata, Dockerfile, script, and Makefile target.**
- [x] **Step 3: Run focused pytest** and verify it passes.

### Task 4: Atomic Gateway Dry-Run Endpoints

**Files:**
- Modify: `agent_app/src/deal_agent/main.py`
- Modify: `agent_app/src/deal_agent/tool_models.py`
- Modify: `agent_app/tests/test_tool_gateway.py`

- [x] **Step 1: Write failing tests** for `/tools/deal/prepare`, `/tools/odoo/deal-artifacts`, `/tools/delivery/tasks`, and `/tools/notify/stakeholder`.
- [x] **Step 2: Implement dry-run endpoint contracts** so the plugin does not hit 404 when baked into OpenClaw.
- [x] **Step 3: Wire live Odoo and delivery endpoints to existing runner components behind the existing live gates.**
- [x] **Step 4: Run focused pytest** and verify the atomic endpoint tests pass.

### Task 5: Final Verification

**Files:**
- All changed files above.

- [x] **Step 1: Run `uv run pytest -q` from `agent_app`.**
- [x] **Step 2: Run `git diff --check`.**
- [x] **Step 3: Summarize how to bake/onboard the plugin in the next sandbox step.**
