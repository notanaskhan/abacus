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
# The same grid for the web app's fixtures and labels (ADM-02b).
TS_TARGET = BACKEND.parent / "apps" / "web" / "src" / "app-core" / "roleTemplates.gen.ts"
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


def render_ts(source: str) -> str:
    """`roleTemplates.gen.ts`: the templates, the grid rows with their labels, and the agent's
    locked row, as typed constants (the fixtures and ADM-02b's labels read them)."""
    document = cast(dict[str, object], yaml.safe_load(source))
    templates = cast(dict[str, dict[str, object]], document["templates"])
    grid = cast(list[dict[str, object]], document["grid"])
    agent = cast(dict[str, object], document["agent"])
    body: dict[str, object] = {
        "templates": {
            name: {"levels": list(_strings(spec["levels"])), "firmRole": spec.get("firm_role")}
            for name, spec in templates.items()
        },
        "grid": [
            {
                "key": row["key"],
                "label": row["label"],
                "actions": list(_strings(row.get("actions"))),
                "cells": row["cells"],
                "conditions": cast(dict[str, str], row.get("conditions") or {}),
            }
            for row in grid
        ],
        "agentLabel": agent["label"],
        "agentNever": list(_strings(agent["never"])),
    }
    return (
        "// GENERATED from docs/architecture/role-templates.yaml. Do not edit.\n"
        "// Regenerate: python -m abacus_tools.codegen.role_templates\n"
        "\n"
        f"export const ROLE_TEMPLATES = {_ts(body, 0, 30)} as const;\n"
    )


_WIDTH = 80  # prettier's default print width (apps/web has no override)


def _ts(value: object, indent: int, column: int) -> str:
    """A TypeScript literal as prettier prints it: objects expanded, arrays inline when they fit
    the line (`column` is where the value starts), trailing commas, double quotes."""
    pad = " " * indent
    if isinstance(value, dict):
        items = cast(dict[str, object], value)
        if not items:
            return "{}"
        lines = [
            f"{pad}  {key}: {_ts(item, indent + 2, indent + 4 + len(key))},\n"
            for key, item in items.items()
        ]
        return "{\n" + "".join(lines) + pad + "}"
    if isinstance(value, list):
        parts = [_ts(item, indent + 2, indent + 2) for item in cast(list[object], value)]
        inline = "[" + ", ".join(parts) + "]"
        if column + len(inline) + 1 <= _WIDTH:
            return inline
        return "[\n" + "".join(f"{pad}  {part},\n" for part in parts) + pad + "]"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the module is out of date")
    args = parser.parse_args(argv)
    text = SOURCE.read_text()
    outputs = ((TARGET, render(text)), (TS_TARGET, render_ts(text)))
    if args.check:
        stale = [path for path, body in outputs if not path.exists() or path.read_text() != body]
        for path in stale:
            print(f"{path.name} is out of date with {SOURCE.name}")
        return 1 if stale else 0
    for path, body in outputs:
        path.write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
