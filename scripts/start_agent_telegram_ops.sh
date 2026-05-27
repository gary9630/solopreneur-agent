#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../agent_app"

exec uv run deal-agent-telegram-ops
