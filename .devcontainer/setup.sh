#!/usr/bin/env bash
# .devcontainer/setup.sh
# Runs once after the container is created (postCreateCommand).
# Sets up all tooling needed for GHARTS development and Claude Code autonomous runs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing uv (fast Python package manager)"
curl -LsSf https://astral.sh/uv/install.sh | sh
# Make uv available in the current shell
export PATH="$HOME/.local/bin:$PATH"

echo "==> Installing Python dependencies"
cd "$REPO_ROOT"
uv pip install --system -r requirements-dev.txt

echo "==> Installing frontend dependencies"
cd "$REPO_ROOT/frontend"
npm ci

echo "==> Installing Claude Code"
npm install -g @anthropic-ai/claude-code

echo "==> Installing pre-commit hooks"
cd "$REPO_ROOT"
pre-commit install

echo "==> Configuring Claude Code for autonomous operation"
# Write a project-scoped settings.json that pre-approves routine operations
# so Claude does not prompt for permission on every tool call inside the Codespace.
# This is safe because the Codespace is an isolated sandbox — it cannot affect
# anything outside the container.
CLAUDE_SETTINGS_DIR="$REPO_ROOT/.claude"
mkdir -p "$CLAUDE_SETTINGS_DIR"

cat > "$CLAUDE_SETTINGS_DIR/settings.json" << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(python *)",
      "Bash(pytest *)",
      "Bash(uv *)",
      "Bash(pip *)",
      "Bash(npm *)",
      "Bash(npx *)",
      "Bash(ruff *)",
      "Bash(pre-commit *)",
      "Bash(terraform *)",
      "Bash(alembic *)",
      "Bash(ls *)",
      "Bash(cat *)",
      "Bash(find *)",
      "Bash(grep *)",
      "Bash(mkdir *)",
      "Bash(cp *)",
      "Bash(mv *)",
      "Bash(rm *)",
      "Bash(touch *)",
      "Bash(echo *)",
      "Bash(sed *)",
      "Bash(awk *)",
      "Bash(curl *)",
      "Bash(jq *)",
      "Bash(docker *)",
      "Bash(docker-compose *)"
    ],
    "deny": []
  }
}
EOF

echo "==> Configuring GitHub MCP server"
# The MCP server is configured using the GITHUB_TOKEN that Codespaces injects
# automatically. No PAT is needed for read/write access to this repo.
claude mcp add github \
  -e GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN:-}" \
  -- npx -y @modelcontextprotocol/server-github 2>/dev/null || \
  echo "  Note: MCP server config will be applied when GITHUB_TOKEN is available."

echo ""
echo "==> Setup complete."
echo "    Claude Code: $(claude --version 2>/dev/null || echo 'installed, authenticate with: claude login')"
echo "    Python:      $(python --version)"
echo "    Node:        $(node --version)"
echo "    Terraform:   $(terraform version -json 2>/dev/null | python -c 'import json,sys; print(json.load(sys.stdin)[\"terraform_version\"])' 2>/dev/null || terraform version | head -1)"
echo ""
echo "    Next: run 'claude' to authenticate with your Anthropic account."
