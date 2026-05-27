# NVIDIA NemoClaw Agent MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a hackathon-ready Deal-to-Delivery Agent MVP that can replay a full customer brief to Odoo, Linear, GitHub, invoice draft, and Telegram notification workflow with tests.

**Architecture:** Use a deterministic Python workflow runner as the execution core, with model-backed services for intake, quote, issue breakdown, and notifications. External side effects are isolated behind connector interfaces so unit and e2e tests can run with fakes before live credentials are configured.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, pytest, Docker Compose, Odoo custom addon, NemoClaw presets/skills/workspace files, NVIDIA NIM OpenAI-compatible chat completions, Linear GraphQL, GitHub REST, Telegram Bot API.

---

## Implementation Rules

- Follow TDD: write or update tests before production code for each behavior.
- Keep live API calls opt-in behind environment variables.
- Do not commit secrets.
- Do not edit `reference-works/`.
- Do not batch-delete files or directories.
- Prefer fake connector e2e tests for CI-speed validation.
- Commit after each completed task if execution time allows.

## Task 1: Scaffold Python Agent App

**Files:**

- Create: `agent_app/pyproject.toml`
- Create: `agent_app/src/deal_agent/__init__.py`
- Create: `agent_app/src/deal_agent/main.py`
- Create: `agent_app/src/deal_agent/config.py`
- Create: `agent_app/tests/test_health.py`

**Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient

from deal_agent.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run from `agent_app/`:

```bash
uv run pytest tests/test_health.py -v
```

Expected: FAIL because the package/app does not exist yet.

**Step 3: Add minimal app scaffold**

`agent_app/pyproject.toml`:

```toml
[project]
name = "deal-agent"
version = "0.1.0"
description = "Deal-to-Delivery Agent MVP"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "httpx>=0.27",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
  "pytest>=8.2",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`agent_app/src/deal_agent/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Deal-to-Delivery Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`agent_app/src/deal_agent/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nvidia_api_key: str | None = None
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    odoo_url: str = "http://localhost:8069"
    odoo_database: str | None = None
    odoo_api_key: str | None = None
    linear_api_key: str | None = None
    github_token: str | None = None
    telegram_bot_token: str | None = None
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_health.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/pyproject.toml agent_app/src/deal_agent/__init__.py agent_app/src/deal_agent/main.py agent_app/src/deal_agent/config.py agent_app/tests/test_health.py
git commit -m "feat: scaffold agent app"
```

## Task 2: Define Domain Models and Workflow States

**Files:**

- Create: `agent_app/src/deal_agent/models.py`
- Create: `agent_app/tests/test_models.py`

**Step 1: Write failing model tests**

```python
from deal_agent.models import DealBrief, WorkflowRun, WorkflowState


def test_deal_brief_derives_stable_input_hash():
    brief = DealBrief(
        customer_name="ACME Studio",
        contact_name="Jane",
        contact_email="jane@example.com",
        message="Need a Shopify-to-Odoo workflow prototype.",
    )

    assert brief.input_hash == "f9e6d23be5ad4df4"


def test_workflow_run_starts_new():
    run = WorkflowRun.from_brief("run_123", "hello")

    assert run.run_id == "run_123"
    assert run.state is WorkflowState.NEW
    assert run.steps == []
```

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL because models do not exist.

**Step 3: Implement models**

Use Pydantic models with `extra="forbid"` for request/response safety.

Required objects:

- `WorkflowState` enum with all design states.
- `DealBrief`.
- `IntakeSummary`.
- `QuoteDraft`.
- `DeliveryIssue`.
- `ExternalRef`.
- `WorkflowStep`.
- `WorkflowRun`.

Implementation detail for `input_hash`: use SHA-256 over stable JSON, return first 16 hex characters. If the exact expected hash differs, update the test to assert determinism rather than a hardcoded value.

**Step 4: Run tests**

```bash
uv run pytest tests/test_models.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/models.py agent_app/tests/test_models.py
git commit -m "feat: add workflow domain models"
```

## Task 3: Implement Workflow State Machine

**Files:**

- Create: `agent_app/src/deal_agent/workflow.py`
- Create: `agent_app/tests/test_workflow.py`

**Step 1: Write failing state transition tests**

