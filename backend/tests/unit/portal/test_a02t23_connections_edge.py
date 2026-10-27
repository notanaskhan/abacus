"""A-02-T23 (TASK-1471; DEC-611; security review L3): the portal's edge to `connections` is one
name wide. The portal home reads only the reconnect to-do's count; any other import from
`connections` (its read models, its services) needs its own review and a line here."""

from __future__ import annotations

import ast
from pathlib import Path

PORTAL = Path(__file__).parents[3] / "src" / "abacus" / "modules" / "portal"
ALLOWED = frozenset({"reconnect_todo_count"})


def _imports_from_connections() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(PORTAL.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "abacus.modules.connections"
            ):
                assert node.module == "abacus.modules.connections.api", path
                found.setdefault(path.name, set()).update(a.name for a in node.names)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("abacus.modules.connections"), path
    return found


def test_the_portal_imports_only_the_reconnect_count_from_connections() -> None:
    found = _imports_from_connections()
    assert found == {"connections.py": set(ALLOWED)}
