import re
import tomllib
import json
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
    "TOOLS.md",
    "USER.md",
    "MEMORY.md",
]
SCRIPT_PATHS = [
    REPO_ROOT / "scripts" / "setup_nemoclaw.sh",
    REPO_ROOT / "scripts" / "apply_nemoclaw_policies.sh",
    REPO_ROOT / "scripts" / "install_nemoclaw_skills.sh",
    REPO_ROOT / "scripts" / "sync_openclaw_workspace.sh",
    REPO_ROOT / "scripts" / "stop_nemoclaw_dashboard.sh",
    REPO_ROOT / "scripts" / "forward_nemoclaw_dashboard.sh",
    REPO_ROOT / "scripts" / "start_tool_gateway.sh",
    REPO_ROOT / "scripts" / "start_agent_telegram_ops.sh",
    REPO_ROOT / "scripts" / "install_solopreneur_openclaw_plugin.sh",
    REPO_ROOT / "scripts" / "onboard_solopreneur_openclaw_sandbox.sh",
]
ATOMIC_OPENCLAW_TOOLS = [
    "crm_lookup",
    "business_card_capture",
    "deal_prepare",
    "odoo_upsert_contact",
    "odoo_create_crm_lead",
    "odoo_create_sale_order",
    "odoo_create_draft_invoice",
    "odoo_create_deal_artifacts",
    "delivery_create_tasks",
    "notify_stakeholder",
]
PRIVATE_ALLOWED_IPS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "fc00::/7",
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
        "live_workflow_enabled=1",
        "selected tool argument `live=true`",
        "use linear for engineering execution",
    ]
    for rule in required_rules:
        assert rule in skill_text


def test_skill_documents_openclaw_tool_boundary_without_prompting_for_shell_tools():
    skill_text = read_text(REPO_ROOT / "skills" / "deal-to-delivery" / "SKILL.md").lower()
    sop_text = read_text(REPO_ROOT / "skills" / "deal-to-delivery" / "sop.md").lower()
    combined = "\n".join([skill_text, sop_text])

    required_phrases = [
        "skills are instructions, not tool registration",
        "first-class openclaw tool",
        "compact tool-catalog mode",
        'openclaw.tools.search("crm_lookup")',
        'openclaw.tools.call("crm_lookup"',
        "normal operator prompts should not name tool apis",
        "do not guess missing shell tools",
        "telegram ops bot",
        "operator fallback",
        "business_card_capture",
        "crm_lookup",
        "deal_prepare",
        "odoo_upsert_contact",
        "odoo_create_crm_lead",
        "odoo_create_sale_order",
        "odoo_create_draft_invoice",
        "odoo_create_deal_artifacts",
        "delivery_create_tasks",
        "notify_stakeholder",
        '"live": true',
        '"live": false',
        '"run_id"',
        '"message"',
    ]
    for phrase in required_phrases:
        assert phrase in combined

    forbidden_prompt_fragments = [
        "use the bash tool",
        'tool_search query:"bash"',
        'tool_call name:"bash"',
        "do not call read",
        "do not call exec",
        "do not call fetch",
        "python urllib fallback",
        "deal_to_delivery_run",
    ]
    for phrase in forbidden_prompt_fragments:
        assert phrase not in combined


def test_solopreneur_openclaw_plugin_declares_atomic_tools_only():
    plugin_root = REPO_ROOT / "openclaw_plugins" / "solopreneur-tools"
    manifest = json.loads(read_text(plugin_root / "openclaw.plugin.json"))
    package = json.loads(read_text(plugin_root / "package.json"))
    runtime = read_text(plugin_root / "dist" / "index.js")

    assert manifest["id"] == "solopreneur-tools"
    assert manifest["contracts"]["tools"] == ATOMIC_OPENCLAW_TOOLS
    assert manifest["configSchema"]["properties"]["gatewayBaseUrl"]["default"] == (
        "http://host.openshell.internal:8088"
    )
    assert package["type"] == "module"
    assert package["openclaw"]["extensions"] == ["./dist/index.js"]

    for tool_name in ATOMIC_OPENCLAW_TOOLS:
        assert f'name: "{tool_name}"' in runtime

    assert "Keep false for preparation" not in runtime
    assert "operator approved full live workflow" in runtime
    assert "deal_to_delivery_run" not in json.dumps(manifest)
    assert "deal_to_delivery_run" not in runtime
    assert "/tools/deal-to-delivery/run" not in runtime


