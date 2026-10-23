"""The E0 audit-core slice's engagement content (F-04-T20; F-04.10; SPEC-307 AC-1).

- The 27 audits and assurance engagements of blueprint 01 §9.7 (A1 to A27): EBP 14 · FS audit
  6 · Review 4 · Compilation and preparation 3, at the phases Planning 7 · Fieldwork 9 · In review
  6 · Ready to release 2 · Released 3 (the C2 `audit_engagement` codes), each with its team.
- Northwind's PBC list (24 requests, 11 received: "11 of 24", DF-34) and Granite Peak's FS PBC
  list (41 requests, all still draft while the engagement letter is out, ENG-01 / G3).
- The portal minimum's client people of Northwind and Granite Peak (blueprint §9.3): Dana
  Kowalski and Luis Ferrante as owners, the benefits committee (Victoria Lam, Robert Haines) as
  `tcwg`. Sam Ortiz's (Keystone) pending invitation is the `portal` slice's (P-08-T14).
- The firm setting `staff_can_accept_evidence` on (DEC-37).

Mirrors `apps/web/src/fixtures/seed/{audits,requests,portal}.ts` row for row, with the same
draws, so the fixtures and a loaded tenant agree until F-04-T31 exports one from the other.
Nothing here reads a clock, the environment or a file.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS, slug_of
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import Rng, stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "audit_core"
AuditPhase = Literal["planning", "fieldwork", "in_review", "ready_to_release", "released"]
EngagementType = Literal["ebp_audit", "fs_audit", "review", "compilation", "preparation"]
EngagementStatus = Literal["accepted", "active", "delivered", "archived"]
TeamRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]
RequestStatus = Literal["draft", "requested", "uploaded", "received"]

_CAL_2025: Final = (date(2025, 1, 1), date(2025, 12, 31))
_FYE_JUN_2026: Final = (date(2025, 7, 1), date(2026, 6, 30))


def on_date(day: date, hour_utc: int = 15) -> datetime:
    """`onDate` of the TS seed: a calendar date at a fixed UTC hour."""
    return datetime(day.year, day.month, day.day, hour_utc, tzinfo=UTC)


def days_before(days: int, hour_utc: int = 15) -> datetime:
    """`daysBefore` of the TS seed: the UTC date `days` before the demo instant, at an hour."""
    return on_date((DEMO_INSTANT.astimezone(UTC) - timedelta(days=days)).date(), hour_utc)


@dataclass(frozen=True)
class Audit:
    n: int  # A1 to A27, the §9.7 row
    client: str  # the client's name as the clients module spells it
    name: str
    type: EngagementType
    period: tuple[date, date]
    phase: AuditPhase
    ep: str  # the engagement partner's initials
    status: EngagementStatus
    entity: str | None = None  # the engagement's entity, when it is not the client itself
    created: date | None = None  # an exact creation date when the handoff gives one
    due_on: date | None = None

    @property
    def label(self) -> str:
        return f"A{self.n}"

    @property
    def id(self) -> str:
        return stable_id(f"engagement:{self.label}")

    @property
    def entity_name(self) -> str:
        return self.entity or self.client


def _ebp(n: int, client: str, phase: AuditPhase, ep: str, **extra: object) -> Audit:
    status: EngagementStatus = "delivered" if phase == "released" else "active"
    base = Audit(n, client, "PY2025 EBP Audit", "ebp_audit", _CAL_2025, phase, ep, status)
    return replace(base, **extra)


def _fs(
    n: int,
    client: str,
    phase: AuditPhase,
    ep: str,
    period: tuple[date, date],
    name: str,
    **extra: object,
) -> Audit:
    status: EngagementStatus = "delivered" if phase == "released" else "active"
    return replace(Audit(n, client, name, "fs_audit", period, phase, ep, status), **extra)


def _review(n: int, client: str, phase: AuditPhase, ep: str, **extra: object) -> Audit:
    base = Audit(n, client, "FY2026 SSARS Review", "review", _FYE_JUN_2026, phase, ep, "active")
    return replace(base, **extra)


_FY26: Final = "FY2026 FS Audit"
# Blueprint 01 §9.7 "Audits & assurance (27)", in row order; names, periods and dates as the TS
# seed (audits.ts) has them. Released maps to Delivered, and to Archived once the archive lock is
# on (A4 and A20, the two Archived engagements of ENG-01). A2 and A7 stay Accepted: their
# letters are out (E14, E11), so G3 is not met.
AUDITS: Final[tuple[Audit, ...]] = (
    _ebp(
        1,
        "Northwind Robotics, Inc.",
        "planning",
        "MO",
        entity="Northwind Robotics 401(k) Plan",
        created=date(2026, 5, 28),
        due_on=date(2026, 10, 9),
    ),
    _fs(
        2,
        "Granite Peak Outdoor Supply, Inc.",
        "planning",
        "MO",
        _FYE_JUN_2026,
        _FY26,
        status="accepted",
        created=date(2026, 8, 31),
    ),
    _review(
        3,
        "Lakeshore Literacy Alliance",
        "fieldwork",
        "CM",
        due_on=date(2026, 10, 30),
        created=date(2026, 7, 20),
    ),
    Audit(
        4,
        "Juniper & Oak Interiors, LLC",
        "FY2025 Preparation (AR-C 70)",
        "preparation",
        _CAL_2025,
        "released",
        "PR",
        "archived",
        created=date(2026, 1, 12),
    ),
    _ebp(5, "Cobalt Ridge Manufacturing 401(k) Plan", "ready_to_release", "TW"),
    _ebp(6, "Halden Health 403(b) Plan", "ready_to_release", "CM"),
    _ebp(
        7,
        "Fairhaven Foods 401(k) Plan",
        "planning",
        "MO",
        status="accepted",
        created=date(2026, 9, 8),
    ),
    _ebp(8, "Sterling Freight 401(k) Plan", "fieldwork", "TW"),
    _ebp(9, "Westbrook Engineering 401(k) Plan", "fieldwork", "CM"),
    _ebp(10, "Arbor Senior Living 401(k) Plan", "fieldwork", "MO"),
    _ebp(11, "Keel & Compass Marine 401(k) Plan", "in_review", "TW"),
    _ebp(12, "Redtail Construction 401(k) Plan", "in_review", "CM"),
    _ebp(13, "Clearwater Credit Union 401(k) Plan", "fieldwork", "MO"),
    _ebp(
        14,
        "Granite Peak Outdoor Supply, Inc.",
        "fieldwork",
        "MO",
        entity="Granite Peak Outdoor Supply 401(k) Plan",
    ),
    _ebp(15, "Hearthstone Hospitality 401(k) Plan", "in_review", "TW"),
    _ebp(16, "Bayside Electric Cooperative 401(k) Plan", "released", "CM"),
    _ebp(17, "Tamarack Health System 403(b) Plan", "planning", "CM"),
    _fs(18, "Larimer Cooperative Grocery", "planning", "TW", _FYE_JUN_2026, _FY26),
    _fs(19, "Sable Creek Homeowners Association", "fieldwork", "CM", _FYE_JUN_2026, _FY26),
    _fs(
        20,
        "Meridian Tool & Die, Inc.",
        "released",
        "MO",
        _CAL_2025,
        "FY2025 FS Audit",
        status="archived",
    ),
    _fs(21, "Halcyon Foods Distribution, Inc.", "planning", "TW", _FYE_JUN_2026, _FY26),
    _fs(
        22,
        "Oakline Software, Inc.",
        "in_review",
        "CM",
        (date(2025, 4, 1), date(2026, 3, 31)),
        _FY26,
    ),
    _review(23, "Riverbend Community Theater", "planning", "CM"),
    _review(24, "Hillcrest Montessori School", "fieldwork", "TW"),
    _review(25, "Wildflower Land Trust", "in_review", "CM"),
    Audit(
        26,
        "Fenwick Family Foundation",
        "FY2025 Compilation (AR-C 80)",
        "compilation",
        _CAL_2025,
        "fieldwork",
        "PR",
        "active",
    ),
    Audit(
        27,
        "Kettle & Kiln Pottery, LLC",
        "FY2025 Preparation (AR-C 70)",
        "preparation",
        _CAL_2025,
        "in_review",
        "PR",
        "active",
    ),
)
BY_LABEL: Final = {a.label: a for a in AUDITS}

# Team pools (audits.ts). Northwind's five are named in the handoff (AUD-03 rail).
_AUDIT_MANAGERS: Final = ("LK", "OH")
_AUDIT_SENIORS: Final = ("CD", "JB", "SB")
_AUDIT_STAFF: Final = ("AW", "FN", "KR", "CH", "HP")
_CAS_SENIORS: Final = ("EW", "RF")
_CAS_STAFF: Final = ("IV", "EG")
_INITIALS: Final = frozenset(s.initials for s in SEATS)


def team_of(audit: Audit) -> tuple[tuple[str, TeamRole], ...]:
    """(initials, engagement role), in the TS seed's order and with its draws."""
    if audit.n == 1:
        return (
            ("MO", "engagement_partner"),
            ("HL", "manager"),
            ("MD", "senior"),
            ("AC", "staff"),
            ("TW", "reviewer"),
        )
    rng = Rng(f"team:{audit.n}")
    cas = audit.ep == "PR"
    team: list[tuple[str, TeamRole]] = [(audit.ep, "engagement_partner")]
    if not cas:
        team.append((rng.pick(_AUDIT_MANAGERS), "manager"))
    team.append((rng.pick(_CAS_SENIORS if cas else _AUDIT_SENIORS), "senior"))
    team.append((rng.pick(_CAS_STAFF if cas else _AUDIT_STAFF), "staff"))
    if audit.n == 22:
        team.append(("TW", "reviewer"))  # A22: "EQR TW"
    return tuple(team)


