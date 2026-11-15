"""JE scoring, v1 (A-08-T10; SPEC-657 AC-0.9, AC-1.2, AC-1.3; ADR-050; DEC-5034).

Pure functions over journal entries (one entry: its reference, posting date, amount, accounts,
descriptions and the JE fields where the ledger carries them, ADR-400). The firm's risk criteria
are content (`threshold_policies.kind = je_risk_criteria`, OQ-7): each names its key, its weight
and its parameters. Code evaluates them:

- `weekend_holiday`  posted on a Saturday or Sunday, or on a date in the published
  `legal_holidays` set whose version enters `inputs_hash` (reason `weekend` or `holiday`);
- `round_amount`     at least `at_least` and a whole multiple of `unit`;
- `post_close`       posted, or (where the ledger carries entry times) entered, after the period
  end and on or before `through`: the export runs through the post-close window;
- `manual_by_role`   a manual entry whose posting user's role class is listed (needs `posted_by`
  and `source`);
- `keywords`         a description holds one of the firm's words (whole words, any case).

A criterion whose fields the ledger does not carry is **unavailable**: it hits nothing and its
missing fields are named ("Not available from this ledger"). An entry's score is the sum of the
weights of the criteria it meets, capped at 100; a non-zero score always carries its reason codes
and a zero score none. Scores are ordered by score (high first), then reference, so the same
inputs give the same list. `inputs_hash` is the SHA-256 of the canonical inputs (criteria, the
holiday set version and dates, the role map, the entries), so a re-performer can prove a score
came from these inputs and this engine.

Imports only the standard library (the compute contract, A-03-T21).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

ENGINE_VERSION: Final = "je_scoring/1.0"
CriterionKey = Literal[
    "weekend_holiday", "round_amount", "post_close", "manual_by_role", "keywords"
]
ReasonCode = Literal[
    "weekend", "holiday", "round_amount", "post_close", "manual_by_role", "keyword"
]
RoleClass = Literal["senior_management", "accounting_staff", "system", "unknown"]
CRITERIA_ORDER: Final[tuple[CriterionKey, ...]] = (
    "weekend_holiday",
    "round_amount",
    "post_close",
    "manual_by_role",
    "keywords",
)
# The JE fields each criterion needs beyond the always-present posting date, amount and text.
NEEDS: Final[dict[CriterionKey, tuple[str, ...]]] = {
    "weekend_holiday": (),
    "round_amount": (),
    "post_close": (),  # the posting date always; the entry time where the ledger carries it
    "manual_by_role": ("posted_by", "source"),
    "keywords": (),
}
_MAX_SCORE: Final = 100


@dataclass(frozen=True)
class JeEntry:
    """One journal entry as scoring needs it (grouped by `ledger.api.journal_entries`)."""

    ref: str
    posted_on: date
    amount: Decimal  # the entry's total debit
    descriptions: tuple[str, ...] = ()
    posted_by: str | None = None
    entered_at: datetime | None = None
    source: Literal["manual", "system"] | None = None


@dataclass(frozen=True)
class Criterion:
    """One firm criterion: its key, weight (0 to 100) and parameters, as text from the policy."""

    key: CriterionKey
    weight: int
    params: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class HolidaySet:
    """The published `legal_holidays` reference set (K-02-T05) at one version."""

    version: str
    dates: frozenset[date]


@dataclass(frozen=True)
class Inputs:
    criteria: tuple[Criterion, ...]
    holidays: HolidaySet
    period_end: date
    # The posting user -> role class map the engagement team entered, with citations.
    roles: Mapping[str, RoleClass] = field(default_factory=dict[str, RoleClass])
    fields_available: frozenset[str] = frozenset()  # the snapshot's `je_fields_available`


@dataclass(frozen=True)
class CriterionResult:
    position: int
    key: CriterionKey
    available: bool
    missing_fields: tuple[str, ...]
    hit_count: int


@dataclass(frozen=True)
class Score:
    entry_ref: str
    score: int
    reason_codes: tuple[ReasonCode, ...]
    criteria_mask: int  # bit n set when CRITERIA_ORDER[n] hit


@dataclass(frozen=True)
class Scored:
    criteria: tuple[CriterionResult, ...]
    scores: tuple[Score, ...]  # every entry, by score then reference
    unique_flagged: int  # entries with a non-zero score
    engine_version: str
    inputs_hash: str


class InvalidCriteria(ValueError):
    """A policy the engine cannot evaluate (unknown key, a repeated key, a bad parameter)."""


def _words(text: str) -> re.Pattern[str] | None:
    cleaned = [re.escape(w.strip()) for w in text.split(",") if w.strip()]
    return re.compile(rf"\b(?:{'|'.join(cleaned)})\b", re.IGNORECASE) if cleaned else None


def _decimal(params: Mapping[str, str], name: str, default: str) -> Decimal:
    try:
        value = Decimal(params.get(name, default))
    except ArithmeticError as exc:
        raise InvalidCriteria(name) from exc
    if not value.is_finite() or value < 0:
        raise InvalidCriteria(name)
    return value


def _date(params: Mapping[str, str], name: str) -> date:
    try:
        return date.fromisoformat(params[name])
    except (KeyError, ValueError) as exc:
        raise InvalidCriteria(name) from exc


def _check(criteria: Sequence[Criterion]) -> None:
    keys = [c.key for c in criteria]
    if len(set(keys)) != len(keys) or any(k not in NEEDS for k in keys):
        raise InvalidCriteria("criteria")
    if any(not 0 <= c.weight <= _MAX_SCORE for c in criteria):
        raise InvalidCriteria("weight")


def available(key: CriterionKey, fields_available: frozenset[str]) -> tuple[bool, tuple[str, ...]]:
    """Whether the ledger carries what `key` needs, and which fields are missing."""
    missing = tuple(f for f in NEEDS[key] if f not in fields_available)
    return not missing, missing


def reasons_for(entry: JeEntry, c: Criterion, inputs: Inputs) -> tuple[ReasonCode, ...]:
    """The reason codes `c` gives this entry (empty when it does not hit)."""
    if c.key == "weekend_holiday":
        if entry.posted_on in inputs.holidays.dates:
            return ("holiday",)
        return ("weekend",) if entry.posted_on.weekday() >= 5 else ()
    if c.key == "round_amount":
        at_least = _decimal(c.params, "at_least", "0")
        unit = _decimal(c.params, "unit", "1000")
        whole = unit > 0 and entry.amount % unit == 0
        return ("round_amount",) if entry.amount >= at_least and whole else ()
    if c.key == "post_close":
        through = _date(c.params, "through")
        window = inputs.period_end, through
        posted_late = window[0] < entry.posted_on <= window[1]
        at = entry.entered_at if "entered_at" in inputs.fields_available else None
        entered_late = at is not None and window[0] < at.date() <= window[1]
        return ("post_close",) if posted_late or entered_late else ()
    if c.key == "manual_by_role":
        wanted = {r.strip() for r in c.params.get("role_class", "").split(",") if r.strip()}
        role = inputs.roles.get(entry.posted_by or "", "unknown")
        return ("manual_by_role",) if entry.source == "manual" and role in wanted else ()
    words = _words(c.params.get("words", ""))
    return ("keyword",) if words and any(words.search(d) for d in entry.descriptions) else ()


def inputs_hash(inputs: Inputs, entries: Iterable[JeEntry]) -> str:
    """SHA-256 over the canonical inputs: criteria, holiday set, role map, fields, entries."""
    doc = {
        "engine": ENGINE_VERSION,
        "criteria": [
            {"key": c.key, "weight": c.weight, "params": dict(sorted(c.params.items()))}
            for c in inputs.criteria
        ],
        "holidays": {
            "version": inputs.holidays.version,
            "dates": sorted(d.isoformat() for d in inputs.holidays.dates),
        },
        "period_end": inputs.period_end.isoformat(),
        "roles": dict(sorted(inputs.roles.items())),
        "fields": sorted(inputs.fields_available),
        "entries": sorted(
            (
                e.ref,
                e.posted_on.isoformat(),
                str(e.amount),
                list(e.descriptions),
                e.posted_by or "",
                e.entered_at.isoformat() if e.entered_at else "",
                e.source or "",
            )
            for e in entries
        ),
    }
    raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def score(inputs: Inputs, entries: Sequence[JeEntry]) -> Scored:
    """Evaluate every criterion on every entry; scores with reason codes; hit counts; the hash."""
    _check(inputs.criteria)
    ordered = sorted(inputs.criteria, key=lambda c: CRITERIA_ORDER.index(c.key))
    usable = {c.key: available(c.key, inputs.fields_available) for c in ordered}
    hits: dict[CriterionKey, int] = dict.fromkeys(CRITERIA_ORDER, 0)
    scores: list[Score] = []
    for entry in entries:
        total, mask = 0, 0
        reasons: list[ReasonCode] = []
        for c in ordered:
            if not usable[c.key][0]:
                continue
            found = reasons_for(entry, c, inputs)
            if found:
                hits[c.key] += 1
                total += c.weight
                mask |= 1 << CRITERIA_ORDER.index(c.key)
                reasons.extend(found)
        final = min(total, _MAX_SCORE) if reasons else 0
        scores.append(
            Score(entry.ref, final, tuple(reasons) if final else (), mask if final else 0)
        )
    scores.sort(key=lambda s: (-s.score, s.entry_ref))
    results = tuple(
        CriterionResult(i + 1, c.key, usable[c.key][0], usable[c.key][1], hits[c.key])
        for i, c in enumerate(ordered)
    )
    return Scored(
        criteria=results,
        scores=tuple(scores),
        unique_flagged=sum(1 for s in scores if s.score > 0),
        engine_version=ENGINE_VERSION,
        inputs_hash=inputs_hash(inputs, entries),
    )


def select_by_score(scored: Scored, score_min: int) -> tuple[str, ...]:
    """The entries at or above `score_min`, in score order (the selection's first part)."""
    return tuple(s.entry_ref for s in scored.scores if s.score >= score_min and s.score > 0)
