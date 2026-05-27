#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
TARGET_DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"
LOCAL_DASHBOARD_PORT="${LOCAL_DASHBOARD_PORT:-18789}"
LOCAL_BIND="${LOCAL_BIND:-127.0.0.1}"

export PATH="$HOME/.local/bin:$PATH"

if ! command -v openshell >/dev/null 2>&1; then
  echo "openshell is required. Run ./scripts/setup_nemoclaw.sh first." >&2
  exit 1
fi

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw is required. Run ./scripts/setup_nemoclaw.sh first." >&2
  exit 1
fi

echo "Starting NemoClaw dashboard forward for sandbox: $SANDBOX"
echo "Local dashboard base URL: http://$LOCAL_BIND:$LOCAL_DASHBOARD_PORT/"
echo "This process keeps the dashboard connection alive. Leave this terminal open."
echo "In another terminal, get the tokenized dashboard URL with:"
echo "  nemoclaw $SANDBOX dashboard-url"
echo "If $LOCAL_BIND:$LOCAL_DASHBOARD_PORT is already in use, rerun with:"
echo "  LOCAL_DASHBOARD_PORT=18790 make nemoclaw-dashboard"
echo "To replace an existing dashboard forward on this port, run:"
echo "  make nemoclaw-dashboard-restart"
echo

exec openshell forward service \
  --target-port "$TARGET_DASHBOARD_PORT" \
  --local "$LOCAL_BIND:$LOCAL_DASHBOARD_PORT" \
  "$SANDBOX"
