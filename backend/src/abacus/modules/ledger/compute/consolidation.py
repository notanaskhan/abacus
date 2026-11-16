"""The consolidation engine (A-09-T19; A-09 §3 F3; SPEC-658; AUD-33; ADR-050). Pure: Decimal
only, no clock, no database, no I/O; imports nothing outside the compute package.

- **Inputs.** Each entity's mapped trial balance as (caption, section, signed amount, debit
  positive); the consolidation's levels (which entities each level holds; level 1 is the whole
  group); and the posted eliminations, each at one level, with debit and credit lines by caption.
- **A level's columns.** One column per member entity, the eliminations column (the net debit of
  every posted elimination at this level or below it: level 1 consolidates the whole group, so
  it carries every elimination; a sub-level carries its own), and consolidated = the entities'
  sum + the eliminations' net debit (eliminations reduce what the entities report).
- **Checks.** Every column nets to zero (a trial balance in balance), each elimination balances,
  and the level's total assets and net income are read off the consolidated column (net income =
  minus the income section's net, income being credit-natural).
- **Attribution.** Each entity's share of the consolidated assets before eliminations (for
  component coverage, A-09-T23).

`inputs_hash` is the SHA-256 of the canonical inputs; the same inputs always give the same hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

ENGINE_NAME: Final = "consolidation"
ENGINE_VERSION: Final = "1"
ZERO: Final = Decimal("0.00")
CENT: Final = Decimal("0.01")
ELIMINATIONS: Final = "eliminations"
CONSOLIDATED: Final = "consolidated"

Section = Literal["assets", "liabilities_equity", "income"]


class ConsolidationInvalid(ValueError):
    code = "consolidation_invalid"


@dataclass(frozen=True)
class TbLine:
    caption: str
    section: Section
    amount: Decimal  # signed, debit positive


@dataclass(frozen=True)
class EliminationLine:
    caption: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class Elimination:
    code: str
    level: int
    lines: tuple[EliminationLine, ...]

    @property
    def balances(self) -> bool:
        return sum((ln.debit for ln in self.lines), ZERO) == sum(
            (ln.credit for ln in self.lines), ZERO
        )


@dataclass(frozen=True)
class Cell:
    column: str
    amount: Decimal
    elimination_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Row:
    caption: str
    section: Section
    cells: tuple[Cell, ...]

    def amount(self, column: str) -> Decimal:
        return next((c.amount for c in self.cells if c.column == column), ZERO)


@dataclass(frozen=True)
class Level:
    level: int
    members: tuple[str, ...]
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    column_totals: Mapping[str, Decimal]
    ties: bool
    total_assets: Decimal
    net_income: Decimal
    eliminations_posted: int
    attribution: Mapping[str, Decimal]  # each member's share of assets before eliminations, %
    inputs_hash: str


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def _captions(tbs: Mapping[str, Sequence[TbLine]]) -> list[tuple[str, Section]]:
    seen: dict[str, Section] = {}
    for lines in tbs.values():
        for line in lines:
            known = seen.get(line.caption)
            if known is not None and known != line.section:
                raise ConsolidationInvalid(f"caption {line.caption!r} in two sections")
            seen.setdefault(line.caption, line.section)
    order: dict[str, int] = {"assets": 0, "liabilities_equity": 1, "income": 2}
    first = {
        c: i for i, c in enumerate(dict.fromkeys(ln.caption for v in tbs.values() for ln in v))
    }
    return sorted(seen.items(), key=lambda kv: (order[kv[1]], first[kv[0]]))


def inputs_hash(
    tbs: Mapping[str, Sequence[TbLine]],
    members: Sequence[str],
    level: int,
    eliminations: Sequence[Elimination],
) -> str:
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "level": level,
            "members": sorted(members),
            "tbs": {
                k: sorted([ln.caption, ln.section, str(_q(ln.amount))] for ln in v)
                for k, v in sorted(tbs.items())
                if k in members
            },
            "eliminations": sorted(
                [
                    e.code,
                    e.level,
                    sorted([ln.caption, str(_q(ln.debit)), str(_q(ln.credit))] for ln in e.lines),
                ]
                for e in eliminations
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


def consolidate(
    tbs: Mapping[str, Sequence[TbLine]],
    members: Sequence[str],
    *,
    level: int,
    eliminations: Sequence[Elimination],
    top_level: int = 1,
) -> Level:
    """One level's consolidated trial balance. `eliminations` are the posted ones; a level
    carries those at its own level, and the top level carries every one."""
    missing = [m for m in members if m not in tbs]
    if missing or not members:
        raise ConsolidationInvalid(f"no trial balance for {missing}")
    for e in eliminations:
        if not e.balances:
            raise ConsolidationInvalid(f"elimination {e.code} does not balance")
    used = [e for e in eliminations if level == top_level or e.level == level]
    captions = _captions({k: v for k, v in tbs.items() if k in members})
    elim_captions = {ln.caption for e in used for ln in e.lines}
    known = {c for c, _ in captions}
    if elim_captions - known:
        raise ConsolidationInvalid(
            f"elimination caption not in any TB: {sorted(elim_captions - known)}"
        )
    by_entity = {k: {ln.caption: _q(ln.amount) for ln in tbs[k]} for k in members}
    rows: list[Row] = []
    for caption, section in captions:
        own = [by_entity[m].get(caption, ZERO) for m in members]
        net = _q(
            sum(
                (ln.debit - ln.credit for e in used for ln in e.lines if ln.caption == caption),
                ZERO,
            )
        )
        codes = tuple(e.code for e in used if any(ln.caption == caption for ln in e.lines))
        rows.append(
            Row(
                caption,
                section,
                (
                    *(Cell(m, a) for m, a in zip(members, own, strict=True)),
                    Cell(ELIMINATIONS, net, codes),
                    Cell(CONSOLIDATED, _q(sum(own, ZERO) + net)),
                ),
            )
        )
    columns = (*members, ELIMINATIONS, CONSOLIDATED)
    totals = {c: _q(sum((r.amount(c) for r in rows), ZERO)) for c in columns}
    assets = _q(sum((r.amount(CONSOLIDATED) for r in rows if r.section == "assets"), ZERO))
    income = _q(sum((r.amount(CONSOLIDATED) for r in rows if r.section == "income"), ZERO))
    gross = {
        m: _q(sum((r.amount(m) for r in rows if r.section == "assets"), ZERO)) for m in members
    }
    whole = sum(gross.values(), ZERO)
    attribution = {m: (ZERO if whole == 0 else _q(gross[m] * 100 / whole)) for m in members}
    return Level(
        level=level,
        members=tuple(members),
        columns=columns,
        rows=tuple(rows),
        column_totals=totals,
        ties=all(v == 0 for v in totals.values()),
        total_assets=assets,
        net_income=_q(-income),
        eliminations_posted=len(used),
        attribution=attribution,
        inputs_hash=inputs_hash(tbs, members, level, used),
    )