def test_solopreneur_openclaw_plugin_runtime_is_not_ignored():
    gitignore = read_text(REPO_ROOT / ".gitignore")

    assert "!openclaw_plugins/solopreneur-tools/dist/" in gitignore
    assert "!openclaw_plugins/solopreneur-tools/dist/index.js" in gitignore


def test_solopreneur_openclaw_plugin_routes_to_atomic_gateway_endpoints():
    runtime = read_text(REPO_ROOT / "openclaw_plugins" / "solopreneur-tools" / "dist" / "index.js")

    expected_routes = [
        "/tools/crm/lookup",
        "/tools/crm/business-card",
        "/tools/deal/prepare",
        "/tools/odoo/contact",
        "/tools/odoo/crm-lead",
        "/tools/odoo/sale-order",
        "/tools/odoo/draft-invoice",
        "/tools/odoo/deal-artifacts",
        "/tools/delivery/tasks",
        "/tools/notify/stakeholder",
    ]
    for route in expected_routes:
        assert route in runtime

    assert "host.openshell.internal:8088" in runtime


def test_tool_gateway_policy_allows_documented_http_clients():
    preset = load_preset(REPO_ROOT / "presets" / "tool-gateway-local.yaml")
    binaries = {
        item["path"]
        for item in preset["network_policies"]["tool_gateway_local"]["binaries"]
    }

    assert "/usr/bin/curl" in binaries
    assert "/usr/local/bin/node" in binaries
    assert "/usr/bin/node" in binaries
    assert "/usr/bin/python3" in binaries


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
    workspace_script = read_text(REPO_ROOT / "scripts" / "sync_openclaw_workspace.sh")

    assert 'nemoclaw sandbox policy add "$SANDBOX" --from-dir ./presets --yes' in policy_script
    assert 'nemoclaw sandbox skill install "$SANDBOX" ./skills/deal-to-delivery' in skill_script
    assert 'WORKSPACE_ROOT="${WORKSPACE_ROOT:-workspace}"' in workspace_script
    assert 'WORKSPACE_TARGET="${WORKSPACE_TARGET:-/sandbox/.openclaw/workspace}"' in workspace_script
    assert 'install_workspace_file "AGENTS.md"' in workspace_script
    assert 'install_workspace_file "IDENTITY.md"' in workspace_script
    assert 'install_workspace_file "SOUL.md"' in workspace_script
    assert 'install_workspace_file "TOOLS.md"' in workspace_script
    assert 'install_workspace_file "USER.md"' in workspace_script
    assert 'install_workspace_file "MEMORY.md"' in workspace_script
    assert 'openssl base64 -A -in "$source_path" | nemoclaw "$SANDBOX" exec -- node -e' in workspace_script
    assert "process.stdin.on(\"data\"" in workspace_script
    assert 'Buffer.from(b64, "base64")' in workspace_script
    assert '"$encoded"' not in workspace_script


