#!/usr/bin/env python3
"""PreToolUse hook for Edit, MultiEdit and Write. Exit 2 blocks the call and shows stderr to the agent.

Fails closed: any error exits 2. Claude Code treats exit 1 as non-blocking, so a crash that
exited 1 would silently disable every protection (it did, until TASK-001).

For the mutation floors file (Q-03-T027) it also rebuilds the file as the call would leave it and
refuses a lowered or removed floor.
"""
import json
import os
import sys


def after(path, tool_input):
    """The file's text once the Write, Edit or MultiEdit has applied."""
    if "content" in tool_input:
        return tool_input.get("content") or ""
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    edits = tool_input.get("edits")
    if not isinstance(edits, list):
        edits = [tool_input]
    for edit in edits:
        old, new = edit.get("old_string") or "", edit.get("new_string") or ""
        if not old:
            text = new if not text else text
            continue
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


try:
    sys.path.insert(0, os.path.dirname(__file__))
    from _protected import ROOT, floor_violation, violation

    data = json.load(sys.stdin)
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path", "")
    msg = violation(path) if path else None
    if path and not msg:
        absolute = path if os.path.isabs(path) else os.path.join(ROOT, path)
        msg = floor_violation(path, after(absolute, tool_input))
except Exception as exc:  # noqa: BLE001 — fail closed on anything
    print(f"BLOCKED: protected-path hook failed ({type(exc).__name__}: {exc}); fix the hook.", file=sys.stderr)
    sys.exit(2)
if msg:
    print(f"BLOCKED: {msg} (ADR-086, protected-paths.md)", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
