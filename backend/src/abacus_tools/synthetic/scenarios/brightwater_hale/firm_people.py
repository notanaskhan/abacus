"""The `people` slice (G-01-T06; G-01 sections 3.3 to 3.5, 5.3; ADM-02 a-d): what ADM-01 and
ADM-02 need from the live seed, as events the loader replays through identity's services.

- **Seats.** The firm's provisioned seat total, 46 (`plan.seats`, DEC-285): "46 of 46 · Full".
- **Each seat holder's profile** (ADM-02's 46 rows, in its order): the role template from the
  ADM-02 Role column; the level from the row's band (PARTNERS 7 · MANAGERS & REVIEWERS 7 ·
  SENIORS 11 · STAFF & PREPARERS 14 · SEASONAL 5 · OPERATIONS 2); the title (`/v1/me`'s job
  title where SHL-03 gives one, else the ADM-02 line, so a person has one title); the team and
  its service line; seasonal access ending Sat Oct 31, 2026; offshore off. Felix Andersen's
  IT / Security template carries `security_admin` (ADM-01e), so Grace Holloway is the firm admin.
- **Teams** (ADM-03a): Audit & assurance 16 · Tax 21 · Client accounting 7 · Firm operations 2
  = 46. Teams have no service yet (G-01-T08), so the loader bootstraps their rows as it does
  offices; who is on them goes through identity's profile service.

Waiting on later rows (so fixture-only for now, in `apps/web/src/fixtures/seed/firm-people.ts`):
the groups (EQR pool, Monitoring reviewers, Seasonal) need team kinds (T08); office addresses,
leads, codes and pools (T08); the three walls' reasons and approvers (T09); service-line
policies (T12); the Nov 2 deactivations (T13's access-end job); Lena Park's Mon Jan 5, 2026
invitation (it predates the firm's setup on the timeline, as POR-02b's history does, DEC-213).

Opt-in (`--slice people`); `build()` keeps its default, so SCENARIO_HASH is unchanged. Mirrors
apps/web/src/fixtures/seed/firm-people.ts.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    JOB_TITLES,
    SEATS,
    Seat,
    SeatRole,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "people"
BY: Final = "GH"  # J01 step 3: Grace Holloway sets the firm's people up
SEATS_TOTAL: Final = 46
SEASON_ENDS: Final = date(2026, 10, 31)

Template = Literal[
    "partner",
    "manager",
    "tax_reviewer",
    "senior",
    "staff",
    "tax_preparer",
    "firm_admin",
    "it_security",
]
Level = Literal["partner", "manager", "senior", "staff", "seasonal", "admin"]
TeamName = Literal["Audit & assurance", "Tax", "Client accounting", "Firm operations"]

TEMPLATE_OF_ROLE: Final[dict[SeatRole, Template]] = {
    "Partner": "partner",
    "Manager": "manager",
    "Tax Reviewer": "tax_reviewer",
    "Senior": "senior",
    "Staff": "staff",
    "Tax Preparer": "tax_preparer",
    "Firm Admin": "firm_admin",
    "IT / Security": "it_security",
}
# ADM-02a's bands, in order, with their row counts (the band is the level).
BANDS: Final[tuple[tuple[Level, int], ...]] = (
    ("partner", 7),
    ("manager", 7),
    ("senior", 11),
    ("staff", 14),
    ("seasonal", 5),
    ("admin", 2),
)
TEAMS: Final[tuple[TeamName, ...]] = (
    "Audit & assurance",
    "Tax",
    "Client accounting",
    "Firm operations",
)
# ADM-02a's "Team · groups" column; rows without one take their role line's team.
_NOT_TAX: Final[dict[TeamName, frozenset[str]]] = {
    "Audit & assurance": frozenset(
        {"MO", "TW", "CM", "HL", "LK", "OH", "MD", "CD", "JB", "SB", "AC", "AW", "FN", "KR"}
        | {"CH", "HP"}
    ),
    "Client accounting": frozenset({"PR", "HV", "RM", "EW", "RF", "IV", "EG"}),
    "Firm operations": frozenset({"GH", "FA"}),
}
SERVICE_LINE_OF_TEAM: Final[dict[TeamName, str | None]] = {
    "Audit & assurance": "audit",
    "Tax": "tax",
    "Client accounting": "cas",
    "Firm operations": None,
}
# ADM-03a's groups (G-01-T08 loads them once teams have kinds); fixture data until then.
GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "EQR pool": ("TW", "CM"),
    "Monitoring reviewers": ("TW", "CM", "LK", "IM", "TR"),
    "Seasonal": ("LP", "MA", "PS", "NK", "RV"),
}


def level_of(seat: Seat) -> Level:
    end = 0
    for level, size in BANDS:
        end += size
        if seat.n <= end:
            return level
    raise ValueError(f"seat {seat.n} is outside the 46")


def team_of(seat: Seat) -> TeamName:
    for team, members in _NOT_TAX.items():
        if seat.initials in members:
            return team
    return "Tax"


def title_of(seat: Seat) -> str:
    """One title per person: SHL-03's where it gives one (`/v1/me`), else ADM-02's line."""
    return JOB_TITLES.get(seat.initials, seat.title)


def access_ends_of(seat: Seat) -> date | None:
    return SEASON_ENDS if level_of(seat) == "seasonal" else None


@register_slice(SLICE)
def people_events() -> list[Event]:
    events = [
        Event(
            "plan:seats",
            SETUP_AT,
            "identity.seats_provisioned",
            "system",
            SLICE,
            {"seats": SEATS_TOTAL},
        ),
    ]
    events += [
        Event(f"team:{slug_of(t)}", SETUP_AT, "organisations.team_created", BY, SLICE, {"name": t})
        for t in TEAMS
    ]
    events += [
        Event(
            f"profile:{slug_of(s.name)}",
            SETUP_AT,
            "identity.member_profile_set",
            BY,
            SLICE,
            {
                "initials": s.initials,
                "template": TEMPLATE_OF_ROLE[s.role],
                "level": level_of(s),
                "title": title_of(s),
                "team": team_of(s),
            },
        )
        for s in SEATS
    ]
    return events
