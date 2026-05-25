import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from deal_agent.demo_cli import build_demo_summary, main, run_demo_from_text
from deal_agent.models import WorkflowState


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_INPUT_PATH = REPO_ROOT / "demo" / "customer_inputs" / "01_initial_request.txt"
EXPECTED_SUMMARY_PATH = REPO_ROOT / "demo" / "expected_outputs" / "happy_path_summary.json"

DEMO_MESSAGE = """
ACME needs a two-week Odoo automation prototype for its sales operations team.
They want the agent to capture the customer brief, draft a quote, create delivery
tracking in Linear and GitHub, and notify the founder in Telegram.
""".strip()


def test_run_demo_from_text_completes_with_fake_integrations():
    run = run_demo_from_text(DEMO_MESSAGE)

    assert run.state is WorkflowState.COMPLETED
    assert run.run_id == f"demo_{hashlib.sha256(DEMO_MESSAGE.encode('utf-8')).hexdigest()[:12]}"
    assert run.brief.message == DEMO_MESSAGE

    systems = {ref.system for ref in run.external_refs}
    assert {"odoo", "linear", "github", "telegram"}.issubset(systems)

    assert any(ref.system == "odoo" and ref.metadata["kind"] == "lead" for ref in run.external_refs)
    assert any(ref.system == "linear" and ref.metadata["kind"] == "project" for ref in run.external_refs)
    assert any(
        ref.system == "github" and ref.metadata["kind"] == "delivery_issue"
        for ref in run.external_refs
    )
    assert any(ref.system == "telegram" and ref.metadata["kind"] == "message" for ref in run.external_refs)


def test_run_demo_from_text_is_deterministic_for_demo_refs():
    first = run_demo_from_text(DEMO_MESSAGE)
    second = run_demo_from_text(DEMO_MESSAGE)

    assert first.run_id == second.run_id
    assert [ref.model_dump(mode="json") for ref in first.external_refs] == [
        ref.model_dump(mode="json") for ref in second.external_refs
    ]


def test_build_demo_summary_is_compact_and_serializable():
    run = run_demo_from_text(DEMO_MESSAGE)

    summary = build_demo_summary(run)

    assert summary == {
        "run_id": run.run_id,
        "state": "COMPLETED",
        "customer_name": "ACME",
        "quote": {"currency": "USD", "total": "4500"},
        "systems": ["github", "linear", "odoo", "telegram"],
        "external_ref_count": len(run.external_refs),
        "step_count": len(run.steps),
    }
    assert json.loads(json.dumps(summary, separators=(",", ":"))) == summary


def test_main_reads_utf8_file_and_prints_compact_json(tmp_path, capsys):
    input_path = tmp_path / "brief.txt"
    input_path.write_text(DEMO_MESSAGE, encoding="utf-8")

    exit_code = main([str(input_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "\n" not in output.rstrip("\n")
    body = json.loads(output)
    assert body["state"] == "COMPLETED"
    assert {"github", "linear", "odoo", "telegram"} == set(body["systems"])


def test_main_rejects_blank_input_file(tmp_path):
    input_path = tmp_path / "blank.txt"
    input_path.write_text(" \n\t", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main([str(input_path)])

    assert exc_info.value.code == 2


def test_seed_input_replays_expected_summary():
    message = SEED_INPUT_PATH.read_text(encoding="utf-8")
    expected_summary = json.loads(EXPECTED_SUMMARY_PATH.read_text(encoding="utf-8"))

    summary = build_demo_summary(run_demo_from_text(message))

    assert summary == expected_summary


def test_console_script_is_registered():
    pyproject_path = REPO_ROOT / "agent_app" / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["deal-agent-demo"] == "deal_agent.demo_cli:main"
