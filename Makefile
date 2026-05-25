.PHONY: test demo odoo-up nemoclaw-policies nemoclaw-skills

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
