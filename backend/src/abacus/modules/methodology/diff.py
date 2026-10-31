"""A version's diff against another, by lineage (K-01-T18; K-01 §3.6 AC6.1; KNW-02 c).

Pure and deterministic: the same two step lists always give the same diff (code only, ADR-050).
Steps pair by `step_key` first; the steps left over pair within their program by number when
their normalised texts are similar enough (a re-keyed step that kept its place and wording is the
same step), else they are added or removed. A paired step is changed when its text or any other
compared field differs; numbering alone is not a change. Rows come back in program, then number
order; the tiles count each kind.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Final, Literal

Kind = Literal["added", "changed", "removed"]

# What a person sees change on a step (`text` first; the rest are the editable fields and the
# lock); the step's position is not here.
COMPARED: Final = (
    "text",
    "assertions",
    "standard_refs",
    "level",
    "guidance",
    "mandatory",
    "lock_note",
)
# Two leftover steps in one program at one number are the same step above this similarity.
SIMILAR: Final = 0.8


@dataclass(frozen=True)
class StepRow:
    """One step as the diff reads it."""

    step_key: str
    program_code: str
    number: int
    fields: dict[str, object] = field(default_factory=dict[str, object])

    @property
    def text(self) -> str:
        value = self.fields.get("text")
        return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class DiffRow:
    kind: Kind
    program_code: str
    number: int
    step_key: str
    before_text: str | None
    after_text: str | None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class VersionDiff:
    added: int
    changed: int
    removed: int
    unchanged: int
    rows: tuple[DiffRow, ...]


def normalised(text: str) -> str:
    """NFKC, case-folded, whitespace collapsed: what "the same words" means here."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalised(a), normalised(b), autojunk=False).ratio()


def _changed(before: StepRow, after: StepRow) -> tuple[str, ...]:
    return tuple(f for f in COMPARED if before.fields.get(f) != after.fields.get(f))


def lineage_diff(before: Sequence[StepRow], after: Sequence[StepRow]) -> VersionDiff:
    old = {s.step_key: s for s in before}
    new = {s.step_key: s for s in after}
    pairs: list[tuple[StepRow, StepRow]] = [(old[k], new[k]) for k in old.keys() & new.keys()]
    left_old = {k: s for k, s in old.items() if k not in new}
    left_new = {k: s for k, s in new.items() if k not in old}
    # Second pass: same program, same number, similar text. Iterated in a fixed order.
    for key in sorted(left_new, key=lambda k: (left_new[k].program_code, left_new[k].number, k)):
        candidate = left_new[key]
        match = next(
            (
                ok
                for ok in sorted(left_old)
                if left_old[ok].program_code == candidate.program_code
                and left_old[ok].number == candidate.number
                and similarity(left_old[ok].text, candidate.text) >= SIMILAR
            ),
            None,
        )
        if match is not None:
            pairs.append((left_old.pop(match), candidate))
            del left_new[key]
    rows: list[DiffRow] = []
    unchanged = 0
    for b, a in pairs:
        fields = _changed(b, a)
        if fields:
            rows.append(
                DiffRow("changed", a.program_code, a.number, a.step_key, b.text, a.text, fields)
            )
        else:
            unchanged += 1
    rows.extend(
        DiffRow("added", s.program_code, s.number, s.step_key, None, s.text)
        for s in left_new.values()
    )
    rows.extend(
        DiffRow("removed", s.program_code, s.number, s.step_key, s.text, None)
        for s in left_old.values()
    )
    rows.sort(key=lambda r: (r.program_code, r.number, r.kind, r.step_key))
    return VersionDiff(
        added=sum(1 for r in rows if r.kind == "added"),
        changed=sum(1 for r in rows if r.kind == "changed"),
        removed=sum(1 for r in rows if r.kind == "removed"),
        unchanged=unchanged,
        rows=tuple(rows),
    )


__all__ = [
    "COMPARED",
    "SIMILAR",
    "DiffRow",
    "StepRow",
    "VersionDiff",
    "lineage_diff",
    "normalised",
]
