#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../agent_app"

exec uv run uvicorn deal_agent.main:app --host 0.0.0.0 --port 8088