def created_at(audit: Audit) -> datetime:
    """`createdAt` of audits.ts: the handoff's date, else a seeded number of days before E0."""
    if audit.created is not None:
        return on_date(audit.created)
    rng = Rng(f"created:{audit.n}")
    late = audit.phase in ("released", "ready_to_release")
    return days_before(rng.integer(120, 300) if late else rng.integer(30, 240))


# --- the portal minimum (portal.ts) -------------------------------------------------------------

SINK_DOMAIN: Final = "sink.brightwaterhale.test"
GrantRole = Literal["owner", "contributor", "tcwg"]


@dataclass(frozen=True)
class PortalUser:
    name: str
    org: str
    title: str
    engagement: str  # the audit label the grant is scoped to
    role: GrantRole  # client_admin is an `owner` grant (identity GRANT_ROLE_OF)

    @property
    def slug(self) -> str:
        return slug_of(self.name)

    @property
    def email(self) -> str:
        return f"{self.slug.replace('-', '.')}@{SINK_DOMAIN}"

    @property
    def id(self) -> str:
        return stable_id(f"user:{self.slug}")


PORTAL_USERS: Final[tuple[PortalUser, ...]] = (
    PortalUser(
        "Dana Kowalski",
        "Northwind Robotics, Inc.",
        "HR Director, plan administrator",
        "A1",
        "owner",
    ),
    PortalUser(
        "Victoria Lam", "Northwind Robotics, Inc.", "CFO, benefits committee chair", "A1", "tcwg"
    ),
    PortalUser(
        "Robert Haines", "Northwind Robotics, Inc.", "Benefits committee member", "A1", "tcwg"
    ),
    PortalUser("Luis Ferrante", "Granite Peak Outdoor Supply, Inc.", "CFO", "A2", "owner"),
)
_PORTAL_BY_NAME: Final = {u.name: u for u in PORTAL_USERS}


