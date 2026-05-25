#!/usr/bin/env bash
set -euo pipefail

SANDBOX="${SANDBOX:-deal-demo}"
NEMOCLAW_INSTALL_URL="${NEMOCLAW_INSTALL_URL:-}"
NVIDIA_API_KEY="${NVIDIA_API_KEY:-}"

if command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw is already available."
  nemoclaw --version || true
else
  echo "nemoclaw was not found on PATH."
  if [ -n "$NEMOCLAW_INSTALL_URL" ]; then
    echo "Installer URL is configured, but this offline-friendly setup script will not run network installers by default."
    echo "To install intentionally, inspect the installer first, then run it manually from: $NEMOCLAW_INSTALL_URL"
  else
    echo "Set NEMOCLAW_INSTALL_URL to the reviewed NemoClaw installer URL, or install NemoClaw from the local reference checkout."
  fi
fi

if [ -z "$NVIDIA_API_KEY" ]; then
  echo "NVIDIA_API_KEY is not set. Export it in your shell for live NIM Serverless Inference calls."
else
  echo "NVIDIA_API_KEY is set in the environment."
fi

echo "Sandbox name: $SANDBOX"
echo "Next: ./scripts/apply_nemoclaw_policies.sh"
echo "Then: ./scripts/install_nemoclaw_skills.sh"
