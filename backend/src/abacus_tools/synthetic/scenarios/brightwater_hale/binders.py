"""The `binders` slice (P-06-T08; P-06 §5.4; DEC-146): the TY2025 tax binders of Brightwater Hale
at E0, the return work items they hang on, and Copperleaf's August close intake.

- **241 TY2025 binders.** Tiles 1 Draft · 48 Published · 0 Unpublished · 40 Complete · 152 Closed
  (BND-01a). That is 224 returns, one "2025 Binder" each, plus 17 "2025 Binder pt 2".
- **The 15 BND-01 rows and Osterberg's binder** are exact (BND-01 spec ROWS 1 to 15, state c):
  status, marked-done person and date, closing date, and last client activity. Their
  "n of m" progress is kept as declared figures (`NamedBinder.progress`). Only the Feld binder
  carries its 7 requests (BND-02a: 5 of 7, nine categories). No source names the other binders'
  requests.
- **224 TY2025 returns on 214 tax engagements** (blueprint §9.5; 10 engagements hold 2 returns),
  as `tax_return` work items:
  - Every tax client has one return: the form §9.3 or §9.7 gives it, otherwise its kind's form.
  - The other 73 go to filler clients, by office, so returns read 98 / 64 / 62 (§9.1).
  - A return's state is known for the named and roster ones, so 79 are open and 145 done
    (§9.5). Done returns' binders are Closed (152 = 145 + 7 second parts).
  - T-02-T11 owns the returns' statuses, assignments and offices. It keeps these labels, so the
    binders don't move.
- **Copperleaf's August 2026 close intake** (CLS-03, SHL-14d): the "2026 Close" engagement, the
  August close and its `close_intake` binder, with 9 requests (8 recurring + 1 ad hoc, 7
  received). "Square payouts — August" is Pending incorporation.
- **The client people a binder names as "Marked done by"** (Owen Calder, Eleanor Calloway,
  Dr. Sofia Lindqvist, Elena Varga), as client users on the sink domain.

- **Granite Peak's SURL Draft** (SHL-14 f; P-06-T08 remainder, TASK-993): "Support for 40
  subsequent disbursements (SURL)" on the Granite Peak FY2026 PBC list, drafted by the agent in
  the BH-FS-430 procedure session on Thu Sep 24 (10:40 AM, the TS seed's instant), Owners only,
  for Luis Ferrante, firm owner Cole Hart, wording composed from the firm's template
  (`drafted_wording_source = 'template'`, so J22 step 3 sends it as designed, DV-11). It loads
  from the 2026-10-01 snapshot on; E0 (Sep 14) predates it.

Not here: the SURL request's 31 files. SHL-20 names two of them ("Granite Rock Logistics —
August statement.pdf", "Invoice 40117.pdf") and TPL-20 sixteen of the forty payments; no source
names the rest, or which 31 had files on Sep 26 (TASK-993). Northwind's PBC binder is F-04-T20's
(`audits.py`). There are no TY2026 binders (BND-01d).

Opt-in, like `shell`: `loader --slice binders`. `build()` keeps its default, so SCENARIO_HASH
is unchanged.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import SINK_DOMAIN, on_date
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import (
    Client,
    ClientKind,
    build_clients,
    slug_of_client,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import OfficeName, slug_of
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "binders"
TAX_YEAR: Final = 2025
BinderStatus = Literal["draft", "published", "unpublished", "complete", "closed"]
RequestStatus = Literal["requested", "received"]
# `tax_returns.form` codes; the label is the form as people write it.
FormCode = Literal["1040", "1041", "1065", "1120s", "1120", "990"]
_LABEL_OF: Final[dict[str, FormCode]] = {
    "1040": "1040",
    "1041": "1041",
    "1065": "1065",
    "1120-S": "1120s",
    "1120": "1120",
    "990": "990",
    "990-PF": "990",
}
_CAL_2025: Final = (date(2025, 1, 1), date(2025, 12, 31))
_FYE_JUN_2026: Final = (date(2025, 7, 1), date(2026, 6, 30))

# --- the return roster --------------------------------------------------------------------------

# Forms the sources give (§9.3 rows 1 to 16; §9.7 R1 to R30; the 8879-family envelopes E5 to E10)
# and each return's state where the sources say it: True done (Filed or Accepted), False open.
_KNOWN: Final[dict[str, tuple[str, bool]]] = {
    "Jonah & Claire Feld": ("1040", False),
    "Copperleaf Coffee Roasters, Inc.": ("1120-S", True),
    "Meera Shah": ("1040", False),
    "Ridgeline Property Partners, LP": ("1065", False),
    "Harborview Dental Properties, LP": ("1065", False),
    "Marcus & Dana Whitley": ("1040", True),
    "Estate of Walter Thornbury": ("1040", False),
    "Bluestem Analytics, LLC": ("1120-S", True),
    "Lakeshore Literacy Alliance": ("990", False),
    "Elena Varga": ("1040", False),
    "Calloway Family Trust": ("1041", False),
    "Ashford Manufacturing Co.": ("1120", False),
    "Daniel & Ruth Okafor": ("1040", True),
    "Mateo & Lucia Alvarez": ("1040", True),
    "Priyanka & Sam Iyer": ("1040", False),
    "Harold Stein": ("1040", False),
    "Wren & Avery Collins": ("1040", False),
    "Gloria Mendez": ("1040", False),
    "Thomas & Irene Kowal": ("1040", False),
    "Benjamin Osterberg": ("1040", False),
    "Nina & Paul Haddox": ("1040", False),
    "Rafael Quintero": ("1040", False),
    "Sunil & Asha Rao": ("1040", True),
    "Cedar Hollow Farms, LLC": ("1065", True),
    "Northgate Medical Partners, LLP": ("1065", False),
    "Marlowe Street Holdings, LP": ("1065", False),
    "Kestrel Ventures Fund I, LP": ("1065", False),
    "Bramble & Finch Design, LLC": ("1065", False),
    "Two Rivers Brewing Co.": ("1120-S", True),
    "Summit Line Logistics, Inc.": ("1120-S", True),
    "Pinecrest Pediatrics, PC": ("1120-S", False),
    "Oakline Software, Inc.": ("1120", False),
    "Meridian Tool & Die, Inc.": ("1120", False),
    "Fenwick Family Foundation": ("990-PF", False),
    "Riverbend Community Theater": ("990", False),
    "Pryor Irrevocable Trust": ("1041", False),
    "Estate of Eugene Barlow": ("1041", False),
    "Delia Fortune": ("1040", True),
    "Morgan & Kai Ferris": ("1040", False),
    "Aurelio Santos": ("1040", False),
    "Hollis Creek Veterinary, PC": ("1120-S", False),
    "Vantage Point Realty, LLC": ("1065", True),
    "Juliet Okonjo": ("1040", False),
    "Larkspur Floral, Inc.": ("1120-S", False),  # E7, Form 8879-S
    "Corinne Abbott": ("1040", False),  # E5
    "Dev & Mira Kapoor": ("1040", False),  # E6
    "Hugo Brandvold": ("1040", False),  # E8
    "Noor & Adam Farouk": ("1040", False),  # E9
    "Brightline Optics, Inc.": ("1120", False),  # E10, Form 8879-C
}
# A filler client's form follows its kind.
_FORM_OF_KIND: Final[dict[ClientKind, str]] = {
    "individual": "1040",
    "household": "1040",
    "business": "1120-S",
    "partnership": "1065",
}
RETURNS_TOTAL: Final = 224
ENGAGEMENTS_TOTAL: Final = 214
OPEN_RETURNS: Final = 79  # §9.5: open 79 · done 145
# §9.1 returns by office: Chicago 98 · Denver 64 · New York 62.
RETURNS_BY_OFFICE: Final[dict[OfficeName, int]] = {"Chicago": 98, "Denver": 64, "New York": 62}


@dataclass(frozen=True)
class Return:
    label: str  # "<client slug>" or "<client slug>:2"
    client: str
    entity: str
    form: str  # as written: "1040", "1120-S", "990-PF"
    office: OfficeName
    engagement: str  # the engagement label
    done: bool

    @property
    def code(self) -> FormCode:
        return _LABEL_OF[self.form]

    @property
    def period(self) -> tuple[date, date]:
        return _FYE_JUN_2026 if self.client == "Lakeshore Literacy Alliance" else _CAL_2025

    @property
    def name(self) -> str:
        """The work item as BND-01's Work item column writes it."""
        if self.client == "Lakeshore Literacy Alliance":
            return "2025 Form 990 (FYE Jun 30, 2026)"
        return f"{TAX_YEAR} Form {self.form}"

    @property
    def id(self) -> str:
        if self.label == "jonah-and-claire-feld":
            return stable_id("work-item:feld")  # the TS seed's id (audits.ts)
        return stable_id(f"work-item:return:{self.label}")


