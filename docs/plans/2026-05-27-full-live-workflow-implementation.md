# Full-Live Workflow Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a gated full-live demo where OpenClaw and the Agent App Telegram bot can create and query real Odoo/Linear/GitHub/Telegram artifacts through the local tool gateway.

**Architecture:** `agent_app` becomes the execution gateway. OpenClaw calls `/tools/**` routes through NemoClaw policy. The Agent App Telegram bot uses polling and shares the same CRM/tool services. Live side effects require explicit env and request gates.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, NVIDIA NIM chat/multimodal APIs, Odoo JSON-2, Linear GraphQL, GitHub REST, Telegram Bot API, NemoClaw/OpenClaw.

---

### Task 1: Configuration And Request Models

**Files:**
- Modify: `agent_app/src/deal_agent/config.py`
- Create: `agent_app/src/deal_agent/tool_models.py`
- Test: `agent_app/tests/test_tool_models.py`

**Step 1: Write failing tests**

Add tests for:

- `ToolWorkflowRequest` strips `run_id` and `message`.
- `live=true` is separate from the host env gate.
- `AgentTelegramSettings.allowed_user_ids` parses comma-separated ids.
- Missing live credentials are reported as names only, never values.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_tool_models.py -v`

Expected: fails because `deal_agent.tool_models` does not exist.

**Step 3: Implement minimal code**

Add models:

- `ToolWorkflowRequest(run_id, message, live=False)`
- `ToolWorkflowResponse(mode, live_enabled, run, missing_config=[])`
- `BusinessCardContact(name, company, title, email, phone, website, raw_text, confidence)`
- `BusinessCardToolRequest(run_id, image_base64, mime_type, live=False)`
- `CrmLookupRequest(query, live=False)`
- `CrmLookupResult(query, contacts, leads)`

Extend settings with:

- `live_workflow_enabled: bool = False`
- `nim_base_url`
- `nim_model`
- `nim_vision_model`
- `odoo_database`
- `odoo_api_key`
- `linear_team_id`
- `github_repository`
- `agent_telegram_bot_token`
- `agent_telegram_chat_id`
- `agent_telegram_allowed_user_ids`

Add helper methods:

- `missing_live_workflow_config() -> list[str]`
- `missing_agent_telegram_config() -> list[str]`
- `agent_telegram_allowed_user_id_set() -> set[int]`

**Step 4: Verify green**

Run: `cd agent_app && uv run pytest tests/test_tool_models.py -v`

Expected: all pass.

---

### Task 2: NIM-Backed Workflow Model Services

**Files:**
- Modify: `agent_app/src/deal_agent/services/model_services.py`
- Modify: `agent_app/src/deal_agent/services/__init__.py`
- Test: `agent_app/tests/test_model_services.py`

**Step 1: Write failing tests**

Tests:

- `NimModelServices.extract_intake()` calls `NimChatClient.chat_json()` and parses `IntakeSummary`.
- `draft_quote()` parses `QuoteDraft`.
- `break_down_issues()` parses a list of `DeliveryIssue`.
- `compose_notification()` parses a text notification.
- malformed NIM output raises a non-retryable validation error.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_model_services.py -v`

Expected: fail because `NimModelServices` does not exist.

**Step 3: Implement minimal code**

Use the existing `NimChatClient.chat_json(system_prompt, user_prompt)` helper. Keep prompts narrow and JSON-only. Convert parsed JSON into existing Pydantic models.

**Step 4: Verify green**

Run the model service tests.

---

### Task 3: Gated Deal-To-Delivery Tool Endpoint

**Files:**
- Modify: `agent_app/src/deal_agent/main.py`
- Create: `agent_app/src/deal_agent/live_factory.py`
- Test: `agent_app/tests/test_tool_gateway.py`

**Step 1: Write failing tests**

Tests:

