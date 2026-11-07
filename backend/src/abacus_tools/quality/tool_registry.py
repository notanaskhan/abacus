"""The agent tool registry check in `make check-fast` (P-10-T10; C17; SPEC-647 AC-R1).

Imports every `modules/<m>/agent_tools.py`, then holds the registry to the matrix: a tool's action
exists, a `read`, `compute` or `propose` tool's action is one the agent may hold, and an
`approved_write` tool's action is `agent: deny`, because it runs only under a person's grant.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from abacus.modules.agents.api import AgentTool, registered_tools

MODULES = Path(__file__).resolve().parents[2] / "abacus" / "modules"
MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"


def load_matrix(folder: Path = MATRIX) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for path in sorted(folder.glob("*.yaml")):
        document = cast(dict[str, dict[str, dict[str, object]]], yaml.safe_load(path.read_text()))
        rows |= document.get("actions", {})
    return rows


def import_agent_tools(root: Path = MODULES) -> list[str]:
    found = sorted(p.parent.name for p in root.glob("*/agent_tools.py"))
    for module in found:
        importlib.import_module(f"abacus.modules.{module}.agent_tools")
    return found


def problems(
    tools: Mapping[str, AgentTool], matrix: Mapping[str, Mapping[str, object]]
) -> list[str]:
    found: list[str] = []
    for name, tool in sorted(tools.items()):
        row = matrix.get(tool.action)
        if row is None:
            found.append(f"{name}: action {tool.action} is not in the matrix")
            continue
        agent = row.get("agent", "deny")
        if tool.kind == "approved_write":
            if agent != "deny":
                found.append(f"{name}: an approved_write action must be agent: deny")
        elif agent == "deny":
            found.append(f"{name}: a {tool.kind} tool's action must not be agent: deny")
    return found


def main() -> int:
    import_agent_tools()
    found = problems(registered_tools(), load_matrix())
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