@dataclass(frozen=True)
class TaxEngagement:
    label: str
    client: str
    entity: str
    partner: str  # the relationship partner, who opens it
    returns: tuple[str, ...]  # return labels

    @property
    def id(self) -> str:
        if self.label == "jonah-and-claire-feld":
            return stable_id("engagement:feld")  # the TS seed's id (audits.ts)
        return stable_id(f"engagement:tax:{self.label}")

    def name(self, first: Return) -> str:
        return f"TY{TAX_YEAR} Form {first.form}"


def _rank(label: str) -> str:
    """A stable, label-keyed order (adding one record never reshuffles the rest)."""
    return stable_id(f"rank:{label}")


def _tax_clients() -> list[Client]:
    return [c for c in build_clients() if "tax" in c.services]


def build_returns() -> tuple[tuple[Return, ...], tuple[TaxEngagement, ...]]:
    clients = _tax_clients()
    first: list[Return] = []
    for c in clients:
        known = c.name in _KNOWN
        form, done = _KNOWN[c.name] if known else (_FORM_OF_KIND[c.kind], False)
        slug = slug_of_client(c.name)
        # Unknown states are settled below; mark them open for now.
        first.append(Return(slug, c.name, c.entities[0], form, c.office, slug, done and known))
    unknown = {r.label for r in first if r.client not in _KNOWN}
    # The second returns: filler clients by office, in roster order, until each office foots.
    need = Counter[str](dict(RETURNS_BY_OFFICE)) - Counter[str](r.office for r in first)
    extras: list[Return] = []
    for c in clients:
        if c.origin != "filler" or need[c.office] <= 0:
            continue
        need[c.office] -= 1
        slug = slug_of_client(c.name)
        form = _FORM_OF_KIND[c.kind]
        extras.append(Return(f"{slug}:2", c.name, c.entities[0], form, c.office, "", False))
    # 10 engagements hold two returns (the first 10 extras join their client's engagement); the
    # other extras each open an engagement of their own.
    doubles = len(first) + len(extras) - ENGAGEMENTS_TOTAL
    extras = [
        Return(r.label, r.client, r.entity, r.form, r.office, r.label.removesuffix(":2"), False)
        if n < doubles
        else Return(r.label, r.client, r.entity, r.form, r.office, r.label, False)
        for n, r in enumerate(extras)
    ]
    unknown |= {r.label for r in extras}
    # Unknown states: open until §9.5's 79 open returns foot, by stable rank; the rest done.
    known_open = sum(1 for r in first if r.client in _KNOWN and not _KNOWN[r.client][1])
    open_left = OPEN_RETURNS - known_open
    ranked = sorted(unknown, key=_rank)
    unknown_open = set(ranked[:open_left])
    returns = tuple(
        Return(
            r.label,
            r.client,
            r.entity,
            r.form,
            r.office,
            r.engagement,
            r.label not in unknown_open,
        )
        if r.label in unknown
        else r
        for r in (*first, *extras)
    )
    partner = {c.name: c.partner for c in clients}
    by_engagement: dict[str, list[Return]] = {}
    for r in returns:
        by_engagement.setdefault(r.engagement, []).append(r)
    engagements = tuple(
        TaxEngagement(
            label, rs[0].client, rs[0].entity, partner[rs[0].client], tuple(r.label for r in rs)
        )
        for label, rs in by_engagement.items()
    )
    return returns, engagements


