#!/usr/bin/env python3
"""PreToolUse hook for Bash. A best-effort local guard against destructive or unsafe commands.

Solo edition (SU-06): no approval gates. It blocks only what can destroy work, leak data or reach
production. Fails closed: any error exits 2.
"""
import json
import os
import re
import sys

RULES = [
    (r"git\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease|\s\+\S)", "Force pushes are forbidden."),
    (r"git\s+commit\b.*(--no-verify|\s-n\b)", "Skipping hooks is forbidden."),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\.|\*)(\s|$)", "Recursive deletion of root, home or the project is forbidden."),
    (r"\bsudo\b", "sudo is not allowed."),
    (r"\bchmod\s+777\b", "World-writable permissions are not allowed."),
    (r"\bterraform\s+(destroy|import|state)\b", "terraform destroy, import and state run by hand, never from a session (ADR-021)."),
    (r"\b(psql|pg_dump|pg_restore)\b(?!.*(localhost|127\.0\.0\.1|@db\b|host=db))", "Database tools may only target local databases (ADR-087)."),
    (r"\baws\b.*--profile\s+\S*prod", "No agent access to production accounts (ADR-028)."),
    (r"(api\.anthropic\.com|api\.openai\.com)", "Model providers are reached only through ai_gateway (ADR-019)."),
    (r"\balembic\s+downgrade\b.*(prod|staging)", "Downgrades run only locally."),
]

def stems(patterns):
    """Literal path fragments of each pattern: `x/**` -> `x`, `**/Makefile` -> `Makefile`."""
    out = set()
    for pat in patterns:
        literal = pat[3:] if pat.startswith("**/") else pat
        stem = literal.split("*")[0].rstrip("/")
        if stem:
            out.add(stem)
    return sorted(out)


# Resolving a conflict in a generated file by picking a side leaves it out of date (F-01-T09).
PICK_SIDE = re.compile(r"\bgit\s+checkout\b.*\s--(ours|theirs)\b")


# The mutation floors file (Q-03-T027) changes only through the edit hook, which refuses a lowered
# floor; the shell may read it, never write it.
FLOORS_NAME = "mutation-thresholds.yaml"
FLOORS_READERS = re.compile(
    r"^\s*(cat|head|tail|less|grep|rg|wc|diff|ls|"
    r"git\s+(diff|show|log|blame|status|add|commit)|"
    r"(uv\s+run\s+)?python3?\s+-m\s+abacus_tools\.quality\.mutation(_floors)?)\b"
)


def floors_write(cmd):
    if FLOORS_NAME not in cmd:
        return None
    for segment in re.split(r"&&|\|\||;|\||\n", cmd):
        if FLOORS_NAME not in segment:
            continue
        if re.search(r">>?\s*\S*" + re.escape(FLOORS_NAME), segment) or not FLOORS_READERS.match(segment):
            return (
                "backend/mutation-thresholds.yaml changes only through the Edit or Write tool, "
                "where the hook refuses a lowered floor (Q-03-T027)."
            )
    return None


def check(cmd):
    from _protected import GENERATED

    for pattern, reason in RULES:
        if re.search(pattern, cmd):
            return reason
    floors = floors_write(cmd)
    if floors:
        return floors
    if PICK_SIDE.search(cmd):
        for stem in stems([pattern for pattern, _ in GENERATED]):
            if re.search(r"(?<![\w.-])" + re.escape(stem) + r"(?![\w-])", cmd, re.IGNORECASE):
                return f"'{stem}' is generated: don't pick a side of the conflict; run make regenerate."
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
