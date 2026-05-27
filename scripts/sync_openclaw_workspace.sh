#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-workspace}"
WORKSPACE_TARGET="${WORKSPACE_TARGET:-/sandbox/.openclaw/workspace}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw is required. Run ./scripts/setup_nemoclaw.sh first." >&2
  exit 1
fi

if [[ ! -d "$WORKSPACE_ROOT" ]]; then
  echo "Missing workspace directory: $WORKSPACE_ROOT" >&2
  exit 1
fi

install_workspace_file() {
  local filename="$1"
  local source_path="$WORKSPACE_ROOT/$filename"
  local sandbox_path="$WORKSPACE_TARGET/$filename"

  if [[ ! -f "$source_path" ]]; then
    echo "Missing workspace file: $source_path" >&2
    exit 1
  fi

  openssl base64 -A -in "$source_path" | nemoclaw "$SANDBOX" exec -- node -e 'const fs=require("fs"); const path=require("path"); const dest=process.argv[1]; const chunks=[]; process.stdin.on("data", c => chunks.push(c)); process.stdin.on("end", () => { const b64=Buffer.concat(chunks).toString("utf8"); fs.mkdirSync(path.dirname(dest), {recursive:true}); fs.writeFileSync(dest, Buffer.from(b64, "base64")); });' "$sandbox_path"
}

nemoclaw "$SANDBOX" exec -- sh -lc "install -d -m 2770 '$WORKSPACE_TARGET'"

install_workspace_file "AGENTS.md"
install_workspace_file "IDENTITY.md"
install_workspace_file "SOUL.md"
install_workspace_file "TOOLS.md"
install_workspace_file "USER.md"
install_workspace_file "MEMORY.md"

nemoclaw "$SANDBOX" exec -- sh -lc "chmod u+rwX,g+rwX,o-rwx '$WORKSPACE_TARGET'/*.md"

echo "Synced OpenClaw workspace files into $SANDBOX:$WORKSPACE_TARGET"
