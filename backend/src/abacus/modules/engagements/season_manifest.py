"""The season roll-forward manifest builder (T-08-T09; TASK-8724; SPEC-710; ENG-07; DEC-5718),
pure: candidates in, cohorts and tallies out, by code (ADR-050).

A candidate is a continuing tax client's prior-year return with its binder count, office and
segment, the people carried from last year, and the facts the exception rules read. Cohorts group
candidates by office and segment in a stable order; tallies count engagements (one per client),
returns and binders. An exception rule marks a row for a person's answer (it stays out of the
cohort's executable rows until resolved): a missing §7216 consent set, a lapsed engagement letter,
or a client flagged inactive. Prospects never enter a manifest (DEC-39).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

Exception_ = Literal["consent_missing", "letter_lapsed", "client_inactive"]
RULES: Final[tuple[Exception_, ...]] = ("consent_missing", "letter_lapsed", "client_inactive")


@dataclass(frozen=True, slots=True)
class Candidate:
    client: str
    office: str
    segment: str
    returns: int
    binders: int
    preparer: str | None
    reviewer: str | None
    consent_on_file: bool = True
    letter_current: bool = True
    active: bool = True
    prospect: bool = False


@dataclass(frozen=True, slots=True)
class Row:
    candidate: Candidate
    exceptions: tuple[Exception_, ...]


@dataclass(frozen=True, slots=True)
class Cohort:
    office: str
    segment: str
    rows: tuple[Row, ...]

    @property
    def engagements(self) -> int:
        return len({r.candidate.client for r in self.rows})

    @property
    def returns(self) -> int:
        return sum(r.candidate.returns for r in self.rows)

    @property
    def binders(self) -> int:
        return sum(r.candidate.binders for r in self.rows)

    @property
    def exceptions(self) -> tuple[str, ...]:
        return tuple(r.candidate.client for r in self.rows if r.exceptions)


def exceptions_of(c: Candidate) -> tuple[Exception_, ...]:
    found: list[Exception_] = []
    if not c.consent_on_file:
        found.append("consent_missing")
    if not c.letter_current:
        found.append("letter_lapsed")
    if not c.active:
        found.append("client_inactive")
    return tuple(found)


def build(candidates: Iterable[Candidate], order: Sequence[tuple[str, str]]) -> list[Cohort]:
    """Cohorts in `order` (office, segment); any other pair after, sorted."""
    groups: dict[tuple[str, str], list[Row]] = {}
    for c in candidates:
        if c.prospect:
            continue
        groups.setdefault((c.office, c.segment), []).append(Row(c, exceptions_of(c)))
    keys = [k for k in order if k in groups] + sorted(k for k in groups if k not in order)
    return [
        Cohort(k[0], k[1], tuple(sorted(groups[k], key=lambda r: r.candidate.client)))
        for k in keys
    ]


@dataclass(frozen=True, slots=True)
class Tally:
    engagements: int
    returns: int
    binders: int
    exceptions: int


def tally(cohorts: Sequence[Cohort]) -> Tally:
    """The manifest's footing line (ENG-07 a: 214 · 224 · 241, Exceptions 3)."""
    return Tally(
        sum(c.engagements for c in cohorts),
        sum(c.returns for c in cohorts),
        sum(c.binders for c in cohorts),
        sum(len(c.exceptions) for c in cohorts),
    )


__all__ = ["RULES", "Candidate", "Cohort", "Row", "Tally", "build", "exceptions_of", "tally"]
