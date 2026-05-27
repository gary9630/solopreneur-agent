ifneq (,$(wildcard .env))
include .env
export
endif

SANDBOX ?= deal-demo

.PHONY: test demo odoo-up nemoclaw-policies nemoclaw-skills nemoclaw-workspace nemoclaw-dashboard nemoclaw-dashboard-stop nemoclaw-dashboard-restart nemoclaw-solopreneur-sandbox nemoclaw-solopreneur-sandbox-recreate nemoclaw-solopreneur-sandbox-destroy nemoclaw-solopreneur-sandbox-destroy-clean nemoclaw-solopreneur-plugin-install tool-gateway telegram-ops

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

nemoclaw-workspace:
	bash scripts/sync_openclaw_workspace.sh

nemoclaw-dashboard:
	bash scripts/forward_nemoclaw_dashboard.sh

nemoclaw-dashboard-stop:
	bash scripts/stop_nemoclaw_dashboard.sh

nemoclaw-dashboard-restart:
	bash scripts/stop_nemoclaw_dashboard.sh && bash scripts/forward_nemoclaw_dashboard.sh

nemoclaw-solopreneur-sandbox:
	bash scripts/onboard_solopreneur_openclaw_sandbox.sh

nemoclaw-solopreneur-sandbox-recreate:
	bash scripts/onboard_solopreneur_openclaw_sandbox.sh --fresh --recreate-sandbox

nemoclaw-solopreneur-sandbox-destroy:
	bash scripts/stop_nemoclaw_dashboard.sh
	nemoclaw $(SANDBOX) destroy --yes

nemoclaw-solopreneur-sandbox-destroy-clean:
	bash scripts/stop_nemoclaw_dashboard.sh
	nemoclaw $(SANDBOX) destroy --yes --cleanup-gateway

nemoclaw-solopreneur-plugin-install:
	SANDBOX="$(SANDBOX)" bash scripts/install_solopreneur_openclaw_plugin.sh
	SANDBOX="$(SANDBOX)" bash scripts/sync_openclaw_workspace.sh
	nemoclaw "$(SANDBOX)" exec -- openclaw plugins validate --root /sandbox/.openclaw/extensions/solopreneur-tools --entry dist/index.js
	nemoclaw "$(SANDBOX)" exec -- openclaw plugins registry --refresh
	nemoclaw "$(SANDBOX)" recover

tool-gateway:
	bash scripts/start_tool_gateway.sh

telegram-ops:
	bash scripts/start_agent_telegram_ops.sh
