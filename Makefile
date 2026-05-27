ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: test demo odoo-up nemoclaw-policies nemoclaw-skills nemoclaw-dashboard nemoclaw-dashboard-stop nemoclaw-dashboard-restart nemoclaw-solopreneur-sandbox tool-gateway telegram-ops

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

nemoclaw-dashboard:
	bash scripts/forward_nemoclaw_dashboard.sh

nemoclaw-dashboard-stop:
	bash scripts/stop_nemoclaw_dashboard.sh

nemoclaw-dashboard-restart:
	bash scripts/stop_nemoclaw_dashboard.sh && bash scripts/forward_nemoclaw_dashboard.sh

nemoclaw-solopreneur-sandbox:
	bash scripts/onboard_solopreneur_openclaw_sandbox.sh

tool-gateway:
	bash scripts/start_tool_gateway.sh

telegram-ops:
	bash scripts/start_agent_telegram_ops.sh
