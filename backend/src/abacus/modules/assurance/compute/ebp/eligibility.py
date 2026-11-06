"""The EBP eligibility engine (A-05-T20; A-05 §3 F4; ADR-050; DEC-2066). Pure: no clock, no I/O.

Code computes every eligibility figure EBP-03 shows; the model only reads the HR record's fields
(mode `ebp_attribute`), and a person concludes each row.

- **Entry** (the verified provision, never the draft; `EntryRule`, read by `entry_rule_from`): the
  first of the month following the later of the participant's birthday at the minimum age and hire
  plus the service months (21 and 3 on Northwind; a birthday on Feb 29 counts from Feb 28 in a
  common year; hire plus the months keeps the day, clamped to the month's end).
- **Auto-escalation** (QACA): the default rate, plus the step for each plan year after the year of
  entry, to the cap (6% + 1% a year to 15%: a 2023 entrant is at 8% for 2025, a 2025 entrant 6%).
- **Missed amounts** (a missed auto-enrollment): the missed deferral at the default rate and the
  missed QACA match at 3.5% (100% of the first 1% and 50% of the next 5%), each of compensation,
  half up to the cent: $41,200 gives 2,472.00 and 1,442.00.
- **Review**: when the census and the HR record disagree on a date, the row needs a person; if
  both dates give the same entry, code says so ("no effect on entry") for the person to confirm.
- **Population** (`eligible_not_enrolled_no_optout`): every participant whose entry is on or before
  the plan year's end, who never deferred, and who has no opt-out on file.

Every result carries `engine_name`, `engine_version` and the SHA-256 `inputs_hash`.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Final

from abacus.kernel.numeric import CONTEXT, quantize_half_up
from abacus.modules.assurance.compute.ebp.provisions import normalise

ENGINE_NAME: Final = "ebp_eligibility"
ENGINE_VERSION: Final = "1"
QACA_MATCH_PCT: Final = Decimal("3.5")  # 100% of 1% + 50% of the next 5%
_HUNDRED: Final = Decimal(100)


@dataclass(frozen=True)
class Escalation:
    default_pct: Decimal = Decimal(6)
    step_pct: Decimal = Decimal(1)
    cap_pct: Decimal = Decimal(15)


QACA: Final = Escalation()


@dataclass(frozen=True)
class EntryRule:
    """A plan's entry rule. EBP-03 builds it from the verified provisions; the default is
    Northwind's, the engine's own golden figures."""

    minimum_age: int = 21
    service_months: int = 3


STANDARD_RULE: Final = EntryRule()
ENTRY_RULE_KEYS: Final = ("minimum_age", "service_requirement", "entry_dates")
# Checked on the raw wording: `normalise` strips symbols, so "<21", "≠21" or "-3 months" would read
# as a value.
_READABLE: Final = re.compile(r"[A-Za-z0-9 (),.]+")
_AGE: Final = re.compile(r"(?:age )?([0-9]{1,2})(?: year)?(?: old)?")
_SERVICE: Final = re.compile(r"([0-9]{1,2}) month(?: of)?(?: elapsed time| service)?")
_ENTRY_DATES: Final = frozenset(
    {"first of month following", "first of month following eligibility"}
)


@dataclass(frozen=True)
class Entry:
    eligible_on: date  # the later of the minimum age and hire plus the service months
    entry_on: date
    service_on: date  # hire plus the service months: what may be shown (DEC-2225)
    inputs_hash: str
    engine_name: str = ENGINE_NAME
    engine_version: str = ENGINE_VERSION


@dataclass(frozen=True)
class Missed:
    deferral: Decimal
    match: Decimal
    inputs_hash: str


@dataclass(frozen=True)
class Review:
    requires_review: bool
    no_effect: bool  # both dates give the same entry
    note: str | None


@dataclass(frozen=True)
class Participant:
    ref: str
    dob: date
    hire_date: date
    ever_deferred: bool
    opt_out_on_file: bool


def _hash(kind: str, **parts: object) -> str:
    body = json.dumps(
        {"engine": ENGINE_NAME, "version": ENGINE_VERSION, "kind": kind}
        | {k: v.isoformat() if isinstance(v, date) else str(v) for k, v in parts.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def birthday(dob: date, years: int) -> date:
    year = dob.year + years
    if dob.month == 2 and dob.day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, dob.month, dob.day)


def first_of_following_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def entry_rule_from(provisions: Mapping[str, str]) -> EntryRule | None:
    """The rule the verified wording states, or None: a wording code cannot read exactly (quarterly
    entry dates, a year of service in hours) is left for a person, never guessed at."""
    raw = [provisions.get(key, "") for key in ENTRY_RULE_KEYS]
    if not all(_READABLE.fullmatch(wording) for wording in raw):
        return None
    age = _AGE.fullmatch(normalise(raw[0]))
    service = _SERVICE.fullmatch(normalise(raw[1]))
    if age is None or service is None:
        return None
    if normalise(raw[2]) not in _ENTRY_DATES:
        return None
    return EntryRule(int(age.group(1)), int(service.group(1)))


def entry(dob: date, hire_date: date, rule: EntryRule = STANDARD_RULE) -> Entry:
    served = add_months(hire_date, rule.service_months)
    eligible = max(birthday(dob, rule.minimum_age), served)
    return Entry(
        eligible,
        first_of_following_month(eligible),
        served,
        _hash(
            "entry",
            dob=dob,
            hire=hire_date,
            minimum_age=rule.minimum_age,
            service_months=rule.service_months,
        ),
    )


def escalation_rate(entry_on: date, plan_year: int, rule: Escalation = QACA) -> Decimal:
    """The expected deferral rate for `plan_year` (0 before entry)."""
    if entry_on.year > plan_year:
        return Decimal(0)
    with localcontext(CONTEXT):
        return min(rule.default_pct + rule.step_pct * (plan_year - entry_on.year), rule.cap_pct)


def missed(compensation: Decimal, rule: Escalation = QACA) -> Missed:
    with localcontext(CONTEXT):
        deferral = quantize_half_up(compensation * rule.default_pct / _HUNDRED, 2)
        match = quantize_half_up(compensation * QACA_MATCH_PCT / _HUNDRED, 2)
    return Missed(deferral, match, _hash("missed", comp=compensation, rate=rule.default_pct))


def review(dob: date, census_hire: date, hr_hire: date, rule: EntryRule = STANDARD_RULE) -> Review:
    if census_hire == hr_hire:
        return Review(False, False, None)
    same = entry(dob, census_hire, rule).entry_on == entry(dob, hr_hire, rule).entry_on
    return Review(
        True, same, "No effect on entry: both dates give the same entry date" if same else None
    )


def eligible_not_enrolled_no_optout(
    participants: Sequence[Participant], plan_year_end: date
) -> tuple[str, ...]:
    """The auto-enrollment finding's population: entered by year end, never deferred, no opt-out
    on file."""
    return tuple(
        p.ref
        for p in participants
        if entry(p.dob, p.hire_date).entry_on <= plan_year_end
        and not p.ever_deferred
        and not p.opt_out_on_file
    )
