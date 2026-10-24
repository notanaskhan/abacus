"""Generate `abacus.modules.identity._role_templates` from `docs/architecture/role-templates.yaml`
(G-01-T05; G-01 section 3.5, AC5.1 to AC5.3).

Run: python -m abacus_tools.codegen.role_templates [--check]

The runtime image has no YAML parser, so the templates and ADM-02b's capability grid are rendered
into Python literals (as the permission matrix is). The source is validated as it is rendered:
every template and every cell names a known template, every cell a known symbol, and the agent's
`never` rows exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final, cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
SOURCE = BACKEND.parent / "docs" / "architecture" / "role-templates.yaml"
TARGET = BACKEND / "src" / "abacus" / "modules" / "identity" / "_role_templates.py"
CELLS: Final = frozenset({"allow", "conditional", "delegated", "deny"})
TEMPLATES: Final = (
    "partner",
    "manager",
    "tax_reviewer",
    "senior",
    "staff",
    "tax_preparer",
    "firm_admin",
    "it_security",
)

_HEADER = '''"""GENERATED from docs/architecture/role-templates.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.role_templates
"""

'''


def _q(value: object) -> str:
    return json.dumps(value)


def _list(values: tuple[str, ...], indent: str) -> str:
    """A list literal; one item per line (with the magic trailing comma) so `ruff format`
    leaves it as it is."""
    if not values:
        return "[]"
    items = "".join(f"{indent}    {_q(v)},\n" for v in values)
    return f"[\n{items}{indent}]"


def _strings(values: object) -> tuple[str, ...]:
    return tuple(str(v) for v in cast(list[object], values or []))


def render(source: str) -> str:
    document = cast(dict[str, object], yaml.safe_load(source))
    templates = cast(dict[str, dict[str, object]], document["templates"])
    if tuple(templates) != TEMPLATES:
        raise ValueError(f"role templates must be {TEMPLATES} in that order")
    grid = cast(list[dict[str, object]], document["grid"])
    keys = [str(row["key"]) for row in grid]
    if len(set(keys)) != len(keys):
        raise ValueError("role templates: duplicate grid row")
    agent = cast(dict[str, object], document["agent"])
    never = _strings(agent["never"])
    if unknown := set(never) - set(keys):
        raise ValueError(f"role templates: agent.never names unknown rows {sorted(unknown)}")

    lines = [_HEADER, "TEMPLATES: dict[str, dict[str, object]] = {\n"]
    for name, spec in templates.items():
        lines.append(f"    {_q(name)}: {{\n")
        firm_role = spec.get("firm_role")
        lines.append(f'        "levels": {_list(_strings(spec["levels"]), "        ")},\n')
        lines.append(f'        "firm_role": {"None" if firm_role is None else _q(firm_role)},\n')
        lines.append(f'        "roles": {_list(_strings(spec["roles"]), "        ")},\n')
        lines.append("    },\n")
    lines.append("}\n\nGRID: tuple[dict[str, object], ...] = (\n")
    for row in grid:
        cells = cast(dict[str, str], row["cells"])
        conditions = cast(dict[str, str], row.get("conditions") or {})
        if tuple(cells) != TEMPLATES:
            raise ValueError(f"grid row {row['key']}: a cell for every template, in order")
        if bad := {str(v) for v in cells.values()} - CELLS:
            raise ValueError(f"grid row {row['key']}: unknown cells {sorted(bad)}")
        if bad := set(conditions) - set(TEMPLATES):
            raise ValueError(f"grid row {row['key']}: conditions for unknown templates {bad}")
        lines.append("    {\n")
        lines.append(f'        "key": {_q(row["key"])},\n')
        lines.append(f'        "label": {_q(row["label"])},\n')
        lines.append(f'        "actions": {_list(_strings(row.get("actions")), "        ")},\n')
        lines.append('        "cells": {\n')
        lines += [f"            {_q(t)}: {_q(c)},\n" for t, c in cells.items()]
        lines.append("        },\n")
        if conditions:
            lines.append('        "conditions": {\n')
            lines += [f"            {_q(t)}: {_q(c)},\n" for t, c in conditions.items()]
            lines.append("        },\n")
        else:
            lines.append('        "conditions": {},\n')
        lines.append("    },\n")
    lines.append(")\n\n")
    lines.append(f"AGENT_LABEL = {_q(agent['label'])}\n")
    lines.append("AGENT_NEVER: tuple[str, ...] = (\n")
    lines += [f"    {_q(key)},\n" for key in never]
    lines.append(")\n")
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the module is out of date")
    args = parser.parse_args(argv)
    expected = render(SOURCE.read_text())
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.name} is out of date with {SOURCE.name}")
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