```python
import pytest

from deal_agent.models import WorkflowRun, WorkflowState
from deal_agent.workflow import InvalidTransition, advance


def test_valid_transition_records_step():
    run = WorkflowRun.from_brief("run_1", "brief")

    updated = advance(run, WorkflowState.INTAKE_SUMMARIZED, "intake", {"summary": "ok"})

    assert updated.state is WorkflowState.INTAKE_SUMMARIZED
    assert len(updated.steps) == 1
    assert updated.steps[0].state_before is WorkflowState.NEW
    assert updated.steps[0].state_after is WorkflowState.INTAKE_SUMMARIZED


def test_invalid_transition_is_rejected():
    run = WorkflowRun.from_brief("run_1", "brief")

    with pytest.raises(InvalidTransition):
        advance(run, WorkflowState.LINEAR_BOOTSTRAPPED, "linear", {})
```

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: FAIL because workflow module does not exist.

**Step 3: Implement transition table**

Allowed transitions:

```python
{
    NEW: {INTAKE_SUMMARIZED, FAILED_TERMINAL},
    INTAKE_SUMMARIZED: {ODOO_LEAD_CREATED, FAILED_RETRYABLE, FAILED_TERMINAL},
    ODOO_LEAD_CREATED: {QUOTE_DRAFTED, FAILED_RETRYABLE},
    QUOTE_DRAFTED: {ODOO_QUOTATION_CREATED, FAILED_RETRYABLE},
    ODOO_QUOTATION_CREATED: {LINEAR_BOOTSTRAPPED, FAILED_RETRYABLE},
    LINEAR_BOOTSTRAPPED: {GITHUB_DELIVERY_TRACKED, FAILED_RETRYABLE},
    GITHUB_DELIVERY_TRACKED: {INVOICE_DRAFT_CREATED, FAILED_RETRYABLE},
    INVOICE_DRAFT_CREATED: {TELEGRAM_NOTIFIED, FAILED_RETRYABLE},
    TELEGRAM_NOTIFIED: {COMPLETED, FAILED_RETRYABLE},
}
```

`advance()` should return a copied run with one appended `WorkflowStep`.

**Step 4: Run tests**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/workflow.py agent_app/tests/test_workflow.py
git commit -m "feat: add workflow state machine"
```

## Task 4: Add Connector Protocols and Fake Connectors

**Files:**

- Create: `agent_app/src/deal_agent/connectors/__init__.py`
- Create: `agent_app/src/deal_agent/connectors/base.py`
- Create: `agent_app/src/deal_agent/connectors/fakes.py`
- Create: `agent_app/tests/test_fake_connectors.py`

**Step 1: Write failing fake connector tests**

```python
from deal_agent.connectors.fakes import FakeOdooConnector
from deal_agent.models import DealBrief, IntakeSummary, QuoteDraft


def test_fake_odoo_connector_is_idempotent_for_leads():
    connector = FakeOdooConnector()
    brief = DealBrief(customer_name="ACME", message="Build an app")
    summary = IntakeSummary(customer_name="ACME", scope_items=["Build an app"], risks=[])

    first = connector.create_lead("run_1", brief, summary)
    second = connector.create_lead("run_1", brief, summary)

    assert first == second
    assert len(connector.leads) == 1
```

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_fake_connectors.py -v
```

Expected: FAIL.

**Step 3: Implement connector protocols**

Define protocols for:

- `OdooConnector`
- `LinearConnector`
- `GitHubConnector`
- `TelegramConnector`

Each method takes `run_id` and returns `ExternalRef`.

Implement fake connectors with in-memory dictionaries keyed by idempotency keys.

**Step 4: Run tests**

```bash
uv run pytest tests/test_fake_connectors.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/connectors agent_app/tests/test_fake_connectors.py
git commit -m "feat: add connector interfaces and fakes"
```

## Task 5: Add NIM Client and Model Service Fakes

**Files:**

- Create: `agent_app/src/deal_agent/nim_client.py`
- Create: `agent_app/src/deal_agent/services/__init__.py`
- Create: `agent_app/src/deal_agent/services/model_services.py`
- Create: `agent_app/tests/test_model_services.py`

**Step 1: Write failing tests for structured model outputs**

