#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.nemoclaw-solopreneur}"
DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"
OPENCLAW_DEFAULT_MODEL="${OPENCLAW_DEFAULT_MODEL:-nvidia/nemotron-3-super-120b-a12b}"

nemoclaw onboard --from "$DOCKERFILE" --name "$SANDBOX" "$@"

nemoclaw "$SANDBOX" exec -- openclaw config set gateway.mode local
nemoclaw "$SANDBOX" exec -- openclaw config set gateway.bind loopback
nemoclaw "$SANDBOX" exec -- openclaw config set gateway.port "$DASHBOARD_PORT" --strict-json
nemoclaw "$SANDBOX" exec -- openclaw config set gateway.auth.mode token
nemoclaw "$SANDBOX" exec -- node -e 'require("child_process").execFileSync("openclaw",["config","set","gateway.auth.token",require("crypto").randomBytes(32).toString("base64url")],{stdio:"inherit"})'
if [[ -n "${NVIDIA_API_KEY:-}" ]]; then
  nemoclaw "$SANDBOX" exec -- env NVIDIA_API_KEY="$NVIDIA_API_KEY" node -e 'const {spawnSync}=require("child_process"); const key=process.env.NVIDIA_API_KEY||""; if(!key){process.exit(2)} const result=spawnSync("openclaw",["models","auth","paste-api-key","--provider","nvidia","--profile-id","nvidia:manual"],{input:key+"\n",stdio:["pipe","ignore","inherit"]}); process.exit(result.status ?? 1)'
  nemoclaw "$SANDBOX" exec -- openclaw models set "$OPENCLAW_DEFAULT_MODEL"
else
  echo "NVIDIA_API_KEY is not set; skipping OpenClaw NVIDIA auth setup."
fi
nemoclaw "$SANDBOX" exec -- openclaw plugins validate --root /sandbox/.openclaw/extensions/solopreneur-tools --entry dist/index.js
nemoclaw "$SANDBOX" exec -- openclaw plugins registry --refresh
nemoclaw "$SANDBOX" recover
