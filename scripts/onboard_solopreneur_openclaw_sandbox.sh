#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.nemoclaw-solopreneur}"
DASHBOARD_PORT="${TARGET_DASHBOARD_PORT:-18789}"
PLUGIN_ROOT="${PLUGIN_ROOT:-openclaw_plugins/solopreneur-tools}"
USE_CUSTOM_IMAGE="${USE_CUSTOM_IMAGE:-1}"

assert_gateway_config_present() {
  if ! nemoclaw "$SANDBOX" exec -- node -e 'const fs=require("fs"); const p="/sandbox/.openclaw/openclaw.json"; const cfg=JSON.parse(fs.readFileSync(p,"utf8")); if (cfg.gateway && cfg.gateway.mode) process.exit(0); process.exit(1);'; then
    echo "OpenClaw config is missing gateway.mode inside sandbox '$SANDBOX'." >&2
    echo "This usually means the sandbox reused a config that was modified by an in-sandbox OpenClaw config command." >&2
    echo "Recreate the sandbox and choose 'n' when NemoClaw asks whether to reuse the existing sandbox." >&2
    exit 1
  fi
}

if [[ "$USE_CUSTOM_IMAGE" == "1" ]]; then
  echo "Using custom NemoClaw sandbox image with baked solopreneur OpenClaw plugin: $DOCKERFILE"
  nemoclaw onboard --from "$DOCKERFILE" --name "$SANDBOX" "$@"
else
  echo "Using NemoClaw default sandbox image, then installing the solopreneur OpenClaw plugin."
  echo "This fallback is for local debugging only; the supported NemoClaw plugin path is the custom image."
  nemoclaw onboard --name "$SANDBOX" "$@"
  SANDBOX="$SANDBOX" PLUGIN_ROOT="$PLUGIN_ROOT" bash scripts/install_solopreneur_openclaw_plugin.sh
fi

# NemoClaw owns inference routing and provider credentials for managed sandboxes.
# Do not run in-sandbox model mutation or provider auth commands here:
# they can rewrite /sandbox/.openclaw/openclaw.json and drop gateway.mode.
assert_gateway_config_present
SANDBOX="$SANDBOX" bash scripts/sync_openclaw_workspace.sh
nemoclaw "$SANDBOX" exec -- openclaw plugins validate --root /sandbox/.openclaw/extensions/solopreneur-tools --entry dist/index.js
nemoclaw "$SANDBOX" exec -- openclaw plugins registry --refresh
nemoclaw "$SANDBOX" recover