def test_solopreneur_plugin_install_makes_openclaw_sdk_resolvable():
    script = read_text(REPO_ROOT / "scripts" / "install_solopreneur_openclaw_plugin.sh")
    dockerfile = read_text(REPO_ROOT / "Dockerfile.nemoclaw-solopreneur")

    assert "$PLUGIN_TARGET/node_modules/openclaw" in script
    assert "ln -s /usr/local/lib/node_modules/openclaw" in script
    assert 'openclaw plugins install "$PLUGIN_TARGET" --force' in script
    assert "openclaw plugins enable solopreneur-tools" in script
    assert "openclaw plugins inspect solopreneur-tools --runtime --json" in script
    assert "/sandbox/.openclaw/extensions/solopreneur-tools/node_modules/openclaw" in dockerfile
    assert "ln -s /usr/local/lib/node_modules/openclaw" in dockerfile
    assert "openclaw plugins install /opt/solopreneur-tools --force" in dockerfile
    assert "openclaw plugins enable solopreneur-tools" in dockerfile
    assert "openclaw plugins inspect solopreneur-tools --runtime --json" in dockerfile


def test_dashboard_forward_script_uses_service_forward_for_local_port():
    script = read_text(REPO_ROOT / "scripts" / "forward_nemoclaw_dashboard.sh")

    assert 'SANDBOX="${SANDBOX:-deal-demo}"' in script
    assert 'TARGET_DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"' in script
    assert 'LOCAL_DASHBOARD_PORT="${LOCAL_DASHBOARD_PORT:-18789}"' in script
    assert 'openshell forward service' in script
    assert '--target-port "$TARGET_DASHBOARD_PORT"' in script
    assert '--local "$LOCAL_BIND:$LOCAL_DASHBOARD_PORT"' in script
    assert 'LOCAL_DASHBOARD_PORT=18790 make nemoclaw-dashboard' in script
    assert 'make nemoclaw-dashboard-restart' in script
    assert '"$SANDBOX"' in script


def test_dashboard_stop_script_only_stops_known_forward_processes():
    script = read_text(REPO_ROOT / "scripts" / "stop_nemoclaw_dashboard.sh")

    assert 'LOCAL_DASHBOARD_PORT="${LOCAL_DASHBOARD_PORT:-18789}"' in script
    assert 'lsof -nP -iTCP:"$LOCAL_DASHBOARD_PORT" -sTCP:LISTEN -t' in script
    assert 'command_name="$(lsof -nP -a -p "$pid" -iTCP:"$LOCAL_DASHBOARD_PORT" -sTCP:LISTEN -Fc' in script
    assert '"$command_name" == "openshell"' in script
    assert '"$command_name" == "ssh"' in script
    assert '127.0.0.1:$LOCAL_DASHBOARD_PORT' in script
    assert 'kill "$pid"' in script
    assert 'Refusing to stop PID' in script


def test_makefile_has_explicit_fresh_recreate_sandbox_target():
    makefile = read_text(REPO_ROOT / "Makefile")

    assert "nemoclaw-solopreneur-sandbox-recreate" in makefile
    assert "bash scripts/onboard_solopreneur_openclaw_sandbox.sh --fresh --recreate-sandbox" in makefile


def test_makefile_has_explicit_destroy_sandbox_targets():
    makefile = read_text(REPO_ROOT / "Makefile")

    assert "SANDBOX ?= deal-demo" in makefile
    assert "nemoclaw-solopreneur-sandbox-destroy" in makefile
    assert "nemoclaw-solopreneur-sandbox-destroy-clean" in makefile
    assert "bash scripts/stop_nemoclaw_dashboard.sh" in makefile
    assert "nemoclaw $(SANDBOX) destroy --yes\n" in makefile
    assert "nemoclaw $(SANDBOX) destroy --yes --cleanup-gateway" in makefile


def test_makefile_can_install_solopreneur_plugin_into_existing_sandbox():
    makefile = read_text(REPO_ROOT / "Makefile")

    assert "nemoclaw-solopreneur-plugin-install" in makefile
    assert 'SANDBOX="$(SANDBOX)" bash scripts/install_solopreneur_openclaw_plugin.sh' in makefile
    assert 'SANDBOX="$(SANDBOX)" bash scripts/sync_openclaw_workspace.sh' in makefile
    assert 'nemoclaw "$(SANDBOX)" exec -- openclaw plugins validate --root /sandbox/.openclaw/extensions/solopreneur-tools --entry dist/index.js' in makefile
    assert 'nemoclaw "$(SANDBOX)" exec -- openclaw plugins registry --refresh' in makefile
    assert 'nemoclaw "$(SANDBOX)" recover' in makefile


