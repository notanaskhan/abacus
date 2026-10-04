#!/usr/bin/env python3
"""PreToolUse hook for Bash. Best-effort local guard; server-side protections are authoritative."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from _protected import PROTECTED, PROTECTED_IF_EXISTS

try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
except json.JSONDecodeError:
    sys.exit(0)

RULES = [
    (r"git\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease)", "Force pushes are forbidden."),
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
for pattern, reason in RULES:
    if re.search(pattern, cmd):
        print(f"BLOCKED: {reason}", file=sys.stderr)
        sys.exit(2)

# Shell writes into protected paths (redirection, sed -i, tee, mv, cp, rm) bypass Edit hooks — block them.
writey = re.search(r"(>>?|\bsed\s+-i\b|\btee\b|\bmv\b|\bcp\b|\brm\b|\btruncate\b)", cmd)
if writey:
    for pat in PROTECTED + PROTECTED_IF_EXISTS:
        stem = pat.split("*")[0].rstrip("/")
        if stem and stem in cmd:
            print(f"BLOCKED: shell write touching protected path '{stem}'. Use the Edit tool with an approval file.", file=sys.stderr)
            sys.exit(2)
sys.exit(0)
