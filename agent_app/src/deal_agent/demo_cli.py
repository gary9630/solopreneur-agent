from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from deal_agent.connectors import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import WorkflowRun
from deal_agent.runner import DealWorkflowRunner
from deal_agent.services import FakeModelServices


def run_demo_from_text(message: str, *, run_id: str | None = None) -> WorkflowRun:
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("message must not be blank")

    demo_run_id = run_id or _derive_demo_run_id(normalized_message)
    runner = DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )
    return runner.run(demo_run_id, normalized_message)


def build_demo_summary(run: WorkflowRun) -> dict[str, Any]:
    payload = run.model_dump(mode="json")
    quote = payload.get("quote_draft") or {}
    external_refs = payload.get("external_refs", [])
    steps = payload.get("steps", [])
    systems = sorted({ref["system"] for ref in external_refs})

    return {
        "run_id": payload["run_id"],
        "state": payload["state"],
        "customer_name": (payload.get("intake_summary") or {}).get("customer_name"),
        "quote": {
            "currency": quote.get("currency"),
            "total": quote.get("total"),
        },
        "systems": systems,
        "external_ref_count": len(external_refs),
        "step_count": len(steps),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the deterministic deal-agent demo workflow.")
    parser.add_argument("input_file", type=Path, help="UTF-8 customer brief text file")
    args = parser.parse_args(argv)

    message = args.input_file.read_text(encoding="utf-8")
    try:
        run = run_demo_from_text(message)
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(build_demo_summary(run), separators=(",", ":"), sort_keys=True))
    return 0


def _derive_demo_run_id(message: str) -> str:
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]
    return f"demo_{digest}"