- `POST /tools/deal-to-delivery/run` with default request uses fake runner and returns `mode=dry_run`.
- `live=true` without `LIVE_WORKFLOW_ENABLED=1` returns `mode=dry_run` and does not call live factory.
- `live=true` with env gate but missing credentials returns `400` with `missing_config`.
- `live=true` with env gate and dependency-overridden live runner returns completed live response.
- endpoint rejects extra fields.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_tool_gateway.py -v`

Expected: fails because route and factory do not exist.

**Step 3: Implement minimal code**

Add:

- `create_fake_runner()`
- `create_live_runner(settings=settings)`
- `run_tool_workflow()`

Use existing `DealWorkflowRunner`, `FakeModelServices`, `NimModelServices`, `OdooHttpConnector`, `LinearHttpConnector`, `GitHubHttpConnector`, `TelegramHttpConnector`.

For GitHub repository parsing, require `owner/repo`.

**Step 4: Verify green**

Run: `cd agent_app && uv run pytest tests/test_tool_gateway.py -v`

Expected: all pass.

---

### Task 4: Odoo CRM Helpers And Custom Audit Writes

**Files:**
- Modify: `agent_app/src/deal_agent/connectors/odoo.py`
- Modify: `agent_app/src/deal_agent/connectors/base.py`
- Test: `agent_app/tests/test_http_connectors.py`

**Step 1: Write failing tests**

Add mocked JSON-2 tests for:

- `upsert_contact_from_business_card()` searches by email, updates existing partner when found.
- creates partner when no existing contact is found.
- `create_crm_lead_for_contact()` creates `crm.lead`.
- `lookup_contacts()` searches `res.partner` and `crm.lead`.
- `write_deal_context()` creates `deal.context`.
- `write_audit_log()` creates `agent.audit.log`.

**Step 2: Run tests**

Run targeted tests in `test_http_connectors.py`.

Expected: fail because methods do not exist.

**Step 3: Implement minimal code**

Use Odoo JSON-2:

- `res.partner/search_read`
- `res.partner/create`
- `res.partner/write`
- `crm.lead/create`
- `crm.lead/search_read`
- `deal.context/create`
- `agent.audit.log/create`

Keep payloads small and Odoo 19-compatible.

**Step 4: Verify green**

Run targeted tests and then `cd agent_app && uv run pytest tests/test_http_connectors.py -v`.

Expected: pass.

---

### Task 5: NIM Business-Card Extraction Service

**Files:**
- Modify: `agent_app/src/deal_agent/nim_client.py`
- Create: `agent_app/src/deal_agent/services/business_card.py`
- Test: `agent_app/tests/test_business_card_service.py`

**Step 1: Write failing tests**

Tests:

- multimodal client sends image content using model from `NIM_VISION_MODEL`.
- service parses JSON into `BusinessCardContact`.
- malformed/low-confidence output returns a validation error with no side effect.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_business_card_service.py -v`

Expected: fail.

**Step 3: Implement minimal code**

Add `NimVisionClient.extract_business_card(image_base64, mime_type)` returning structured JSON. Prompt must require JSON only with fields:

- `name`
- `company`
- `title`
- `email`
- `phone`
- `website`
- `raw_text`
- `confidence`

**Step 4: Verify green**

Run test file.

---

### Task 6: CRM Tool Endpoints

**Files:**
- Modify: `agent_app/src/deal_agent/main.py`
- Create: `agent_app/src/deal_agent/crm_tools.py`
- Test: `agent_app/tests/test_crm_tools.py`

**Step 1: Write failing tests**

Tests:

