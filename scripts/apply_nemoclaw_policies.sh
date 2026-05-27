#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw is required. Run ./scripts/setup_nemoclaw.sh first." >&2
  exit 1
fi

nemoclaw sandbox policy add "$SANDBOX" --from-dir ./presets --yes