```python
from deal_agent.services.model_services import FakeModelServices


def test_fake_model_services_extracts_intake():
    services = FakeModelServices()

    summary = services.extract_intake("ACME needs a two-week Odoo automation prototype.")

    assert summary.customer_name == "ACME"
    assert summary.scope_items
    assert summary.risks == []
```

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_model_services.py -v
```

Expected: FAIL.

**Step 3: Implement fake services and NIM client shell**

`FakeModelServices` returns deterministic demo outputs.

`NimChatClient` should:

- accept `api_key`, `model`, and `base_url`
- call `POST /v1/chat/completions`
- never log the API key
- expose `chat_json(system_prompt, user_prompt)` for later live smoke tests

Do not wire live NIM calls into default workflow tests yet.

**Step 4: Run tests**

```bash
uv run pytest tests/test_model_services.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/nim_client.py agent_app/src/deal_agent/services agent_app/tests/test_model_services.py
git commit -m "feat: add model service abstraction"
```

## Task 6: Build End-to-End Workflow Runner With Fakes

**Files:**

- Create: `agent_app/src/deal_agent/runner.py`
- Create: `agent_app/tests/test_runner_e2e.py`

**Step 1: Write failing fake e2e test**

```python
from deal_agent.connectors.fakes import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import WorkflowState
from deal_agent.runner import DealWorkflowRunner
from deal_agent.services.model_services import FakeModelServices


def test_runner_completes_happy_path_with_fakes():
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )

    run = runner.run("run_1", "ACME needs a two-week Odoo automation prototype.")

    assert run.state is WorkflowState.COMPLETED
    assert [step.step_name for step in run.steps] == [
        "intake",
        "odoo_lead",
        "quote",
        "odoo_quotation",
        "linear",
        "github",
        "invoice",
        "telegram",
        "complete",
    ]
