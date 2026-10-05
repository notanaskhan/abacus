#!/usr/bin/env python3
"""PreToolUse hook for Edit, MultiEdit and Write. Exit 2 blocks the call and shows stderr to the agent.

Fails closed: any error exits 2. Claude Code treats exit 1 as non-blocking, so a crash that
exited 1 would silently disable every protection (it did, until TASK-001).
"""
import json
import os
import sys

try:
    sys.path.insert(0, os.path.dirname(__file__))
    from _protected import violation

    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path", "")
    msg = violation(path) if path else None
except Exception as exc:  # noqa: BLE001 — fail closed on anything
    print(f"BLOCKED: protected-path hook failed ({type(exc).__name__}: {exc}); fix the hook.", file=sys.stderr)
    sys.exit(2)
if msg:
    print(f"BLOCKED: {msg} (ADR-086, protected-paths.md)", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
