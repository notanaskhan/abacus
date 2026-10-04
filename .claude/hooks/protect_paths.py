#!/usr/bin/env python3
"""PreToolUse hook for Edit, MultiEdit and Write. Exit 2 blocks the call and shows stderr to the agent."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _protected import violation

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)
path = (data.get("tool_input") or {}).get("file_path", "")
if not path:
    sys.exit(0)
msg = violation(path)
if msg:
    print(f"BLOCKED: {msg} (ADR-086, protected-paths.md)", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