```

**Step 2: Run failing test**

```bash
uv run pytest tests/test_runner_e2e.py -v
```

Expected: FAIL.

**Step 3: Implement runner**

The runner calls:

1. `models.extract_intake`
2. `odoo.create_lead`
3. `models.draft_quote`
4. `odoo.create_quotation`
5. `models.break_down_issues`
6. `linear.bootstrap_project`
7. `github.create_delivery_issue`
8. `odoo.create_invoice_draft`
9. `models.compose_notification`
10. `telegram.send_status`

Use `advance()` after each successful step.

**Step 4: Run e2e test**

```bash
uv run pytest tests/test_runner_e2e.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/runner.py agent_app/tests/test_runner_e2e.py
git commit -m "feat: add deal workflow runner"
```

## Task 7: Expose Workflow API Endpoints

**Files:**

- Modify: `agent_app/src/deal_agent/main.py`
- Create: `agent_app/tests/test_api_workflows.py`

**Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient

from deal_agent.main import app


def test_demo_workflow_endpoint_completes_with_fakes():
    client = TestClient(app)

    response = client.post(
        "/workflows/demo",
        json={"run_id": "run_api_1", "message": "ACME needs an Odoo prototype."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run_api_1"
    assert body["state"] == "COMPLETED"
```

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_api_workflows.py -v
```

Expected: FAIL.

**Step 3: Implement endpoint**

Add:

- `POST /workflows/demo`
- request model with `run_id` and `message`
- response serialized from `WorkflowRun`

Use fake connectors by default for this endpoint. Keep live workflow endpoint separate for later.

**Step 4: Run tests**

```bash
uv run pytest tests/test_api_workflows.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/main.py agent_app/tests/test_api_workflows.py
git commit -m "feat: expose demo workflow API"
```

## Task 8: Add HTTP Connector Implementations With Mocked Tests

**Files:**

- Create: `agent_app/src/deal_agent/connectors/odoo.py`
- Create: `agent_app/src/deal_agent/connectors/linear.py`
- Create: `agent_app/src/deal_agent/connectors/github.py`
- Create: `agent_app/src/deal_agent/connectors/telegram.py`
- Create: `agent_app/tests/test_http_connectors.py`

**Step 1: Write tests using `httpx.MockTransport`**

Test cases:

- Odoo uses `POST /json/2/<model>/<method>` with bearer auth.
- Linear raises when JSON body contains `errors`.
- GitHub sends issue creation payload to `/repos/{owner}/{repo}/issues`.
- Telegram calls `/bot<TOKEN>/sendMessage`.

**Step 2: Run failing tests**

```bash
uv run pytest tests/test_http_connectors.py -v
```

Expected: FAIL.

**Step 3: Implement connectors**

Implementation requirements:

- Accept an injected `httpx.Client` for testability.
- Use timeouts.
- Never print tokens.
- Convert successful responses to `ExternalRef`.
- Raise typed connector errors for retryable vs terminal failures.

**Step 4: Run tests**

```bash
uv run pytest tests/test_http_connectors.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/connectors/odoo.py agent_app/src/deal_agent/connectors/linear.py agent_app/src/deal_agent/connectors/github.py agent_app/src/deal_agent/connectors/telegram.py agent_app/tests/test_http_connectors.py
git commit -m "feat: add HTTP connectors"
```

## Task 9: Add Demo CLI and Seed Inputs

**Files:**

- Create: `agent_app/src/deal_agent/demo_cli.py`
- Create: `demo/customer_inputs/01_initial_request.txt`
- Create: `demo/expected_outputs/happy_path_summary.json`
- Modify: `agent_app/pyproject.toml`
- Create: `agent_app/tests/test_demo_cli.py`

**Step 1: Write failing CLI test**

Use `tmp_path` and call a pure function such as `run_demo_from_text(message)`.

Expected assertions:

- final state is `COMPLETED`
- at least one Odoo, Linear, GitHub, and Telegram external ref exists

**Step 2: Run failing test**

```bash
uv run pytest tests/test_demo_cli.py -v
```

Expected: FAIL.

**Step 3: Implement CLI**

Expose:

```bash
uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt
```

The CLI prints compact JSON suitable for recording demos.

**Step 4: Run tests**

```bash
uv run pytest tests/test_demo_cli.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent_app/src/deal_agent/demo_cli.py agent_app/pyproject.toml agent_app/tests/test_demo_cli.py demo/customer_inputs/01_initial_request.txt demo/expected_outputs/happy_path_summary.json
git commit -m "feat: add replayable demo CLI"
```

## Task 10: Add Odoo Custom Addon Skeleton

**Files:**

- Create: `odoo_addons/deal_to_delivery_agent/__init__.py`
- Create: `odoo_addons/deal_to_delivery_agent/__manifest__.py`
- Create: `odoo_addons/deal_to_delivery_agent/models/__init__.py`
- Create: `odoo_addons/deal_to_delivery_agent/models/agent_audit_log.py`
- Create: `odoo_addons/deal_to_delivery_agent/models/deal_context.py`
- Create: `odoo_addons/deal_to_delivery_agent/views/agent_audit_log_views.xml`
- Create: `odoo_addons/deal_to_delivery_agent/views/deal_context_views.xml`
- Create: `odoo_addons/deal_to_delivery_agent/data/demo_products.xml`
- Create: `agent_app/tests/test_odoo_addon_structure.py`

**Step 1: Write failing structure test**

Assert:

- manifest exists
- manifest depends on `base`, `crm`, `sale`, `project`, `account`
- model files exist
- XML files are well-formed

**Step 2: Run failing test**

```bash
uv run pytest tests/test_odoo_addon_structure.py -v
```

Expected: FAIL.

**Step 3: Implement addon skeleton**

`__manifest__.py` should include:

```python
{
    "name": "Deal-to-Delivery Agent Bridge",
    "version": "0.1.0",
    "category": "Productivity",
    "summary": "Agent bridge for SME deal-to-delivery automation",
    "depends": ["base", "crm", "sale", "project", "account"],
    "data": [
        "data/demo_products.xml",
        "views/agent_audit_log_views.xml",
        "views/deal_context_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```

**Step 4: Run test**

```bash
uv run pytest tests/test_odoo_addon_structure.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add odoo_addons/deal_to_delivery_agent agent_app/tests/test_odoo_addon_structure.py
git commit -m "feat: add Odoo agent bridge addon"
```

## Task 11: Add NemoClaw Presets, Skill, Workspace, and Scripts

**Files:**

- Create: `presets/tool-gateway-local.yaml`
- Create: `presets/linear.yaml`
- Create: `presets/odoo-local.yaml`
- Create: `skills/deal-to-delivery/SKILL.md`
- Create: `skills/deal-to-delivery/sop.md`
- Create: `workspace/AGENTS.md`
- Create: `workspace/IDENTITY.md`
- Create: `workspace/SOUL.md`
- Create: `workspace/USER.md`
- Create: `workspace/MEMORY.md`
- Create: `scripts/setup_nemoclaw.sh`
- Create: `scripts/apply_nemoclaw_policies.sh`
- Create: `scripts/install_nemoclaw_skills.sh`
- Create: `agent_app/tests/test_nemoclaw_assets.py`

**Step 1: Write failing asset tests**

Assert:

- skill has YAML frontmatter with `name`.
- presets parse as YAML.
- workspace files exist.
- scripts contain no real API keys.

Add `pyyaml` to dev dependencies only if needed; otherwise use simple file checks.

**Step 2: Run failing test**

```bash
uv run pytest tests/test_nemoclaw_assets.py -v
```

Expected: FAIL.

**Step 3: Implement assets**

Use commands aligned with the local NemoClaw reference:

```bash
nemoclaw sandbox policy add "$SANDBOX" --from-dir ./presets --yes
nemoclaw sandbox skill install "$SANDBOX" ./skills/deal-to-delivery
```

Skill hard rules:

- Never finalize invoices.
- Never mark a deal won without explicit acceptance.
- Always log high-impact actions.
- Prefer tool gateway for side effects.
- Use Linear for engineering execution.

**Step 4: Run test**

```bash
uv run pytest tests/test_nemoclaw_assets.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add presets skills workspace scripts agent_app/tests/test_nemoclaw_assets.py
git commit -m "feat: add NemoClaw integration assets"
```

## Task 12: Add Docker Compose, Makefile, Env Example, and Third-party Notices

**Files:**

- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `.env.example`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `docs/demo-script.md`
- Modify: `README.md`

**Step 1: Write docs/config smoke test**

Create `agent_app/tests/test_project_assets.py` and assert:

- `.env.example` contains variable names but no `nvapi-`.
- `docker-compose.yml` references Odoo and mounts `./odoo_addons:/mnt/extra-addons`.
- `Makefile` has `test`, `demo`, `odoo-up`, `nemoclaw-policies`, and `nemoclaw-skills` targets.

**Step 2: Run failing test**

```bash
uv run pytest tests/test_project_assets.py -v
```

Expected: FAIL.

**Step 3: Implement assets**

Make targets:

```makefile
test:
	cd agent_app && uv run pytest

demo:
	cd agent_app && uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt

odoo-up:
	docker compose up -d db odoo

nemoclaw-policies:
	bash scripts/apply_nemoclaw_policies.sh

nemoclaw-skills:
	bash scripts/install_nemoclaw_skills.sh
```

Do not include real secrets in `.env.example`.

**Step 4: Run test**

```bash
uv run pytest tests/test_project_assets.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add docker-compose.yml Makefile .env.example THIRD_PARTY_NOTICES.md docs/demo-script.md README.md agent_app/tests/test_project_assets.py
git commit -m "docs: add demo setup and project assets"
```

## Task 13: Add Optional Live Smoke Tests

**Files:**

- Create: `agent_app/tests/live/test_nim_live.py`
- Create: `agent_app/tests/live/test_telegram_live.py`
- Create: `agent_app/tests/live/test_linear_live.py`
- Create: `agent_app/tests/live/test_odoo_live.py`
- Modify: `agent_app/pyproject.toml`

**Step 1: Write skipped-by-default live tests**

Each test should skip unless its required env vars are present.

Example:

```python
import os

import pytest


pytestmark = pytest.mark.live


def test_nim_live_smoke():
    if not os.getenv("NVIDIA_API_KEY"):
        pytest.skip("NVIDIA_API_KEY is not set")
```

**Step 2: Run default tests**

```bash
uv run pytest
```

Expected: PASS with live tests skipped.

**Step 3: Add pytest marker config**

Add:

```toml
markers = [
  "live: tests that call external services and require credentials",
]
```

**Step 4: Run live selection without credentials**

```bash
uv run pytest -m live
```

Expected: all live tests skip cleanly.

**Step 5: Commit**

```bash
git add agent_app/tests/live agent_app/pyproject.toml
git commit -m "test: add optional live smoke tests"
```

## Task 14: Final Verification

**Files:**

- Modify only files needed to fix verification failures.

**Step 1: Run full default test suite**

```bash
cd agent_app
uv run pytest
```

Expected: all non-live tests pass.

**Step 2: Run demo CLI**

```bash
cd agent_app
uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt
```

Expected: JSON output includes `"state": "COMPLETED"`.

**Step 3: Run project-level checks**

```bash
make test
make demo
```

Expected: both commands pass.

**Step 4: Inspect git status**

```bash
git status --short
```

Expected: only intentional files are modified or untracked.

**Step 5: Final commit**

If fixes were needed:

```bash
git add <fixed files>
git commit -m "chore: verify MVP demo workflow"
```

## Execution Notes

The critical path is Tasks 1 through 12. Task 13 is useful for credibility but should not block a working fake-connector demo. If time becomes constrained, prioritize:

1. Workflow runner with fake e2e test.
2. Odoo addon skeleton.
3. NemoClaw assets.
4. README/demo script.
5. Optional live smoke tests.