def test_solopreneur_openclaw_sandbox_onboard_assets_are_present():
    dockerfile = read_text(REPO_ROOT / "Dockerfile.nemoclaw-solopreneur")
    script = read_text(REPO_ROOT / "scripts" / "onboard_solopreneur_openclaw_sandbox.sh")

    assert "COPY openclaw_plugins/solopreneur-tools/" in dockerfile
    assert "/sandbox/.openclaw/extensions/solopreneur-tools" in dockerfile
    assert "chown -R sandbox:sandbox /sandbox/.openclaw/extensions/solopreneur-tools" in dockerfile
    assert "openclaw plugins install /opt/solopreneur-tools --force" in dockerfile
    assert "openclaw plugins enable solopreneur-tools" in dockerfile
    assert "openclaw plugins validate" not in dockerfile
    assert "openclaw doctor --fix --non-interactive" in dockerfile
    assert "openclaw config" not in dockerfile
    assert "openclaw models" not in dockerfile
    assert "/sandbox/.openclaw/openclaw.json || rm" not in dockerfile
    assert "/sandbox/.openclaw/.config-hash || rm" not in dockerfile
    assert 'SANDBOX="${SANDBOX:-deal-demo}"' in script
    assert 'DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"' in script
    assert 'PLUGIN_ROOT="${PLUGIN_ROOT:-openclaw_plugins/solopreneur-tools}"' in script
    assert 'USE_CUSTOM_IMAGE="${USE_CUSTOM_IMAGE:-1}"' in script
    assert 'if [[ "$USE_CUSTOM_IMAGE" == "1" ]]' in script
    assert 'nemoclaw onboard --from "$DOCKERFILE" --name "$SANDBOX" "$@"' in script
    assert 'nemoclaw onboard --name "$SANDBOX" "$@"' in script
    assert 'bash scripts/install_solopreneur_openclaw_plugin.sh' in script
    assert "exec -- sh -lc '\n" not in script
    assert 'openclaw doctor --fix --yes --non-interactive' not in script
    assert "NemoClaw owns inference routing" in script
    assert "openclaw models set" not in script
    assert "models\",\"auth\",\"paste-api-key" not in script
    assert 'gateway.mode' in script
    assert 'SANDBOX="$SANDBOX" bash scripts/sync_openclaw_workspace.sh' in script
    assert "openclaw plugins validate --root /sandbox/.openclaw/extensions/solopreneur-tools" in script
    assert "openclaw plugins registry --refresh" in script
    assert 'nemoclaw "$SANDBOX" recover' in script


def test_solopreneur_plugin_install_script_uses_stdin_not_newline_arguments():
    script = read_text(REPO_ROOT / "scripts" / "install_solopreneur_openclaw_plugin.sh")

    assert 'PLUGIN_ROOT="${PLUGIN_ROOT:-openclaw_plugins/solopreneur-tools}"' in script
    assert 'PLUGIN_TARGET="${PLUGIN_TARGET:-/sandbox/.openclaw/extensions/solopreneur-tools}"' in script
    assert 'install_plugin_file()' in script
    assert 'openssl base64 -A -in "$source_path" | nemoclaw "$SANDBOX" exec -- node -e' in script
    assert "process.stdin.on(\"data\"" in script
    assert 'Buffer.from(b64, "base64")' in script
    assert '"$encoded"' not in script
    assert "exec -- sh -lc '\n" not in script
    assert 'install_plugin_file "$PLUGIN_ROOT/package.json"' in script
    assert 'install_plugin_file "$PLUGIN_ROOT/openclaw.plugin.json"' in script
    assert 'install_plugin_file "$PLUGIN_ROOT/dist/index.js"' in script
