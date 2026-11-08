"""Generate `abacus.modules.agents.specs._specs_v2` from `specs/v2/*.yaml` (P-10-T20; ADR-047;
SPEC-647 AC-R8).

Run: python -m abacus_tools.codegen.agent_specs_v2 [--check]

The codegen refuses a spec before it is rendered, so a bad capability never reaches the runtime:

- the spec's own rules (`spec_v2.spec_problems`): a single_call takes one step and no tools, a
  loop declares `max_tool_calls` and `max_repeat_identical_calls`, a propose or approved_write
  tool forces `plan: required_when_writes`, `tri` needs C19's consent checks, tiers are ordered;
- the registry's (`spec_v2.registry_problems`), after importing every module's `agent_tools.py`
  and reading the permission matrix: every tool is registered under the kind the spec lists it, its
  action is in `task_scope`, an approved_write tool's action is `agent: deny`, any other tool's is
  agent-holdable, and a denied scope action belongs to one of the spec's approved_write tools;
- clearance (`agent_specs.check_clearance`): `client_data: cleared` needs a committed Bedrock
  evaluation report and Bedrock route parity.

The v1 specs (`specs/*.yaml`) are rendered by `agent_specs` and stay untouched.
"""

from __future__ import annotations

import argparse
import importlib
import pprint
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from abacus_tools.codegen.agent_specs import SPECS_DIR, check_clearance
from abacus_tools.quality.tool_registry import import_agent_tools, load_matrix

V2_DIR = SPECS_DIR / "v2"
TARGET = SPECS_DIR / "_specs_v2.py"
_HEADER = '''"""GENERATED from abacus/modules/agents/specs/v2/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.agent_specs_v2
"""

'''


class SpecV2Refused(ValueError):
    pass


def _agent_cell(matrix: Mapping[str, Mapping[str, object]], action: str) -> str | None:
    row = matrix.get(action)
    return None if row is None else str(row.get("agent", "deny"))


def refusals(
    document: dict[str, object], matrix: Mapping[str, Mapping[str, object]] | None = None
) -> list[str]:
    """Every reason this spec may not be rendered; empty means it renders."""
    # Imported here: the runtime module validates its own generated file at import.
    from abacus.modules.agents.api import registered_tools
    from abacus.modules.agents.spec_v2 import (
        AgentSpecV2,
        ToolFacts,
        registry_problems,
        spec_problems,
    )

    rows = load_matrix() if matrix is None else matrix
    spec = AgentSpecV2.model_validate(document)

    def holdable(action: str) -> bool:
        return _agent_cell(rows, action) == "task_scope"

    def denied(action: str) -> bool:
        return _agent_cell(rows, action) == "deny"

    tools = {n: ToolFacts(t.kind, t.action) for n, t in registered_tools().items()}
    found = spec_problems(spec, holdable=lambda a: True)  # scope is the registry rule's
    found += registry_problems(spec, tools, denied=denied, holdable=holdable)
    return found


def render(folder: Path = V2_DIR) -> str:
    import_agent_tools()
    importlib.import_module("abacus.modules.organisations.api")  # registers C19's consent checks

    specs: dict[str, object] = {}
    for path in sorted(folder.glob("*.yaml")):
        document = cast(dict[str, object], yaml.safe_load(path.read_text()))
        check_clearance(document)
        found = refusals(document)
        if found:
            raise SpecV2Refused(f"{path.name}: " + "; ".join(found))
        specs[str(document["id"])] = document
    body = pprint.pformat(specs, indent=4, width=99, sort_dicts=True)
    return f"{_HEADER}# fmt: off\nSPECS_V2: dict[str, dict[str, object]] = {body}\n# fmt: on\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        expected = render()
    except SpecV2Refused as refused:
        print(refused)
        return 1
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(
                f"{TARGET.relative_to(SPECS_DIR.parents[4])} is out of date with the v2 spec YAML"
            )
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
