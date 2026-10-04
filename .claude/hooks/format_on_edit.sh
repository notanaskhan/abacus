#!/usr/bin/env bash
# PostToolUse: format the edited file and surface lint errors so the agent fixes them immediately.
# Skips quietly until the relevant toolchain and directories exist.
set -u
input=$(cat)
file=$(printf '%s' "$input" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("tool_input") or {}).get("file_path",""))' 2>/dev/null)
[ -z "$file" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
case "$file" in
  *.py)
    { [ -d backend ] && [ -f backend/pyproject.toml ] && command -v uv >/dev/null 2>&1; } || exit 0
    (cd backend && uv run ruff format "$file" >/dev/null 2>&1)
    out=$(cd backend && uv run ruff check "$file" 2>&1) || { echo "$out" >&2; exit 2; } ;;
  *.ts|*.tsx)
    { [ -d apps/web ] && [ -f apps/web/package.json ] && command -v pnpm >/dev/null 2>&1; } || exit 0
    pnpm -C apps/web exec prettier --write "$file" >/dev/null 2>&1
    out=$(pnpm -C apps/web exec eslint "$file" 2>&1) || { echo "$out" >&2; exit 2; } ;;
esac
exit 0
