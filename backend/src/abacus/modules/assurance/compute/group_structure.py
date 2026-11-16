"""The deterministic group structure proposal (A-09-T13 rest; AUD-32 c; DV-2; DEC-5340).

A group's source (NetSuite OneWorld) names each subsidiary and its parent. The proposal places
every subsidiary that matches one of the client's entities by its casefolded name (bulk upload's
rule):
the top of the tree is level 1 and each child sits one level below its parent. A subsidiary whose
name matches no entity, or more than one, is left out with everything under it (its place in the
tree is unknown). A fourth tier refuses (X-06: three tiers at most). Ownership is always 100%, so
it is not part of the proposal.

The proposal travels as a code run's identifier-only output; a field value holds 200 characters,
so the suggestion carries the output's SHA-256 and the adopting code re-reads and checks it.
The standard library only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

MAX_LEVEL: Final = 3


@dataclass(frozen=True)
class Placed:
    client_entity_id: UUID
    parent_client_entity_id: UUID | None
    level: int


class HierarchyInvalid(ValueError):
    """The source named a subsidiary twice or its parents form a loop."""


class StructureTooDeep(ValueError):
    """A matched subsidiary would sit below the third tier."""


def _key(name: str) -> str:
    return name.strip().casefold()


def propose(
    hierarchy: Sequence[tuple[str, str | None]], entities: Mapping[UUID, str]
) -> tuple[Placed, ...]:
    """`hierarchy` is the source's (subsidiary, parent) pairs; `entities` the client's entity
    names by id. Ordered by level, then name, then id."""
    parent_of: dict[str, str | None] = {}
    for subsidiary, parent in hierarchy:
        key = _key(subsidiary)
        if key in parent_of:
            raise HierarchyInvalid(subsidiary)
        parent_of[key] = None if parent is None else _key(parent)
    named: dict[str, list[UUID]] = {}
    for entity_id, name in entities.items():
        named.setdefault(_key(name), []).append(entity_id)
    match = {k: ids[0] for k, ids in named.items() if len(ids) == 1}

    def chain(key: str) -> list[str]:
        """`key` and its ancestors inside the source, nearest first."""
        seen = [key]
        up = parent_of[key]
        while up is not None and up in parent_of:
            if up in seen:
                raise HierarchyInvalid(up)
            seen.append(up)
            up = parent_of[up]
        return seen

    placed: list[tuple[int, str, Placed]] = []
    for key in parent_of:
        line = chain(key)
        if any(k not in match for k in line):
            continue
        level = len(line)
        if level > MAX_LEVEL:
            raise StructureTooDeep(key)
        parent = match[line[1]] if level > 1 else None
        placed.append((level, key, Placed(match[key], parent, level)))
    placed.sort(key=lambda p: (p[0], p[1], str(p[2].client_entity_id)))
    return tuple(p for _, _, p in placed)


def output_of(placed: Sequence[Placed]) -> dict[str, object]:
    """The code run's output: identifiers and levels only."""
    return {
        "entities": [
            [
                str(p.client_entity_id),
                None if p.parent_client_entity_id is None else str(p.parent_client_entity_id),
                p.level,
            ]
            for p in placed
        ]
    }


def digest(output: Mapping[str, object]) -> str:
    raw = json.dumps(output, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def from_output(output: Mapping[str, object]) -> tuple[Placed, ...]:
    """The proposal back from a run's output; `ValueError` for any other shape."""
    rows = output.get("entities")
    if not isinstance(rows, list) or not rows:
        raise ValueError("entities")
    out: list[Placed] = []
    for row in cast(list[object], rows):
        if not isinstance(row, list) or len(cast(list[object], row)) != 3:
            raise ValueError("row")
        entity, parent, level = cast(list[object], row)
        if not isinstance(entity, str) or not (parent is None or isinstance(parent, str)):
            raise ValueError("id")
        if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= MAX_LEVEL:
            raise ValueError("level")
        out.append(Placed(UUID(entity), None if parent is None else UUID(parent), level))
    return tuple(out)
