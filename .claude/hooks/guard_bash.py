#!/usr/bin/env python3
"""PreToolUse hook for Bash. Best-effort local guard; server-side protections are authoritative.

A shell can always find another way to write a file; this catches the common ones. CODEOWNERS
and branch protection are the real control. Fails closed: any error exits 2.
"""
import json
import os
import re
import sys

RULES = [
    (r"git\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease|\s\+\S)", "Force pushes are forbidden."),
    (r"git\s+push\b.*\b(main|master)\b", "Never push directly to main. Open a pull request."),
    (r"git\s+commit\b.*(--no-verify|\s-n\b)", "Skipping hooks is forbidden."),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\.|\*)(\s|$)", "Recursive deletion of root, home or the project is forbidden."),
    (r"\bsudo\b", "sudo is not allowed."),
    (r"\bchmod\s+777\b", "World-writable permissions are not allowed."),
    (r"\bterraform\s+(apply|destroy|import|state)\b", "Infrastructure changes go through CI only (ADR-021)."),
    (r"\b(psql|pg_dump|pg_restore)\b(?!.*(localhost|127\.0\.0\.1|@db\b|host=db))", "Database tools may only target local databases (ADR-087)."),
    (r"\baws\b.*--profile\s+\S*prod", "No agent access to production accounts (ADR-028)."),
    (r"(api\.anthropic\.com|api\.openai\.com)", "Model providers are reached only through ai_gateway (ADR-019)."),
    (r"\b(uv\s+add|uv\s+pip\s+install|pip3?\s+install|pnpm\s+add|npm\s+(install|i)\s+\S|yarn\s+add)\b", "New dependencies need approval and an allowlist entry."),
    (r"\balembic\s+downgrade\b.*(prod|staging)", "Downgrades run only locally."),
]

# Anything that can write a file. Redirection ignores `->` and `=>` (arrows in messages).
WRITERS = re.compile(
    r"((?<![-=])>>?|\bsed\s+-i\b|\btee\b|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bln\b|\binstall\b"
    r"|\bdd\b|\brsync\b|\bpatch\b|\btar\b|\bunzip\b|\bchmod\b"
    r"|\bpython[0-9.]*\b|\bperl\b|\bruby\b|\bnode\b|\bdeno\b|\bbun\b"
    r"|\bgit\s+(apply|checkout|restore|am|stash|reset|mv|rm)\b)",
    re.IGNORECASE,
)


def stems(patterns):
    """Literal path fragments of each pattern: `x/**` -> `x`, `**/Makefile` -> `Makefile`."""
    out = set()
    for pat in patterns:
        literal = pat[3:] if pat.startswith("**/") else pat
        stem = literal.split("*")[0].rstrip("/")
        if stem:
            out.add(stem)
    return sorted(out)


def check(cmd):
    from _protected import PROTECTED, PROTECTED_IF_EXISTS

    for pattern, reason in RULES:
        if re.search(pattern, cmd):
            return reason
    if WRITERS.search(cmd):
        for stem in stems(PROTECTED + PROTECTED_IF_EXISTS):
            if re.search(r"(?<![\w.-])" + re.escape(stem) + r"(?![\w-])", cmd, re.IGNORECASE):
                return f"shell write touching protected path '{stem}'. Use the Edit tool with an approval file."
    return None


try:
    sys.path.insert(0, os.path.dirname(__file__))
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
    reason = check(cmd)
except Exception as exc:  # noqa: BLE001 — fail closed on anything
    print(f"BLOCKED: bash guard hook failed ({type(exc).__name__}: {exc}); fix the hook.", file=sys.stderr)
    sys.exit(2)
if reason:
    print(f"BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
