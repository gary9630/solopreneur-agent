#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.nemoclaw-solopreneur}"
DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"
OPENCLAW_DEFAULT_MODEL="${OPENCLAW_DEFAULT_MODEL:-nvidia/nemotron-3-super-120b-a12b}"
PLUGIN_ROOT="${PLUGIN_ROOT:-openclaw_plugins/solopreneur-tools}"
USE_CUSTOM_IMAGE="${USE_CUSTOM_IMAGE:-0}"

if [[ "$USE_CUSTOM_IMAGE" == "1" ]]; then
  echo "Using experimental custom sandbox image: $DOCKERFILE"
  echo "For hackathon demos, prefer the default NemoClaw image path unless you have verified the image keeps NemoClaw preloads."
  nemoclaw onboard --from "$DOCKERFILE" --name "$SANDBOX" "$@"
else
  echo "Using NemoClaw default sandbox image, then installing the solopreneur OpenClaw plugin."
  nemoclaw onboard --name "$SANDBOX" "$@"
fi

if [[ ! -f "$PLUGIN_ROOT/openclaw.plugin.json" || ! -f "$PLUGIN_ROOT/dist/index.js" ]]; then
  echo "Missing solopreneur plugin files under $PLUGIN_ROOT" >&2
  exit 1
fi

tar -C "$PLUGIN_ROOT" -cf - . | nemoclaw "$SANDBOX" exec -- sh -lc '
set -e
install -d -m 2770 /sandbox/.openclaw/extensions/solopreneur-tools
tar -C /sandbox/.openclaw/extensions/solopreneur-tools -xf -
chmod -R u+rwX,g+rwX,o-rwx /sandbox/.openclaw/extensions/solopreneur-tools
'

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
