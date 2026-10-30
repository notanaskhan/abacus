"""The TY2025 practice board (T-02-T11; T-02 §3; blueprint 01 §9.5, §9.7; TPL-01, TAX-01):
the statuses, review levels, extensions, sync chips, due dates and the preparer and reviewer of
each of the 224 returns `binders.build_returns` rosters (214 engagements, 10 with two returns;
offices 98 / 64 / 62).

The named rows are TPL-01's (a, b) and §9.7 R1 to R30; the rest are settled by stable rank so
the §9.5 tiles foot: open 79 (2 / 8 / 9 / 17 / 15 / 11 / 7 / 10), done 145 (6 filed, 139
accepted), 161 extended. This is the same algorithm as the fixture seed
(`apps/web/src/fixtures/seed/tax/tax-returns.ts`), so the loaded tenant and fixture mode show
the same board; the golden footing tests hold both to these numbers. Values are synthetic
(AGENTS 16): due dates are what K-02's rules give TY2025, written as data here only for the demo
tenant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.binders import RETURNS, Return
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS, OfficeName
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "tax_board"
NEEDS: Final = ("binders",)  # the returns this board sets
Status = Literal[
    "not_started",
    "gathering",
    "preparing",
    "prepared",
    "in_review",
    "action_required",
    "approved",
    "awaiting_signature",
    "filed",
    "accepted",
]
Level = Literal["Detail", "Manager", "Partner"]

RETURNS_TOTAL: Final = 224
OPEN_TOTAL: Final = 79
EXTENDED_TOTAL: Final = 161
# §9.5, in tile order of the registry: open 79, done 145.
STATUS_COUNTS: Final[dict[Status, int]] = {
    "not_started": 2,
    "gathering": 8,
    "preparing": 9,
    "prepared": 17,
    "in_review": 15,
    "action_required": 11,
    "approved": 7,
    "awaiting_signature": 10,
    "filed": 6,
    "accepted": 139,
}
OPEN_STATUSES: Final = frozenset(
    {
        "not_started",
        "gathering",
        "preparing",
        "prepared",
        "in_review",
        "action_required",
        "approved",
        "awaiting_signature",
    }
)


@dataclass(frozen=True)
class Sync:
    code: Literal["not_yet_exported", "ready_for_export", "synced"]
    day: str | None = None  # "Sep 9" for a synced chip


NYE: Final = Sync("not_yet_exported")
RFE: Final = Sync("ready_for_export")


def synced(day: str) -> Sync:
    return Sync("synced", day)


@dataclass(frozen=True)
class Named:
    team: str  # "OB / SI"
    status: Status
    office: OfficeName | None = None
    level: Level | None = None
    issues: int | None = None
    sync: Sync | None = None
    extended: bool | None = None
    due: str | None = None  # ISO, when it is not the form's date
    tag: str | None = None
    envelope: str | None = None


# TPL-01 a and b, §9.7 R1 to R30, §9.3 (the fixture seed's NAMED, row for row).
NAMED: Final[dict[str, Named]] = {
    "Ridgeline Property Partners, LP": Named(
        office="New York", team="OB / SI", status="in_review", level="Partner", issues=11, sync=NYE
    ),
    "Harborview Dental Properties, LP": Named(
        office="New York", team="DS / TR", status="approved", sync=synced("Sep 11")
    ),
    "Northgate Medical Partners, LLP": Named(
        office="Chicago", team="BN / NA", status="in_review", level="Manager", issues=2, sync=NYE
    ),
    "Marlowe Street Holdings, LP": Named(
        office="New York", team="DS / TR", status="action_required", issues=3, sync=NYE
    ),
    "Kestrel Ventures Fund I, LP": Named(
        office="New York",
        team="NP / TR",
        status="awaiting_signature",
        sync=synced("Sep 11"),
        envelope="E3",
    ),
    "Bramble & Finch Design, LLC": Named(
        office="Chicago", team="GT / YK", status="prepared", issues=1, sync=NYE
    ),
    "Hollis Creek Veterinary, PC": Named(
        office="Denver", team="JL / OB", status="in_review", level="Detail", issues=2, sync=NYE
    ),
    "Pinecrest Pediatrics, PC": Named(
        office="Denver", team="LP / OB", status="approved", sync=RFE
    ),
    "Calloway Family Trust": Named(office="Chicago", team="KO / SI", status="prepared", sync=NYE),
    "Pryor Irrevocable Trust": Named(
        office="Chicago",
        team="MA / YK",
        status="awaiting_signature",
        sync=synced("Sep 10"),
        envelope="E4",
    ),
    "Jonah & Claire Feld": Named(
        office="New York",
        team="KO / SI",
        status="in_review",
        level="Manager",
        issues=4,
        sync=synced("Sep 10"),
    ),
    "Meera Shah": Named(
        office="Chicago", team="LP / SI", status="preparing", sync=NYE, tag="Waiting on K-1"
    ),
    "Ashford Manufacturing Co.": Named(
        office="Chicago", team="YK / NA", status="in_review", level="Manager", issues=2, sync=NYE
    ),
    "Elena Varga": Named(
        office="Chicago",
        team="LP / OB",
        status="awaiting_signature",
        sync=synced("Sep 8"),
        envelope="E1",
    ),
    "Estate of Walter Thornbury": Named(
        office="Chicago", team="BN / YK", status="gathering", sync=NYE
    ),
    "Larkspur Floral, Inc.": Named(
        office="Chicago", team="GT / YK", status="awaiting_signature", envelope="E7"
    ),
    "Thomas & Irene Kowal": Named(
        office="Chicago", team="MA / YK", status="awaiting_signature", envelope="E2"
    ),
    "Corinne Abbott": Named(
        office="Denver", team="JL / IM", status="awaiting_signature", envelope="E5"
    ),
    "Dev & Mira Kapoor": Named(
        office="New York", team="DS / QL", status="awaiting_signature", envelope="E6"
    ),
    "Hugo Brandvold": Named(
        office="Denver", team="NK / OB", status="awaiting_signature", envelope="E8"
    ),
    "Noor & Adam Farouk": Named(
        office="New York", team="RV / NP", status="awaiting_signature", envelope="E9"
    ),
    "Brightline Optics, Inc.": Named(
        office="Chicago", team="BN / NA", status="awaiting_signature", envelope="E10"
    ),
    "Mateo & Lucia Alvarez": Named(
        office="Chicago", team="BN / YK", status="accepted", extended=False
    ),
    "Priyanka & Sam Iyer": Named(
        office="New York", team="DS / QL", status="in_review", level="Manager"
    ),
    "Harold Stein": Named(office="Chicago", team="GT / YK", status="action_required"),
    "Wren & Avery Collins": Named(office="Denver", team="JL / IM", status="prepared"),
    "Gloria Mendez": Named(office="Denver", team="NK / OB", status="gathering"),
    "Benjamin Osterberg": Named(office="New York", team="RV / NP", status="preparing"),
    "Nina & Paul Haddox": Named(office="Chicago", team="PS / YK", status="approved"),
    "Rafael Quintero": Named(office="Denver", team="LW / OB", status="not_started"),
    "Sunil & Asha Rao": Named(
        office="New York", team="KO / QL", status="filed", sync=synced("Sep 11")
    ),
    "Cedar Hollow Farms, LLC": Named(office="Denver", team="JL / IM", status="accepted"),
    "Two Rivers Brewing Co.": Named(office="Denver", team="LW / IM", status="accepted"),
    "Summit Line Logistics, Inc.": Named(
        office="Chicago", team="BN / YK", status="filed", sync=synced("Sep 12")
    ),
    "Oakline Software, Inc.": Named(
        office="New York", team="QL / TR", status="in_review", level="Partner"
    ),
    "Meridian Tool & Die, Inc.": Named(office="Chicago", team="YK / NA", status="preparing"),
    "Fenwick Family Foundation": Named(office="Chicago", team="BN / NA", status="gathering"),
    "Riverbend Community Theater": Named(office="Denver", team="NK / IM", status="prepared"),
    "Estate of Eugene Barlow": Named(
        office="New York", team="RV / QL", status="in_review", level="Manager"
    ),
    "Delia Fortune": Named(office="Denver", team="LP / OB", status="accepted", extended=False),
    "Morgan & Kai Ferris": Named(office="New York", team="DS / NP", status="gathering"),
    "Aurelio Santos": Named(office="Chicago", team="PS / YK", status="action_required"),
    "Vantage Point Realty, LLC": Named(office="Chicago", team="GT / NA", status="accepted"),
    "Juliet Okonjo": Named(office="Chicago", team="BN / YK", status="prepared"),
    "Copperleaf Coffee Roasters, Inc.": Named(team="LW / IM", status="accepted", extended=False),
    "Marcus & Dana Whitley": Named(
        team="KO / SI", status="accepted", extended=False, sync=synced("Apr 10")
    ),
    "Bluestem Analytics, LLC": Named(team="QL / TR", status="accepted", extended=False),
    "Daniel & Ruth Okafor": Named(team="BN / YK", status="accepted", extended=False),
    "Lakeshore Literacy Alliance": Named(
        team="BN / NA", status="gathering", extended=False, due="2026-11-16"
    ),
}


@dataclass(frozen=True)
class Due:
    original: str
    extended: str
    rule: str


DUE: Final[dict[str, Due]] = {
    "1040": Due("2026-04-15", "2026-10-15", "15th day, 4th month + 6 months"),
    "1041": Due("2026-04-15", "2026-09-30", "15th day, 4th month + 5½ months"),
    "1065": Due("2026-03-16", "2026-09-15", "15th day, 3rd month + 6 months"),
    "1120-S": Due("2026-03-16", "2026-09-15", "15th day, 3rd month + 6 months"),
    "1120": Due("2026-04-15", "2026-10-15", "15th day, 4th month + 6 months"),
    "990": Due("2026-05-15", "2026-11-16", "15th day, 5th month + 6 months"),
    "990-PF": Due("2026-05-15", "2026-11-16", "15th day, 5th month + 6 months"),
}
_LEVELS: Final[tuple[Level, ...]] = ("Detail", "Manager", "Partner")
_SYNC_DAYS: Final = ("Sep 8", "Sep 9", "Sep 10", "Sep 11")
_LEVEL_CODE: Final[dict[Level, str]] = {
    "Detail": "detail",
    "Manager": "manager",
    "Partner": "partner",
}


@dataclass(frozen=True)
class BoardRow:
    label: str
    work_item_id: str
    client: str
    form: str
    office: OfficeName
    preparer: str  # initials
    reviewer: str
    status: Status
    level: Level | None
    issues: int | None
    sync: Sync
    due: date
    original_due: date
    extended_due: date
    extended: bool
    due_rule: str
    tag: str | None
    envelope: str | None

    @property
    def review_level(self) -> str | None:
        return None if self.level is None else _LEVEL_CODE[self.level]


def _rank(label: str) -> str:
    return stable_id(f"rank:{label}")


def _pick[T](items: tuple[T, ...], label: str, salt: str) -> T:
    if not items:
        raise ValueError(f"nothing to pick for {label}")
    return items[int(stable_id(f"{salt}:{label}")[:8], 16) % len(items)]


def _seats(office: OfficeName, role: str) -> tuple[str, ...]:
    return tuple(s.initials for s in SEATS if s.office == office and s.role == role)


def _named(r: Return) -> Named | None:
    return None if r.label.endswith(":2") else NAMED.get(r.client)


def build_board(returns: tuple[Return, ...] = RETURNS) -> tuple[BoardRow, ...]:
    named = [(r, n) for r in returns if (n := _named(r)) is not None]
    left = dict(STATUS_COUNTS)
    for _, n in named:
        left[n.status] -= 1
    queue: list[Status] = [st for st in STATUS_COUNTS for _ in range(max(0, left[st]))]
    unnamed = sorted((r for r in returns if _named(r) is None), key=lambda r: _rank(r.label))
    status_of: dict[str, Status] = {
        r.label: (queue[i] if i < len(queue) else "accepted") for i, r in enumerate(unnamed)
    }
    named_extended = sum(1 for _, n in named if n.extended is not False)
    extend_left = (
        EXTENDED_TOTAL
        - named_extended
        - sum(1 for r in unnamed if status_of[r.label] in OPEN_STATUSES)
    )
    level_at = 0
    rows: list[BoardRow] = []
    for r in returns:
        n = _named(r)
        status: Status = n.status if n is not None else status_of.get(r.label, "accepted")
        is_open = status in OPEN_STATUSES
        if n is not None:
            extended = n.extended is not False
        elif is_open:
            extended = True
        else:
            extended = extend_left > 0
            if extended:
                extend_left -= 1
        rule = DUE[r.form]
        office: OfficeName = (n.office if n is not None and n.office else None) or r.office
        if n is not None:
            preparer, reviewer = n.team.split(" / ")
        else:
            preparer = _pick(_seats(office, "Tax Preparer"), r.label, "prep")
            reviewer = _pick(_seats(office, "Tax Reviewer"), r.label, "rev")
        level = n.level if n is not None else None
        if status == "in_review" and level is None:
            level = _LEVELS[level_at % len(_LEVELS)]
            level_at += 1
        sync = (n.sync if n is not None else None) or (
            (RFE if status == "approved" else NYE)
            if is_open
            else synced(_pick(_SYNC_DAYS, r.label, "sync"))
        )
        due = (n.due if n is not None else None) or (rule.extended if extended else rule.original)
        rows.append(
            BoardRow(
                label=r.label,
                work_item_id=r.id,
                client=r.client,
                form=r.form,
                office=office,
                preparer=preparer,
                reviewer=reviewer,
                status=status,
                level=level,
                issues=n.issues if n is not None else None,
                sync=sync,
                due=date.fromisoformat(due),
                original_due=date.fromisoformat(rule.original),
                extended_due=date.fromisoformat(rule.extended),
                extended=extended,
                due_rule=rule.rule if extended else re.sub(r" \+ .*$", "", rule.rule),
                tag=n.tag if n is not None else None,
                envelope=n.envelope if n is not None else None,
            )
        )
    return tuple(rows)


BOARD: Final = build_board()
BOARD_BY_LABEL: Final = {row.label: row for row in BOARD}


@register_slice(SLICE)
def _tax_board_slice() -> list[Event]:
    return [
        Event(
            f"tax-return-board:{row.label}",
            SETUP_AT,
            "tax.return_board_set",
            "system",
            SLICE,
            {"return": row.label},
            client=row.client,
        )
        for row in BOARD
    ]


__all__ = [
    "BOARD",
    "BOARD_BY_LABEL",
    "EXTENDED_TOTAL",
    "NEEDS",
    "OPEN_TOTAL",
    "RETURNS_TOTAL",
    "SLICE",
    "STATUS_COUNTS",
    "BoardRow",
    "build_board",
]
