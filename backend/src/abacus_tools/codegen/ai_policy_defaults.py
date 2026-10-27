"""Generate `abacus.modules.agents._ai_policy_defaults` from the AI policy defaults (G-02-T23).
Run: python -m abacus_tools.codegen.ai_policy_defaults [--check]

`docs/architecture/ai-policy-defaults.yaml` holds the platform's policy sections, the locked cells,
which way each tunable cell is stricter, and the twelve-gate catalogue (ADR-186, ADR-187). The
file is validated here (twelve gates numbered 1 to 12, unique keys, known directions, locks and
stricter cells naming real section paths) and written as a JSON document the module parses once.
`--check` reports a stale module without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
SOURCE = BACKEND.parent / "docs" / "architecture" / "ai-policy-defaults.yaml"
TARGET = BACKEND / "src" / "abacus" / "modules" / "agents" / "_ai_policy_defaults.py"
GATES = 12
DIRECTIONS = frozenset({"lower", "higher"})
_HEADER = '''"""GENERATED from docs/architecture/ai-policy-defaults.yaml. Do not edit.
Regenerate: python -m abacus_tools.codegen.ai_policy_defaults
"""

from __future__ import annotations

import json
from typing import Final, cast

'''


def _has_path(sections: dict[str, object], path: str) -> bool:
    head, _, rest = path.partition(".")
    if head == "gates":
        return rest == "*.policy_acceptance_on"
    node = sections.get(head)
    return isinstance(node, dict) and rest in cast(dict[str, object], node)


def validate(document: dict[str, object]) -> None:
    sections = cast(dict[str, object], document["sections"])
    for path in cast(list[str], document["locks"]):
        if not _has_path(sections, path):
            raise ValueError(f"lock {path!r} names no section cell")
    for path, way in cast(dict[str, str], document["stricter"]).items():
        if way not in DIRECTIONS or not _has_path(sections, path):
            raise ValueError(f"stricter {path!r}: {way!r}")
    gates = cast(list[dict[str, object]], document["gates"])
    if [g["row"] for g in gates] != list(range(1, GATES + 1)):
        raise ValueError(f"the catalogue holds gates 1 to {GATES}, in order")
    keys = [g["gate_key"] for g in gates]
    if len(set(keys)) != len(keys):
        raise ValueError("gate keys are unique")
    for gate in gates:
        # AC-32: every gate names its approver, the approver rule's roles until the owning epic
        # builds the action (then the matrix's roles for it, checked by a generated test).
        if not gate.get("approver_roles"):
            raise ValueError(f"{gate['gate_key']}: every gate names its approver roles")


def render(text: str) -> str:
    document = cast(dict[str, object], yaml.safe_load(text))
    validate(document)
    body = json.dumps(document, indent=2, sort_keys=True)
    return (
        _HEADER
        + f'_DOCUMENT: Final[dict[str, object]] = json.loads(\n    r"""\n{body}\n"""\n)\n'
        + 'SCHEMA_VERSION: Final = cast(int, _DOCUMENT["schema_version"])\n'
        + 'SECTIONS: Final = cast(dict[str, object], _DOCUMENT["sections"])\n'
        + 'LOCKS: Final = tuple(cast(list[str], _DOCUMENT["locks"]))\n'
        + 'STRICTER: Final = cast(dict[str, str], _DOCUMENT["stricter"])\n'
        + 'GATES: Final = tuple(cast(list[dict[str, object]], _DOCUMENT["gates"]))\n'
    )


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
