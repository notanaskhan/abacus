"""Generate `abacus.modules.agents.specs._specs` from the agent spec YAML files (ADR-047).

Run: python -m abacus_tools.codegen.agent_specs [--check]

The runtime has no YAML parser (PyYAML is tooling only), so each `specs/*.yaml` is rendered into
a Python literal; `AgentSpec` validates it at import. The unit tests fail when they drift.
"""

from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
OPERATIONS = BACKEND.parent / "docs" / "operations"
SPECS_DIR = BACKEND / "src" / "abacus" / "modules" / "agents" / "specs"
TARGET = SPECS_DIR / "_specs.py"
_HEADER = '''"""GENERATED from abacus/modules/agents/specs/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.agent_specs
"""

'''


class ClearanceRefused(ValueError):
    pass


def reports_dir(suite: str) -> Path:
    """`evals/upload_review` -> `docs/operations/upload-review` (where real-model reports go)."""
    return OPERATIONS / suite.removeprefix("evals/").replace("_", "-")


def check_clearance(document: dict[str, object]) -> None:
    """SPEC-036 AC-4: `client_data: cleared` needs a passing Bedrock evaluation report for the
    agent's suite and a Bedrock route parity report, both committed."""
    if document.get("client_data", "none") != "cleared":
        return
    agent = document["id"]
    if not any(reports_dir(str(document["evaluation_suite"])).glob("bedrock-*-passed.json")):
        raise ClearanceRefused(f"{agent}: cleared needs a bedrock-*-passed.json evaluation report")
    if not any((OPERATIONS / "route-parity").glob("bedrock-*.json")):
        raise ClearanceRefused(f"{agent}: cleared needs a bedrock route parity report")


def render() -> str:
    specs: dict[str, object] = {}
    for path in sorted(SPECS_DIR.glob("*.yaml")):
        document = cast(dict[str, object], yaml.safe_load(path.read_text()))
        check_clearance(document)
        specs[str(document["id"])] = document
    # Python literal syntax (True/None), not JSON (true/null).
    body = pprint.pformat(specs, indent=4, width=99, sort_dicts=True)
    # fmt: off/on keeps the literal exactly as generated, so the drift check is byte-exact.
    return f"{_HEADER}# fmt: off\nSPECS: dict[str, dict[str, object]] = {body}\n# fmt: on\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.relative_to(BACKEND)} is out of date with the spec YAML")
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