# --- the binders --------------------------------------------------------------------------------

CLIENT_PEOPLE: Final[dict[str, str]] = {  # person -> the client they mark binders done for
    "Owen Calder": "Ridgeline Property Partners, LP",
    "Eleanor Calloway": "Calloway Family Trust",
    "Dr. Sofia Lindqvist": "Harborview Dental Properties, LP",
    "Elena Varga": "Elena Varga",
}


def person_id(name: str) -> str:
    return stable_id(f"user:{slug_of(name)}")


def person_email(name: str) -> str:
    return f"{slug_of(name).strip('-').replace('-', '.')}@{SINK_DOMAIN}"


@dataclass(frozen=True)
class NamedBinder:
    """A BND-01 row (spec ROWS 1 to 15) or Osterberg's (state c), verbatim."""

    client: str
    part: int
    status: BinderStatus
    progress: tuple[int, int]  # "done of total" as BND-01 shows it
    prep: str  # the Prep column's initials
    last_activity: datetime | None
    marked_done: tuple[str, datetime] | None = None
    closed_at: datetime | None = None
    published: tuple[str, datetime] | None = None  # by (initials), when


def _d(month: int, day: int, year: int = 2026) -> datetime:
    return on_date(date(year, month, day))


NAMED: Final[tuple[NamedBinder, ...]] = (
    NamedBinder(
        "Jonah & Claire Feld",
        1,
        "published",
        (5, 7),
        "KO",
        datetime(2026, 9, 14, 9, 12, tzinfo=CT),  # "9:12 AM · Claire emailed 2 files"
        published=("KO", _d(2, 3)),  # BND-02 rail: "Feb 3, 2026 · Kevin Osei"
    ),
    NamedBinder(
        "Ridgeline Property Partners, LP",
        1,
        "complete",
        (21, 21),
        "OB",
        _d(6, 1),
        marked_done=("Owen Calder", _d(6, 1)),
    ),
    NamedBinder("Ridgeline Property Partners, LP", 2, "published", (1, 3), "OB", _d(9, 11)),
    NamedBinder("Meera Shah", 1, "published", (15, 17), "LP", _d(9, 9)),
    NamedBinder(
        "Calloway Family Trust",
        1,
        "complete",
        (9, 9),
        "KO",
        _d(9, 9),
        marked_done=("Eleanor Calloway", _d(9, 9)),
    ),
    NamedBinder(
        "Harborview Dental Properties, LP",
        1,
        "complete",
        (18, 18),
        "DS",
        _d(8, 28),
        marked_done=("Dr. Sofia Lindqvist", _d(8, 28)),
    ),
    NamedBinder(
        "Elena Varga",
        1,
        "complete",
        (8, 8),
        "LP",
        _d(8, 30),
        marked_done=("Elena Varga", _d(8, 30)),
    ),
    NamedBinder("Estate of Walter Thornbury", 1, "published", (6, 15), "BN", _d(9, 9)),
    NamedBinder("Gloria Mendez", 1, "published", (4, 11), "NK", _d(9, 13)),  # "Yesterday"
    NamedBinder("Morgan & Kai Ferris", 1, "published", (2, 12), "DS", _d(9, 9)),
    NamedBinder("Rafael Quintero", 1, "draft", (0, 10), "LW", None),
    NamedBinder("Lakeshore Literacy Alliance", 1, "published", (7, 16), "BN", _d(9, 10)),
    NamedBinder("Fenwick Family Foundation", 1, "published", (5, 14), "BN", _d(8, 11)),
    NamedBinder(
        "Marcus & Dana Whitley", 1, "closed", (14, 14), "KO", _d(4, 2), closed_at=_d(4, 10)
    ),
    NamedBinder("Copperleaf Coffee Roasters, Inc.", 1, "closed", (12, 12), "LW", _d(3, 6)),
    # BND-01c's binder. Its "Unpublished Sep 2" is that artboard's override: the tiles of a read
    # 0 Unpublished at the same instant (DEC-146).
    NamedBinder("Benjamin Osterberg", 1, "published", (0, 0), "RV", None),
)
TILES: Final[dict[BinderStatus, int]] = {
    "draft": 1,
    "published": 48,
    "unpublished": 0,
    "complete": 40,
    "closed": 152,
}
SECOND_PARTS: Final = 17


