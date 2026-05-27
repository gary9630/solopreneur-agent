#!/usr/bin/env bash
set -euo pipefail

LOCAL_DASHBOARD_PORT="${LOCAL_DASHBOARD_PORT:-18789}"
LOCAL_BIND="${LOCAL_BIND:-127.0.0.1}"

if ! command -v lsof >/dev/null 2>&1; then
  echo "lsof is required to find the dashboard forward process." >&2
  exit 1
fi

pids="$(lsof -nP -iTCP:"$LOCAL_DASHBOARD_PORT" -sTCP:LISTEN -t 2>/dev/null || true)"

if [[ -z "$pids" ]]; then
  echo "No dashboard forward is listening on $LOCAL_BIND:$LOCAL_DASHBOARD_PORT."
  exit 0
fi

for pid in $pids; do
  command_name="$(lsof -nP -a -p "$pid" -iTCP:"$LOCAL_DASHBOARD_PORT" -sTCP:LISTEN -Fc 2>/dev/null | sed -n 's/^c//p' | head -n 1)"
  process_command="$(ps -p "$pid" -o command= 2>/dev/null || true)"

  if [[ "$command_name" == "openshell" ]]; then
    echo "Stopping NemoClaw dashboard forward PID $pid ($command_name)."
    kill "$pid"
    continue
  fi

  if [[ "$command_name" == "ssh" && "$process_command" == *"127.0.0.1:$LOCAL_DASHBOARD_PORT"* ]]; then
    echo "Stopping NemoClaw dashboard SSH forward PID $pid."
    kill "$pid"
    continue
  fi

  if [[ "$command_name" == "ssh" && "$process_command" == *"localhost:$LOCAL_DASHBOARD_PORT"* ]]; then
    echo "Stopping NemoClaw dashboard SSH forward PID $pid."
    kill "$pid"
    continue
  fi

  echo "Refusing to stop PID $pid ($command_name)." >&2
  echo "It is listening on $LOCAL_BIND:$LOCAL_DASHBOARD_PORT but does not look like a NemoClaw dashboard forward." >&2
  echo "Stop it manually or use LOCAL_DASHBOARD_PORT=<free-port> make nemoclaw-dashboard." >&2
  exit 1
done
