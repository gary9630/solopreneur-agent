import re
import tomllib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

PRESET_PATHS = [
    REPO_ROOT / "presets" / "tool-gateway-local.yaml",
    REPO_ROOT / "presets" / "linear.yaml",
    REPO_ROOT / "presets" / "odoo-local.yaml",
]
WORKSPACE_FILES = [
    "AGENTS.md",
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
]
SCRIPT_PATHS = [
    REPO_ROOT / "scripts" / "setup_nemoclaw.sh",
    REPO_ROOT / "scripts" / "apply_nemoclaw_policies.sh",
    REPO_ROOT / "scripts" / "install_nemoclaw_skills.sh",
]
PRIVATE_ALLOWED_IPS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]


def read_text(path: Path) -> str:
    assert path.exists(), f"missing {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def parse_skill_frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n")
    _, frontmatter, _ = text.split("---", 2)

    parsed = {}
    for line in frontmatter.strip().splitlines():
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def load_preset(path: Path) -> dict:
    return yaml.safe_load(read_text(path))


def test_deal_to_delivery_skill_has_named_frontmatter():
    skill_text = read_text(REPO_ROOT / "skills" / "deal-to-delivery" / "SKILL.md")

    frontmatter = parse_skill_frontmatter(skill_text)

    assert frontmatter["name"] == "deal-to-delivery"


def test_pyyaml_is_declared_as_an_explicit_test_dependency():
    pyproject = tomllib.loads(read_text(REPO_ROOT / "agent_app" / "pyproject.toml"))

    dev_dependencies = pyproject["dependency-groups"]["dev"]

    assert "pyyaml>=6.0" in dev_dependencies


def test_presets_are_nemoclaw_yaml_documents():
    for path in PRESET_PATHS:
        content = read_text(path)
        preset = load_preset(path)

        assert preset["preset"]["name"] == path.stem
        assert preset["preset"]["description"]
        assert isinstance(preset["network_policies"], dict)
        assert preset["network_policies"]
        assert re.search(r"^network_policies:\n", content, re.MULTILINE)

        for policy in preset["network_policies"].values():
            assert policy["endpoints"]
            assert policy["binaries"]


def test_local_presets_allow_openshell_host_gateway_with_private_ips():
    expected_gateway_endpoints = [
        (REPO_ROOT / "presets" / "tool-gateway-local.yaml", "tool_gateway_local", 8088),
        (REPO_ROOT / "presets" / "odoo-local.yaml", "odoo_local", 8069),
    ]

    for path, policy_name, port in expected_gateway_endpoints:
        preset = load_preset(path)
        endpoints = preset["network_policies"][policy_name]["endpoints"]
        gateway_endpoint = next(
            endpoint
            for endpoint in endpoints
            if endpoint["host"] == "host.openshell.internal" and endpoint["port"] == port
        )

        assert gateway_endpoint["allowed_ips"] == PRIVATE_ALLOWED_IPS
        assert gateway_endpoint["protocol"] == "rest"
        assert gateway_endpoint["enforcement"] == "enforce"


def test_workspace_files_exist_for_local_nemoclaw_context():
    for filename in WORKSPACE_FILES:
        content = read_text(REPO_ROOT / "workspace" / filename)

        assert "deal-to-delivery" in content.lower()


def test_skill_hard_rules_cover_demo_safety_boundaries():
    skill_text = read_text(REPO_ROOT / "skills" / "deal-to-delivery" / "SKILL.md").lower()

    required_rules = [
        "never finalize invoices",
        "never mark a deal won without explicit acceptance",
        "always log high-impact actions",
        "prefer tool gateway for side effects",
        "use linear for engineering execution",
    ]
    for rule in required_rules:
        assert rule in skill_text


def test_scripts_are_offline_safe_and_do_not_contain_real_secrets():
    secret_patterns = [
        re.compile(r"nvapi-[A-Za-z0-9_-]+"),
    ]

    for path in SCRIPT_PATHS:
        script = read_text(path)

        assert "NVIDIA_API_KEY" in script or path.name != "setup_nemoclaw.sh"
        for pattern in secret_patterns:
            assert pattern.search(script) is None


def test_scripts_use_current_nemoclaw_policy_and_skill_commands():
    policy_script = read_text(REPO_ROOT / "scripts" / "apply_nemoclaw_policies.sh")
    skill_script = read_text(REPO_ROOT / "scripts" / "install_nemoclaw_skills.sh")

    assert 'nemoclaw sandbox policy add "$SANDBOX" --from-dir ./presets --yes' in policy_script
    assert 'nemoclaw sandbox skill install "$SANDBOX" ./skills/deal-to-delivery' in skill_script
