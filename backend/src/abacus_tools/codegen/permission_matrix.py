"""Generate `abacus.modules.identity.authz._matrix` from the permission matrix (ADR-027).

Run: python -m abacus_tools.codegen.permission_matrix [--check]

The runtime image ships product code only and has no YAML parser, so the permission matrix is
rendered into a Python literal. It is split per module (P-39; F-03-T07):
`docs/architecture/permission-matrix/_roles.yaml` holds the roles, and `<module>.yaml` each
module's actions; `source()` joins them, and actions render sorted, so where an action lives never
changes the output. The unit tests fail when the checked-in module and the YAML differ; `--check`
reports the same without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
SOURCE_DIR = BACKEND.parent / "docs" / "architecture" / "permission-matrix"
TARGET = BACKEND / "src" / "abacus" / "modules" / "identity" / "authz" / "_matrix.py"

_HEADER = '''"""GENERATED from docs/architecture/permission-matrix/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.permission_matrix
"""

'''


def _q(value: object) -> str:
    return json.dumps(str(value))


def _reject_duplicate_keys(node: yaml.Node | None) -> None:
    """YAML keeps the last of duplicate keys silently; in a permission matrix that hides a rule."""
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key, value in cast(list[tuple[yaml.Node, yaml.Node]], node.value):
            name = str(cast(object, key.value))
            if name in seen:
                line = key.start_mark.line + 1
                raise ValueError(f"permission matrix: duplicate key {name!r} (line {line})")
            seen.add(name)
            _reject_duplicate_keys(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in cast(list[yaml.Node], node.value):
            _reject_duplicate_keys(item)


def source(directory: Path | None = None) -> str:
    """The roles file and every module's actions, joined into one YAML document."""
    folder = directory or SOURCE_DIR
    parts = [(folder / "_roles.yaml").read_text().rstrip("\n"), "", "actions:"]
    for path in sorted(folder.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = path.read_text()
        if "\nactions:\n" not in f"\n{text}":
            raise ValueError(f"{path.name}: a module file holds one `actions:` mapping")
        parts.append(f"\n{text}".split("\nactions:\n", 1)[1].rstrip("\n"))
    return "\n".join(parts) + "\n"


def render(source: str) -> str:
    """A Python module, already in `ruff format` style (one entry per line, trailing commas)."""
    loader = yaml.SafeLoader(source)
    try:
        _reject_duplicate_keys(loader.get_single_node())
    finally:
        loader.dispose()
    document = cast(dict[str, object], yaml.safe_load(source))
    roles = cast(list[str], document["roles"])
    actions = cast(dict[str, dict[str, str]], document["actions"])
    lines = [_HEADER, "ROLES: tuple[str, ...] = (\n"]
    lines += [f"    {_q(role)},\n" for role in roles]
    lines.append(")\n\nACTIONS: dict[str, dict[str, str]] = {\n")
    for action, rules in sorted(actions.items()):
        lines.append(f"    {_q(action)}: {{\n")
        lines += [f"        {_q(key)}: {_q(value)},\n" for key, value in rules.items()]
        lines.append("    },\n")
    lines.append("}\n")
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the module is out of date")
    args = parser.parse_args(argv)
    expected = render(source())
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.relative_to(BACKEND)} is out of date with {SOURCE_DIR.name}/")
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