@dataclass(frozen=True)
class Request:
    category: str
    title: str
    status: RequestStatus
    created: datetime  # when it was requested
    due_on: date | None
    kind: Literal["client_upload", "firm_provided"] = "client_upload"
    received: datetime | None = None
    incorporation: Literal["none", "pending_incorporation", "incorporated"] = "none"


@dataclass(frozen=True)
class Binder:
    ret: str  # the return label, or the close label for the close intake
    part: int
    status: BinderStatus
    kind: Literal["organizer", "close_intake"] = "organizer"
    named: NamedBinder | None = None
    categories: tuple[tuple[str, str | None], ...] = ()  # (name, glyph)
    family: Literal["tax_portal", "close"] = "tax_portal"
    requests: tuple[Request, ...] = field(default_factory=tuple[Request, ...])
    created_from: Literal["blank", "engine_import"] = "blank"
    published: tuple[str, datetime] | None = None

    @property
    def label(self) -> str:
        return f"{self.ret}:{self.part}" if self.kind == "organizer" else f"close:{self.ret}"

    @property
    def id(self) -> str:
        return stable_id(f"binder:{self.label}")

    @property
    def name(self) -> str:
        if self.kind == "close_intake":
            return "Requests"
        return f"{TAX_YEAR} Binder" if self.part == 1 else f"{TAX_YEAR} Binder pt {self.part}"

    def request_id(self, position: int) -> str:
        return stable_id(f"request:{self.label}:{position}")

    def category_id(self, name: str) -> str:
        return stable_id(f"request-category:{self.label}:{name}")


