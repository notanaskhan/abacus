"""Fresh-MFA lint (Q-02-T37; Q-02 AC-42): every action `docs/architecture/fresh-mfa-actions.yaml`
lists is in the permission matrix sources (`docs/architecture/permission-matrix/*.yaml`) with
`mfa_recent: required`, once, in a known group.

Run: python -m abacus_tools.quality.fresh_mfa (`make check-fast`).

It reads the YAML sources, not the generated `_matrix.py`, so removing the condition from a listed
action fails before anything is regenerated. `tests/security/test_fresh_mfa_generated.py` then
shows `authorise` refusing each listed action without a fresh second factor, and the routes that
declare it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, cast

import yaml

from abacus_tools.codegen.permission_matrix import source

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs" / "architecture" / "fresh-mfa-actions.yaml"
GROUPS: Final = frozenset(
    {"wall", "ai_policy", "export", "legal_hold", "independence", "data_boundary", "reveal"}
    | {"portal_access"}  # P-07-T25 (DEC-303), P-08-T21: a client's portal unlock and MFA reset
)


def problems(register_text: str, matrix_text: str) -> list[str]:
    data = cast(dict[str, object], yaml.safe_load(register_text) or {})
    entries = cast(list[dict[str, str]], data.get("actions") or [])
    matrix = cast(
        dict[str, dict[str, object] | None],
        cast(dict[str, object], yaml.safe_load(matrix_text))["actions"],
    )
    found: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        action, group = entry.get("action", ""), entry.get("group", "")
        if action in seen:
            found.append(f"{action}: listed twice")
        seen.add(action)
        if group not in GROUPS:
            found.append(f"{action}: unknown group {group!r}")
        cells = matrix.get(action)
        if cells is None:
            found.append(f"{action}: not in the permission matrix")
        elif cells.get("mfa_recent") != "required":
            found.append(f"{action}: listed as fresh-MFA but lacks `mfa_recent: required`")
    if not entries:
        found.append("the fresh-MFA register lists no actions")
    return found


def main() -> int:
    found = problems(REGISTER.read_text(encoding="utf-8"), source())
    for problem in found:
        print(f"fresh-mfa-actions.yaml: {problem}")
    if found:
        print(f"{len(found)} fresh-MFA violation(s).")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