# --- PBC lists (requests.ts) ---------------------------------------------------------------------


@dataclass(frozen=True)
class Request:
    category: str
    title: str
    status: RequestStatus
    due_on: date | None
    owner: str  # who answers it: a person or an organisation

    @property
    def assignee(self) -> PortalUser | None:
        """The owner's portal user when they hold an owner or contributor grant."""
        user = _PORTAL_BY_NAME.get(self.owner)
        return user if user is not None and user.role != "tcwg" else None


@dataclass(frozen=True)
class PbcList:
    key: str  # "northwind", "granite-peak": the label every id derives from
    engagement: str  # the audit label
    created: datetime
    published: bool
    requests: tuple[Request, ...] = field(default_factory=tuple[Request, ...])

    @property
    def id(self) -> str:
        return stable_id(f"request-list:{self.key}")

    def request_id(self, position: int) -> str:
        """`request:<key>:<n>` from 1, as requests.ts derives its item ids."""
        return stable_id(f"request:{self.key}:{position}")

    def category_id(self, name: str) -> str:
        return stable_id(f"request-category:{self.key}:{name}")

    def categories(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(r.category for r in self.requests))


_HARBORLINE: Final = "Harborline Trust Company"
_KEYSTONE: Final = "Keystone Retirement Services"
_PAYGRID: Final = "PayGrid Payroll"
_DANA: Final = "Dana Kowalski"
_SEP_18: Final = date(2026, 9, 18)
_SEP_25: Final = date(2026, 9, 25)

