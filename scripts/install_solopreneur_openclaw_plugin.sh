#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
PLUGIN_ROOT="${PLUGIN_ROOT:-openclaw_plugins/solopreneur-tools}"
PLUGIN_TARGET="${PLUGIN_TARGET:-/sandbox/.openclaw/extensions/solopreneur-tools}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f "$PLUGIN_ROOT/package.json" || ! -f "$PLUGIN_ROOT/openclaw.plugin.json" || ! -f "$PLUGIN_ROOT/dist/index.js" ]]; then
  echo "Missing solopreneur plugin files under $PLUGIN_ROOT" >&2
  exit 1
fi

install_plugin_file() {
  local source_path="$1"
  local sandbox_path="$2"

  openssl base64 -A -in "$source_path" | nemoclaw "$SANDBOX" exec -- node -e 'const fs=require("fs"); const path=require("path"); const dest=process.argv[1]; const chunks=[]; process.stdin.on("data", c => chunks.push(c)); process.stdin.on("end", () => { const b64=Buffer.concat(chunks).toString("utf8"); fs.mkdirSync(path.dirname(dest), {recursive:true}); fs.writeFileSync(dest, Buffer.from(b64, "base64")); });' "$sandbox_path"
}

nemoclaw "$SANDBOX" exec -- sh -lc "install -d -m 2770 '$PLUGIN_TARGET' && install -d -m 2770 '$PLUGIN_TARGET/dist'"

install_plugin_file "$PLUGIN_ROOT/package.json" "$PLUGIN_TARGET/package.json"
install_plugin_file "$PLUGIN_ROOT/openclaw.plugin.json" "$PLUGIN_TARGET/openclaw.plugin.json"
install_plugin_file "$PLUGIN_ROOT/dist/index.js" "$PLUGIN_TARGET/dist/index.js"

nemoclaw "$SANDBOX" exec -- sh -lc "chmod -R u+rwX,g+rwX,o-rwx '$PLUGIN_TARGET' && install -d -m 2770 '$PLUGIN_TARGET/node_modules' && if [ ! -e '$PLUGIN_TARGET/node_modules/openclaw' ] && [ ! -L '$PLUGIN_TARGET/node_modules/openclaw' ]; then ln -s /usr/local/lib/node_modules/openclaw '$PLUGIN_TARGET/node_modules/openclaw'; fi"

nemoclaw "$SANDBOX" exec -- openclaw plugins install "$PLUGIN_TARGET" --force
nemoclaw "$SANDBOX" exec -- openclaw plugins enable solopreneur-tools
nemoclaw "$SANDBOX" exec -- openclaw plugins inspect solopreneur-tools --runtime --json >/dev/null
nemoclaw "$SANDBOX" exec -- openclaw plugins registry --refresh >/dev/null

echo "Installed solopreneur OpenClaw plugin into $SANDBOX:$PLUGIN_TARGET"
