"""The weekly W4 and W5 read (Q-04-T050; chapter 11 §11.6.2; thresholds.md rules 4 to 6).

`wedge_read(tenant_id, week_start)` reads one firm's `pilot_metric_snapshots` for the
ISO week (Q-04-T008 wrote them; this only reads), and gives each signal its value, the counts
behind it and its colour by chapter 11's thresholds:

- **W4 portal activation** (`w4_portal_activation.v1`): green ≥ 80%, amber 50-79%, red < 50%
  once the firm's earliest live enrolment has run four weeks (before that, a low value is amber:
  the window has not had its four weeks). The plan's "at ≥ 2 firms" is the cross-firm rule
  (`cross_firm`): one firm alone below 50% stays amber, with that note.
- **W5 PBC through the portal** (`w5_pbc_via_portal.v1`): green ≥ 70%, amber 40-69%, red < 40%.

A firm's value is the mean of its enrolments' week values (each enrolment counted once), and the
read keeps every enrolment's value and how many there were: a read without counts is not a read.
A signal with no snapshot is "no data", never a colour. Each amber or red carries chapter 11's
owner (AY) and the action the plan names for it, so the sprint review gets an owner and an action
for every amber (the row's acceptance). Read only, as the platform in the firm's tenant; a
synthetic firm's read is labelled synthetic (DEC-1530), never a live firm's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import firm_name, is_synthetic_firm
from abacus.modules.platform.pilot_metrics import NotAMonday

Colour = Literal["green", "amber", "red", "no data"]
Signal = Literal["W4", "W5"]

METRIC: Final[dict[Signal, str]] = {
    "W4": "w4_portal_activation.v1",
    "W5": "w5_pbc_via_portal.v1",
}
TITLE: Final[dict[Signal, str]] = {
    "W4": "Portal activation: invited client contacts who sign in",
    "W5": "PBC items delivered through the portal",
}
# Chapter 11 §11.6.2: (green from, amber from); below amber is red.
BANDS: Final[dict[Signal, tuple[Decimal, Decimal]]] = {
    "W4": (Decimal("0.80"), Decimal("0.50")),
    "W5": (Decimal("0.70"), Decimal("0.40")),
}
W4_RED_AFTER_WEEKS: Final = 4
OWNER: Final = "AY"  # chapter 11 §11.6.2's owner for W4 and W5
ACTION: Final[dict[tuple[Signal, Colour], str]] = {
    ("W4", "amber"): (
        "Re-invite the client contacts who have not signed in and ask the partner to raise it "
        "at the next status call; read again next week."
    ),
    ("W5", "amber"): (
        "Move the open PBC requests onto the published portal binder and chase them through "
        "the portal reminders; read again next week."
    ),
    ("W4", "red"): (
        "Kill-or-pivot review against the pivot menu (chapter 11 §11.6.3, P1) by M14."
    ),
    ("W5", "red"): (
        "Kill-or-pivot review against the pivot menu (chapter 11 §11.6.3, P1) by M14."
    ),
}
SINGLE_FIRM_NOTE: Final = "below 50% at one firm only: red needs at least two firms (amber here)"


@dataclass(frozen=True)
class SignalRead:
    signal: Signal
    value: Decimal | None
    enrolments: int
    values: tuple[Decimal, ...]
    colour: Colour
    owner: str | None
    action: str | None
    note: str | None = None


@dataclass(frozen=True)
class FirmRead:
    firm_id: UUID
    firm_name: str
    synthetic: bool
    week_start: date
    weeks_live: int
    signals: tuple[SignalRead, ...]


def colour(signal: Signal, value: Decimal | None, weeks_live: int) -> Colour:
    if value is None:
        return "no data"
    green, amber = BANDS[signal]
    if value >= green:
        return "green"
    if value >= amber:
        return "amber"
    if signal == "W4" and weeks_live < W4_RED_AFTER_WEEKS:
        return "amber"  # W4 is red only after four weeks
    return "red"


def _signal(signal: Signal, values: Sequence[Decimal], weeks_live: int) -> SignalRead:
    value = (sum(values, Decimal(0)) / len(values)).quantize(Decimal("0.0001")) if values else None
    found = colour(signal, value, weeks_live)
    flagged = found in ("amber", "red")
    return SignalRead(
        signal,
        value,
        len(values),
        tuple(values),
        found,
        OWNER if flagged else None,
        ACTION[(signal, found)] if flagged else None,
    )


_SNAPSHOTS = text(
    "SELECT metric_key, value FROM pilot_metric_snapshots WHERE period_start = :start "
    "AND metric_key = ANY(:keys) AND subject_id IS NULL ORDER BY enrolment_id"
)
_FIRST_START = text(
    "SELECT min(window_start) FROM pilot_enrolments WHERE mode <> 'exited' "
    "AND window_start <= :end AND window_end >= :start"
)


async def wedge_read(tenant_id: UUID, week_start: date) -> FirmRead:
    """One firm's W4 and W5 for the ISO week starting `week_start` (a Monday)."""
    if week_start.isoweekday() != 1:
        raise NotAMonday(str(week_start))
    end = week_start + timedelta(days=6)
    tenant = TenantContext(tenant_id, "system", "pilot_read")
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(_SNAPSHOTS, {"start": week_start, "keys": list(METRIC.values())})
        ).all()
        first = (await session.execute(_FIRST_START, {"start": week_start, "end": end})).scalar()
    weeks_live = 0 if first is None else max(0, (end - first).days // 7 + 1)
    signals = tuple(
        _signal(
            signal,
            [Decimal(r.value) for r in rows if r.metric_key == key],
            weeks_live,
        )
        for signal, key in METRIC.items()
    )
    # The firm's name and synthetic mark are identity's (`identity.api`), never read here.
    name = await firm_name(tenant_id)
    synthetic = await is_synthetic_firm(tenant)
    return FirmRead(tenant_id, name, synthetic, week_start, weeks_live, signals)


def cross_firm(reads: Sequence[FirmRead]) -> tuple[FirmRead, ...]:
    """Chapter 11's "< 50% after 4 weeks at ≥ 2 firms": W4 red stands only when at least two
    firms read red; one firm alone stays amber, with the note and the amber action."""
    red_firms = sum(1 for r in reads for s in r.signals if s.signal == "W4" and s.colour == "red")
    if red_firms >= 2:
        return tuple(reads)
    out: list[FirmRead] = []
    for read in reads:
        signals = tuple(
            replace(s, colour="amber", action=ACTION[("W4", "amber")], note=SINGLE_FIRM_NOTE)
            if s.signal == "W4" and s.colour == "red"
            else s
            for s in read.signals
        )
        out.append(replace(read, signals=signals))
    return tuple(out)


def _percent(value: Decimal | None) -> str:
    return "—" if value is None else f"{(value * 100).quantize(Decimal('0.1'))}%"


def report(reads: Sequence[FirmRead]) -> str:
    """The read as Markdown for the sprint review: per firm and signal, the value, the counts
    behind it, the colour, and the owner and action for every amber or red."""
    lines = [
        "| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner "
        "| Action |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for read in reads:
        name = f"{read.firm_name} (synthetic)" if read.synthetic else read.firm_name
        for s in read.signals:
            values = ", ".join(_percent(v) for v in s.values) or "none"
            action = s.action or ""
            if s.note:
                action = f"{action} ({s.note})"
            lines.append(
                f"| {name} | {read.week_start.isoformat()} | {read.weeks_live} | "
                f"{s.signal} {TITLE[s.signal]} | {_percent(s.value)} | {s.enrolments} ({values}) "
                f"| {s.colour} | {s.owner or ''} | {action} |"
            )
    return "\n".join(lines) + "\n"