# AUD-03 spec: "Totals: 24 requests; 11 received; 1 needs review; 12 requested".
_NORTHWIND: Final[tuple[Request, ...]] = (
    Request(
        "Plan documents",
        "Trust agreement — Harborline Trust Company",
        "requested",
        _SEP_18,
        _HARBORLINE,
    ),
    Request(
        "Plan documents",
        "IRS opinion letter on the pre-approved plan document",
        "requested",
        _SEP_18,
        _DANA,
    ),
    Request("Plan documents", "Plan document & amendments", "received", None, _DANA),
    Request("Plan documents", "Adoption agreement", "received", None, _DANA),
    Request("Plan documents", "Summary plan description", "received", None, _DANA),
    Request(
        "Trust / Recordkeeper Reports",
        "Certified trust report (full year, signed)",
        "uploaded",
        None,
        _HARBORLINE,
    ),
    Request(
        "Trust / Recordkeeper Reports",
        "Withdrawals / distributions report",
        "requested",
        _SEP_18,
        _KEYSTONE,
    ),
    Request(
        "Trust / Recordkeeper Reports",
        "Summary of net trust assets",
        "received",
        None,
        _HARBORLINE,
    ),
    Request(
        "Trust / Recordkeeper Reports", "Schedule of Account Balances", "received", None, _KEYSTONE
    ),
    Request(
        "Trust / Recordkeeper Reports",
        "Annual loan balance roll-forward",
        "received",
        None,
        _KEYSTONE,
    ),
    Request(
        "Trust / Recordkeeper Reports",
        "Brokerage / SDBA asset detail — BrokerWindow",
        "received",
        None,
        _KEYSTONE,
    ),
    Request("Census & Payroll", "W-3 Form", "requested", _SEP_18, _DANA),
    Request("Census & Payroll", "Opt-Out Elections", "requested", _SEP_18, _DANA),
    Request("Census & Payroll", "Pay Rate Authorizations", "requested", _SEP_18, _DANA),
    Request("Census & Payroll", "YTD payroll register", "requested", _SEP_18, _PAYGRID),
    Request("Census & Payroll", "Employee Census File", "received", None, _DANA),
    Request("Census & Payroll", "Contribution Reports — PayGrid", "received", None, _PAYGRID),
    Request("Census & Payroll", "Quarterly 941 Forms", "received", None, _PAYGRID),
    Request(
        "Form 5500 & SOC 1",
        "Bridge letter — Keystone, Oct–Dec 2025",  # noqa: RUF001 (verbatim)
        "requested",
        _SEP_25,
        _KEYSTONE,
    ),
    Request(
        "Form 5500 & SOC 1",
        "Draft Form 5500 & Schedule H — Summit Plan Administrators",
        "requested",
        date(2026, 9, 30),
        "Summit Plan Administrators",
    ),
    Request(
        "Form 5500 & SOC 1", "ERISA 408(b)(2) fee disclosure", "requested", _SEP_25, _KEYSTONE
    ),
    Request(
        "Form 5500 & SOC 1",
        "SOC 1 Type 2 — Keystone Retirement Services",
        "received",
        None,
        _KEYSTONE,
    ),
    Request(
        "Cash",
        "Schedule of cash accounts, confirmations, and statements",
        "requested",
        _SEP_18,
        _HARBORLINE,
    ),
    Request(
        "Compliance & other", "Participant Complaints Log and Support", "requested", _SEP_18, _DANA
    ),
)