# BND-02's nine portal categories, in the platform-portal order, with their Lucide glyphs.
FELD_CATEGORIES: Final[tuple[tuple[str, str | None], ...]] = (
    ("Personal & Household Information", "CircleUserRound"),
    ("Income Sources", "Banknote"),
    ("Home & Property", "House"),
    ("Health & Medical", "Heart"),
    ("Education & Student", "GraduationCap"),
    ("Retirement", "PiggyBank"),
    ("Charitable & Donations", "HandHeart"),
    ("Business & Self-Employment", "Briefcase"),
    ("Other Activity", "Ellipsis"),
)
_FEB_3: Final = _d(2, 3)
_MAR_15: Final = date(2026, 3, 15)
# BND-02a and requests.ts: 5 of 7 satisfied, 2 open (Intake 2).
FELD_REQUESTS: Final[tuple[Request, ...]] = (
    Request("Income Sources", "2025 W-2 From Mercer Hill Health", "received", _FEB_3, _MAR_15),
    Request(
        "Income Sources",
        "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
        "received",
        _FEB_3,
        _MAR_15,
    ),
    Request(
        "Income Sources",
        "Schedule K-1 from Ridgeline Property Partners, LP",
        "received",
        _FEB_3,
        _MAR_15,
        kind="firm_provided",  # an internal draft handoff satisfies the row
    ),
    Request(
        "Home & Property",
        "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
        "received",
        _FEB_3,
        _MAR_15,
    ),
    Request(
        "Health & Medical", "Form 1095-C From Mercer Hill Health", "requested", _FEB_3, _MAR_15
    ),
    Request(
        "Charitable & Donations",
        "2025 donation receipts and acknowledgment letters",
        "received",
        _FEB_3,
        _MAR_15,
    ),
    Request(
        "Other Activity",
        "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
        "requested",
        _d(9, 1),
        date(2026, 9, 21),
    ),
)