- `/tools/crm/business-card` dry-run extracts contact and returns planned Odoo actions without live side effect.
- live gated request creates/upserts contact and CRM lead.
- `/tools/crm/lookup` returns Odoo contact/lead results when live-enabled.
- lookup without live gate returns a safe refusal/dry-run response.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_crm_tools.py -v`

Expected: fail.

**Step 3: Implement minimal code**

`crm_tools.py` should depend on interfaces:

- `BusinessCardExtractor`
- `OdooCrmGateway`

`main.py` wires fake/dry-run behavior by default and live behavior only when the double gate is satisfied.

**Step 4: Verify green**

Run test file.

---

### Task 7: Agent App Telegram Polling Bot

**Files:**
- Modify: `agent_app/src/deal_agent/connectors/telegram.py`
- Create: `agent_app/src/deal_agent/telegram_ops.py`
- Create: `agent_app/src/deal_agent/telegram_ops_cli.py`
- Modify: `agent_app/pyproject.toml`
- Test: `agent_app/tests/test_telegram_ops.py`

**Step 1: Write failing tests**

Tests:

- unauthorized user id is rejected and no CRM tool is called.
- `/start` returns capability text.
- text message routes to CRM lookup.
- photo message downloads highest-resolution photo and routes to business-card tool.
- CLI entrypoint is registered as `deal-agent-telegram-ops`.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_telegram_ops.py -v`

Expected: fail.

**Step 3: Implement minimal code**

Telegram connector additions:

- `get_updates(offset=None)`
- `get_file(file_id)`
- `download_file(file_path)`
- `send_message(chat_id, text)`

Polling loop:

- reads updates
- checks allowlist
- handles `/start`
- handles photos
- handles text lookup
- advances offset

**Step 4: Verify green**

Run test file.

---

### Task 8: Scripts, Make Targets, Skill, And Demo Docs

**Files:**
- Modify: `Makefile`
- Create: `scripts/start_tool_gateway.sh`
- Create: `scripts/start_agent_telegram_ops.sh`
- Modify: `skills/deal-to-delivery/SKILL.md`
- Modify: `skills/deal-to-delivery/sop.md`
- Modify: `README.md`
- Modify: `docs/demo-script.md`
- Test: `agent_app/tests/test_project_assets.py`
- Test: `agent_app/tests/test_nemoclaw_assets.py`

**Step 1: Write failing tests**

Expect:

- Makefile targets: `tool-gateway`, `telegram-ops`, existing `nemoclaw-dashboard`.
- docs mention `/tools/deal-to-delivery/run`, `LIVE_WORKFLOW_ENABLED=1`, and Agent App Telegram bot.
- skill mentions exact gateway route and double opt-in.

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest tests/test_project_assets.py tests/test_nemoclaw_assets.py -v`

Expected: fail.

**Step 3: Implement minimal code/docs**

Scripts:

- `scripts/start_tool_gateway.sh`: runs `uv run uvicorn deal_agent.main:app --host 0.0.0.0 --port 8088`
- `scripts/start_agent_telegram_ops.sh`: runs `uv run deal-agent-telegram-ops`

**Step 4: Verify green**

Run asset tests.

---

### Task 9: Live Smoke Tests And Demo Verification

**Files:**
- Create: `agent_app/tests/live/test_agent_telegram_live.py`
- Create: `agent_app/tests/live/test_tool_gateway_live.py`
- Modify: `README.md`
- Modify: `docs/demo-script.md`

**Step 1: Write failing/skipping tests**

Live tests should skip unless explicit env vars are present:

- `LIVE_WORKFLOW_ENABLED=1`
- `LIVE_TOOL_WORKFLOW_RUN=1`
- `AGENT_TELEGRAM_LIVE_POLL=1` or `AGENT_TELEGRAM_LIVE_SEND=1`

**Step 2: Run tests**

Run: `cd agent_app && uv run pytest -m live -v`

Expected: existing tests pass/skip; new tests skip without opt-in.

**Step 3: Implement minimal smoke tests**

Smoke tests:

- health check for local gateway route if running.
- Agent Telegram sendMessage with explicit send opt-in.
- optional live workflow creates refs when fully opted in.

**Step 4: Verify**

Run:

- `cd agent_app && uv run pytest -v`
- `cd agent_app && set -a; source ../.env; set +a; uv run pytest -m live -v`

Expected: unit tests pass; live tests pass or skip clearly.