# The default FS-audit PBC catalogue (domain-audit.md Appendix A.1), the first n requests of each
# category so the list reads 41 (ENG-12: "41 requests"); the titles are the catalogue's.
_FS_CATALOGUE: Final[tuple[tuple[str, int, tuple[str, ...]], ...]] = (
    (
        "General & governance",
        7,
        (
            "TB (unadjusted) and GL detail for the year",
            "PY audited FS",
            "Board/committee minutes",
            "Org chart & ownership/cap table",
            "Significant contracts and agreements",
            "List of related parties",
            "List of legal counsel",
        ),
    ),
    (
        "Cash",
        3,
        (
            "Bank statements (year-end month + subsequent month)",
            "Bank reconciliations",
            "Confirmation authorizations (signature)",
        ),
    ),
    (
        "Receivables & revenue",
        5,
        (
            "AR aging at year end",
            "Subsequent receipts listing",
            "Allowance (CECL) calculation",
            "Revenue contracts (above threshold)",
            "Sales register",
        ),
    ),
    (
        "Inventory",
        3,
        ("Count instructions and count sheets", "Priced inventory listing", "Costing support"),
    ),
    ("Prepaids & other assets", 1, ("Prepaid schedules with invoices",)),
    (
        "PP&E & leases",
        3,
        ("Fixed-asset rollforward", "Additions/disposals support", "Depreciation schedule"),
    ),
    ("Investments", 2, ("Broker/custodian statements", "Fair value support")),
    (
        "Payables & accruals",
        2,
        ("AP aging", "Subsequent disbursements listing (unrecorded liabilities)"),
    ),
    (
        "Debt & equity",
        3,
        (
            "Debt agreements & amendments",
            "Amortization schedules",
            "Covenant compliance calculations",
        ),
    ),
    ("Payroll", 3, ("Payroll registers", "Forms 941/W-3", "Bonus/commission calculations")),
    ("Income taxes", 2, ("Tax provision workpapers", "Returns filed")),
    ("IT", 3, ("System inventory", "User access listings & terminations", "Change logs")),
    (
        "Completion",
        4,
        (
            "Subsequent-events questionnaire",
            "Going concern forecast (if indicated)",
            "Draft FS & notes (if client-prepared)",
            "Rep letter signatories",
        ),
    ),
)

PBC_LISTS: Final[tuple[PbcList, ...]] = (
    # "Requested Sep 1": published, so every client-visible request reads `requested` from then.
    PbcList("northwind", "A1", on_date(date(2026, 9, 1)), True, _NORTHWIND),
    # Drafts, firm only, while the letter is out (G3 not met).
    PbcList(
        "granite-peak",
        "A2",
        on_date(date(2026, 8, 31)),
        False,
        tuple(
            Request(category, title, "draft", None, "Luis Ferrante")
            for category, take, titles in _FS_CATALOGUE
            for title in titles[:take]
        ),
    ),
)

# DEC-37: the firm setting the E0 slice turns on.
FIRM_SETTINGS: Final[tuple[tuple[str, bool], ...]] = (("staff_can_accept_evidence", True),)
FIRM_ADMIN: Final = "GH"  # Grace Holloway sets firm settings (§9.2 "season setup")


def _audit_client(label: str) -> str:
    return BY_LABEL[label].client


def audit_events(setup_at: datetime) -> list[Event]:
    """The slice's events. Everything that predates the firm's setup instant (the clients exist
    from `setup_at`) is replayed at it and keeps its own date as `created_at`."""

    def at(when: datetime) -> datetime:
        return max(when, setup_at)

    events: list[Event] = []
    # Entities a client gains beyond its primary one: the two plans the EBP audits are for.
    for audit in AUDITS:
        if audit.entity is not None:
            events.append(
                Event(
                    f"entity:{slug_of(audit.entity)}",
                    setup_at,
                    "organisations.client_entity_added",
                    audit.ep,
                    SLICE,
                    {"entity": audit.entity},
                    client=audit.client,
                )
            )
    events += [
        Event(
            f"engagement:{a.label}",
            at(created_at(a)),
            "engagements.engagement_created",
            a.ep,
            SLICE,
            {"audit": a.label},
            client=a.client,
        )
        for a in AUDITS
    ]
    events += [
        Event(
            f"portal-user:{u.slug}",
            setup_at,
            "identity.portal_user_added",
            BY_LABEL[u.engagement].ep,
            SLICE,
            {"user": u.name},
            client=_audit_client(u.engagement),
        )
        for u in PORTAL_USERS
    ]
    events += [
        Event(
            f"pbc-list:{p.key}",
            at(p.created),
            "requests.pbc_list_created",
            BY_LABEL[p.engagement].ep,
            SLICE,
            {"list": p.key, "requests": len(p.requests)},
            client=_audit_client(p.engagement),
        )
        for p in PBC_LISTS
    ]
    events += [
        Event(
            f"firm-setting:{key}",
            setup_at,
            "identity.firm_setting_set",
            FIRM_ADMIN,
            SLICE,
            {"key": key, "value": value},
        )
        for key, value in FIRM_SETTINGS
    ]
    unknown = {i for a in AUDITS for i, _ in team_of(a)} - _INITIALS
    if unknown:
        raise ValueError(f"team initials without a seat: {sorted(unknown)}")
    return events