# CLS-03 (Copperleaf, August 2026): 8 recurring from close plan v3 + 1 ad hoc = 9; 7 received.
COPPERLEAF: Final = "Copperleaf Coffee Roasters, Inc."
CLOSE_LABEL: Final = "copperleaf-2026-08"
CLOSE_PERIOD: Final = "2026-08"
CLOSE_DUE: Final = date(2026, 9, 10)  # "due Sep 10 → 4 days past due"
CLOSE_PREPARER: Final = "RM"
_SEP_1: Final = _d(9, 1)
_BANK: Final = "Bank & Cash Accounts"
CLOSE_CATEGORIES: Final[tuple[tuple[str, str | None], ...]] = (
    (_BANK, None),
    ("Revenue", None),
    ("Payroll", None),
    ("Loans & Payables", None),
    ("Questions from review", None),
)
CLOSE_REQUESTS: Final[tuple[Request, ...]] = (
    Request(
        _BANK,
        "Square payouts — August",
        "received",
        _SEP_1,
        date(2026, 9, 3),  # BD3
        received=_d(9, 3),
        incorporation="pending_incorporation",
    ),
    Request(
        _BANK,
        "Shopify payouts — August",
        "received",
        _SEP_1,
        None,
        received=_d(9, 3),
        incorporation="incorporated",
    ),
    Request(
        _BANK,
        "Front Range Bank statement — August (Savings ••4436)",
        "requested",
        _SEP_1,
        date(2026, 9, 5),  # BND-04: overdue since Sep 5
    ),
    Request(
        _BANK,
        "Amex ••1009 statement — cycle ending Aug 22",
        "received",
        _SEP_1,
        None,
        received=_d(8, 25),
        incorporation="incorporated",
    ),
    Request(
        "Revenue",
        "Subscription billing report — August",
        "received",
        _SEP_1,
        None,
        received=_d(9, 3),
        incorporation="incorporated",
    ),
    Request(
        "Payroll",
        "Payroll register — August (pay dates Aug 3, 17, 31)",
        "received",
        _SEP_1,
        None,
        received=_d(9, 2),
        incorporation="incorporated",
    ),
    Request(
        "Loans & Payables",
        "Equipment loan statement — August",
        "received",
        _SEP_1,
        None,
        received=_d(9, 2),
        incorporation="incorporated",
    ),
    Request(
        "Loans & Payables",
        "AP aging — Aug 31",
        "received",
        _SEP_1,
        None,
        received=_d(9, 2),
        incorporation="incorporated",
    ),
    Request(
        "Questions from review",
        "Sound Electric invoice — Aug 18 ($3,200)",
        "requested",
        _d(9, 11),  # ad hoc, requested Sep 11
        None,
    ),
)


def build_binders(returns: tuple[Return, ...]) -> tuple[Binder, ...]:
    by_client = {r.client: r for r in returns if not r.label.endswith(":2")}
    named: list[Binder] = []
    for b in NAMED:
        ret = by_client[b.client]
        is_feld = b.client == "Jonah & Claire Feld"
        named.append(
            Binder(
                ret.label,
                b.part,
                b.status,
                named=b,
                categories=FELD_CATEGORIES if is_feld else (),
                requests=FELD_REQUESTS if is_feld else (),
                created_from="engine_import" if is_feld else "blank",  # DV-9
                published=b.published,
            )
        )
    taken = {(b.ret, b.part) for b in named}
    generic = [r for r in returns if (r.label, 1) not in taken]
    # Second parts: 17 = Ridgeline's + 7 on done returns + 9 on open returns, by stable rank.
    pt2_named = sum(1 for b in named if b.part == 2)
    done_pt2 = TILES["closed"] - sum(1 for r in returns if r.done)
    open_pt2 = SECOND_PARTS - pt2_named - done_pt2
    has_pt2 = {(b.ret) for b in named if b.part == 2}
    candidates = sorted(
        (r for r in generic if r.label not in has_pt2), key=lambda r: _rank(r.label)
    )
    pt2 = [r for r in candidates if r.done][:done_pt2] + [r for r in candidates if not r.done][
        :open_pt2
    ]
    # Generic binders: Closed when the return is done; otherwise Published, then Complete, until
    # the tiles foot (by stable rank).
    opened = [(r.label, 1) for r in generic if not r.done] + [
        (r.label, 2) for r in pt2 if not r.done
    ]
    published_left = TILES["published"] - sum(1 for b in named if b.status == "published")
    published = set(sorted(opened, key=lambda k: _rank(f"{k[0]}:{k[1]}"))[:published_left])
    out = list(named)
    for r, part in [*((r, 1) for r in generic), *((r, 2) for r in pt2)]:
        status: BinderStatus = (
            "closed" if r.done else "published" if (r.label, part) in published else "complete"
        )
        out.append(Binder(r.label, part, status))
    out.append(
        Binder(
            CLOSE_LABEL,
            1,
            "published",
            kind="close_intake",
            categories=CLOSE_CATEGORIES,
            family="close",
            requests=CLOSE_REQUESTS,
            published=(CLOSE_PREPARER, _SEP_1),
        )
    )
    return tuple(out)


