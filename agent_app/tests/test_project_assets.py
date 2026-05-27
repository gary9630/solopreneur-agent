import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    path = REPO_ROOT / relative_path

    assert path.exists(), f"missing {relative_path}"
    return path.read_text(encoding="utf-8")


def test_env_example_lists_integrations_without_real_secrets():
    env_text = read_text(".env.example")

    required_names = [
        "NVIDIA_API_KEY",
        "NIM_BASE_URL",
        "NIM_MODEL",
        "NIM_VISION_MODEL",
        "LIVE_WORKFLOW_ENABLED",
        "ODOO_URL",
        "ODOO_DATABASE",
        "ODOO_API_KEY",
        "LINEAR_API_KEY",
        "LINEAR_TEAM_ID",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_CHAT_ID",
        "AGENT_TELEGRAM_ALLOWED_USER_IDS",
        "SANDBOX",
    ]
    for name in required_names:
        assert re.search(rf"^{name}=", env_text, re.MULTILINE), f"missing {name}"

    forbidden_secret_patterns = [
        re.compile(r"nvapi-[A-Za-z0-9_-]+", re.IGNORECASE),
        re.compile(r"github_pat_[A-Za-z0-9_]+", re.IGNORECASE),
        re.compile(r"ghp_[A-Za-z0-9_]+", re.IGNORECASE),
        re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
    ]
    for pattern in forbidden_secret_patterns:
        assert pattern.search(env_text) is None


def test_docker_compose_exposes_odoo_with_extra_addons_mount():
    compose = yaml.safe_load(read_text("docker-compose.yml"))

    services = compose["services"]

    assert "db" in services
    assert "odoo" in services
    assert "postgres" in services["db"]["image"]
    assert services["odoo"]["image"] in {"odoo:19.0", "odoo:19"}
    assert "db" in services["odoo"]["depends_on"]

    volumes = services["odoo"]["volumes"]
    assert "./odoo_addons:/mnt/extra-addons" in volumes


def test_makefile_has_demo_setup_targets_with_expected_commands():
    makefile = read_text("Makefile")

    expected_commands = {
        "test": "cd agent_app && uv run pytest",
        "demo": "cd agent_app && uv run deal-agent-demo ../demo/customer_inputs/01_initial_request.txt",
        "odoo-up": "docker compose up -d db odoo",
        "nemoclaw-policies": "bash scripts/apply_nemoclaw_policies.sh",
        "nemoclaw-skills": "bash scripts/install_nemoclaw_skills.sh",
        "nemoclaw-dashboard": "bash scripts/forward_nemoclaw_dashboard.sh",
        "nemoclaw-dashboard-stop": "bash scripts/stop_nemoclaw_dashboard.sh",
        "nemoclaw-dashboard-restart": "bash scripts/stop_nemoclaw_dashboard.sh && bash scripts/forward_nemoclaw_dashboard.sh",
        "nemoclaw-solopreneur-sandbox": "bash scripts/onboard_solopreneur_openclaw_sandbox.sh",
        "tool-gateway": "bash scripts/start_tool_gateway.sh",
        "telegram-ops": "bash scripts/start_agent_telegram_ops.sh",
    }

    for target, command in expected_commands.items():
        assert re.search(rf"^{re.escape(target)}:\n\t{re.escape(command)}$", makefile, re.MULTILINE)


def test_makefile_exports_dotenv_to_demo_targets():
    makefile = read_text("Makefile")

    assert re.search(
        r"^ifneq \(,\$\(wildcard \.env\)\)\ninclude \.env\nexport\nendif$",
        makefile,
        re.MULTILINE,
    )


def test_readme_and_demo_docs_describe_hackathon_mvp_flow_without_secrets():
    readme = read_text("README.md")
    demo_script = read_text("docs/demo-script.md")
    notices = read_text("THIRD_PARTY_NOTICES.md")
    combined = "\n".join([readme, demo_script, notices])

    required_phrases = [
        "hackathon MVP",
        "Odoo 19",
        "Odoo 19 demo baseline",
        "uv run pytest",
        "uv run deal-agent-demo",
        "docker compose up -d db odoo",
        "bash scripts/apply_nemoclaw_policies.sh",
        "bash scripts/install_nemoclaw_skills.sh",
        "make nemoclaw-solopreneur-sandbox",
        "make tool-gateway",
        "make telegram-ops",
        "/tools/deal-to-delivery/run",
        "LIVE_WORKFLOW_ENABLED=1",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "Odoo and NemoClaw source code is not vendored",
        "NVIDIA NemoClaw",
        "Telegram Bot API",
    ]
    for phrase in required_phrases:
        assert phrase in combined

    assert "nvapi-" not in combined.lower()
