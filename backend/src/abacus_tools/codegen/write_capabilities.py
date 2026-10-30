"""Compile the write-capability registry into `abacus.modules.integrations._capabilities`
(A-02-T15; ADR-150, P-17, DEC-46; SPEC-333 AC-50; C20 v1).

Run: python -m abacus_tools.codegen.write_capabilities [--check | --egress]

`docs/architecture/write-capabilities.yaml` is a protected policy file: the read connectors with
the only hosts each may reach, and the writes. It validates against
`integrations.ports.WriteCapabilityRegistry` (version 2: only a shape in `OPENABLE_SHAPES` may be
enabled, and only by an ADR), and on top of the schema this compiler refuses:

- version 2 unless ADR-150 itself is accepted, and an enabled write whose ADR is not accepted
  (`status: accepted` in `docs/adr/`; DEC-1280);
- a write that names no decision (the plan P-nn or repo ADR that would enable it);
- a write whose `adapter_key` is a declared read connector's (a reader never also writes);
- duplicate YAML keys and any field the schema does not know.

`--check` (in `make check-generated`) fails when the generated module differs from what the file
compiles to, so a hand edit of `_capabilities.py` fails the drift check. `--egress` prints the
egress host allowlist as JSON for Q-01's DNS Firewall generator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from abacus.modules.integrations.api import WriteCapabilityRegistry

BACKEND = Path(__file__).resolve().parents[3]
SOURCE = BACKEND.parent / "docs" / "architecture" / "write-capabilities.yaml"
ADRS = BACKEND.parent / "docs" / "adr"
FRAMEWORK_ADR = "ADR-150"
TARGET = BACKEND / "src" / "abacus" / "modules" / "integrations" / "_capabilities.py"
_HEADER = '''"""GENERATED from docs/architecture/write-capabilities.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.write_capabilities
"""

'''


class RegistryInvalid(ValueError):
    pass


def _no_duplicate_keys(node: yaml.Node | None) -> None:
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key, value in cast(list[tuple[yaml.Node, yaml.Node]], node.value):
            name = str(cast(yaml.ScalarNode, key).value)
            if name in seen:
                raise RegistryInvalid(f"{name!r} appears twice")
            seen.add(name)
            _no_duplicate_keys(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in cast(list[yaml.Node], node.value):
            _no_duplicate_keys(item)


def adr_accepted(adr: str, adrs: Path | None = None) -> bool:
    """Whether the repo ADR's front matter says `status: accepted`."""
    found = sorted((adrs or ADRS).glob(f"{adr}-*.md"))
    if len(found) != 1:
        return False
    head = found[0].read_text(encoding="utf-8").split("\n---", 1)[0]
    return any(line.strip() == "status: accepted" for line in head.splitlines())


def load(source: str) -> WriteCapabilityRegistry:
    """The registry the file declares; `RegistryInvalid` names the first rule it breaks."""
    loader = yaml.SafeLoader(source)
    try:
        _no_duplicate_keys(loader.get_single_node())
    finally:
        loader.dispose()
    try:
        registry = WriteCapabilityRegistry.model_validate(yaml.safe_load(source))
    except ValidationError as exc:
        first = exc.errors()[0]["msg"]
        raise RegistryInvalid(f"the registry does not validate: {first}") from None
    if not adr_accepted(FRAMEWORK_ADR):
        raise RegistryInvalid(f"version 2 needs {FRAMEWORK_ADR} accepted")
    readers = {r.adapter_key for r in registry.read_connectors}
    for write in registry.writes:
        if write.enabled and not adr_accepted(str(write.decision)):
            raise RegistryInvalid(f"{write.key}: enabled, but {write.decision} is not accepted")
        if write.decision is None:
            raise RegistryInvalid(f"{write.key}: a write names the decision that would enable it")
        if write.adapter_key in readers:
            raise RegistryInvalid(f"{write.key}: a read connector never also writes")
    return registry


def _value(value: object, indent: int = 8) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, list):
        items = cast(list[object], value)
        if len(items) < 2:
            return "(" + "".join(f"{_value(v)}," for v in items) + ")"
        # Two or more carry ruff's magic trailing comma: one item per line, as ruff formats it.
        inner = " " * (indent + 4)
        return "(\n" + "".join(f"{inner}{_value(v)},\n" for v in items) + " " * indent + ")"
    return json.dumps(value)


def _rows(entries: list[dict[str, object]]) -> str:
    """A tuple of dict literals as ruff formats them (one field per line)."""
    if not entries:
        return "()"
    out = ["("]
    for entry in entries:
        out.append("    {")
        out.extend(f"        {json.dumps(k)}: {_value(entry[k])}," for k in sorted(entry))
        out.append("    },")
    out.append(")")
    return "\n".join(out)


def render(registry: WriteCapabilityRegistry) -> str:
    readers = [
        r.model_dump(mode="json")
        for r in sorted(registry.read_connectors, key=lambda r: r.adapter_key)
    ]
    writes = [w.model_dump(mode="json") for w in sorted(registry.writes, key=lambda w: w.key)]
    hosts = sorted(registry.egress_hosts())
    egress = (
        "frozenset(\n    {" + "".join(f"\n        {json.dumps(h)}," for h in hosts) + "\n    }\n)"
        if hosts
        else "frozenset()"
    )
    return (
        _HEADER
        + "from typing import Final\n\n"
        + f"VERSION: Final = {registry.version}\n"
        + "# The read connectors and the only hosts each may reach (ADR-040).\n"
        + f"READ_CONNECTORS: Final[tuple[dict[str, object], ...]] = {_rows(readers)}\n"
        + "# Declared writes: an openable shape under an accepted ADR may be enabled (DEC-1280).\n"
        + f"WRITES: Final[tuple[dict[str, object], ...]] = {_rows(writes)}\n"
        + "# Q-01's DNS Firewall allowlist: every declared egress host.\n"
        + f"EGRESS_HOSTS: Final[frozenset[str]] = {egress}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail if the module is out of date")
    mode.add_argument("--egress", action="store_true", help="print the egress host allowlist")
    args = parser.parse_args(argv)
    try:
        registry = load(SOURCE.read_text())
    except RegistryInvalid as exc:
        print(f"write-capabilities.yaml: {exc}", file=sys.stderr)
        return 1
    if args.egress:
        print(json.dumps(sorted(registry.egress_hosts())))
        return 0
    body = render(registry)
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != body:
            print(f"{TARGET.name} is out of date: run python -m {__spec__.name}")
            return 1
        return 0
    TARGET.write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