RETURNS, TAX_ENGAGEMENTS = build_returns()
BINDERS: Final = build_binders(RETURNS)
RETURN_BY_LABEL: Final = {r.label: r for r in RETURNS}
ENGAGEMENT_BY_LABEL: Final = {e.label: e for e in TAX_ENGAGEMENTS}
BINDER_BY_LABEL: Final = {b.label: b for b in BINDERS}
COPPERLEAF_CLOSE_ENGAGEMENT: Final = stable_id("engagement:cas:copperleaf-2026")
COPPERLEAF_CLOSE_ITEM: Final = stable_id(f"work-item:close:{CLOSE_LABEL}")


# --- Granite Peak's SURL Draft (SHL-14 f) ------------------------------------------------------

GRANITE_PEAK: Final = "Granite Peak Outdoor Supply, Inc."


@dataclass(frozen=True)
class DraftedRequest:
    """A request the agent drafted in a procedure session: a Draft, Owners only, until a person
    approves and sends it (ADR-005)."""

    key: str  # the id's label, as the TS seed derives it
    list_key: str  # the PBC list it joins (`audits.PBC_LISTS`)
    category: str  # the list's category it sits in
    title: str
    assignee: str  # the client person it is for
    owner: str  # the firm owner's initials
    period: tuple[date, date]
    due_on: date
    session: str  # the procedure session that drafted it
    at: datetime

    @property
    def id(self) -> str:
        return stable_id(f"request:{self.key}")

    @property
    def run_id(self) -> str:
        return stable_id(f"agent-run:{self.key}")


SURL_DRAFT: Final = DraftedRequest(
    "granite-peak:surl",
    "granite-peak",
    # SHL-14 f writes the band "Payables & accrued"; the list's category is the catalogue's.
    "Payables & accruals",
    "Support for 40 subsequent disbursements (SURL)",
    "Luis Ferrante",
    "CH",
    (
        date(2026, 6, 1),
        date(2026, 9, 18),
    ),  # SHL-20: "Jun 1 – Sep 18, 2026"  # noqa: RUF003 (verbatim)
    date(2026, 10, 2),  # the TS seed's due date (SHL-14.ts)
    "BH-FS-430",
    datetime(2026, 9, 24, 10, 40, tzinfo=CT),  # SHL-14.ts: 2026-09-24T15:40:00Z
)


def tax_binders() -> tuple[Binder, ...]:
    return tuple(b for b in BINDERS if b.kind == "organizer")


def binder_events(setup_at: datetime) -> list[Event]:
    events = [
        Event(
            f"client-person:{slug_of(name)}",
            setup_at,
            "identity.client_person_added",
            "system",
            SLICE,
            {"person": name},
            client=client,
        )
        for name, client in CLIENT_PEOPLE.items()
    ]
    events += [
        Event(
            f"tax-engagement:{e.label}",
            setup_at,
            "engagements.tax_engagement_created",
            e.partner,
            SLICE,
            {"engagement": e.label, "returns": len(e.returns)},
            client=e.client,
        )
        for e in TAX_ENGAGEMENTS
    ]
    events.append(
        Event(
            f"close-engagement:{CLOSE_LABEL}",
            setup_at,
            "engagements.close_engagement_created",
            "PR",
            SLICE,
            {"close": CLOSE_LABEL},
            client=COPPERLEAF,
        )
    )
    events += [
        Event(
            f"binder:{b.label}",
            setup_at,
            "requests.binder_created",
            _binder_actor(b),
            SLICE,
            {"binder": b.label, "status": b.status, "requests": len(b.requests)},
            client=COPPERLEAF if b.kind == "close_intake" else RETURN_BY_LABEL[b.ret].client,
        )
        for b in BINDERS
    ]
    events.append(
        Event(
            f"drafted-request:{SURL_DRAFT.key}",
            SURL_DRAFT.at,
            "requests.request_drafted",
            "system",
            SLICE,
            {"request": SURL_DRAFT.key, "session": SURL_DRAFT.session},
            client=GRANITE_PEAK,
        )
    )
    return events


def _binder_actor(binder: Binder) -> str:
    if binder.published is not None:
        return binder.published[0]
    if binder.kind == "close_intake":
        return CLOSE_PREPARER
    return ENGAGEMENT_BY_LABEL[RETURN_BY_LABEL[binder.ret].engagement].partner


@register_slice(SLICE)
def _binders_slice() -> list[Event]:
    return binder_events(SETUP_AT)
