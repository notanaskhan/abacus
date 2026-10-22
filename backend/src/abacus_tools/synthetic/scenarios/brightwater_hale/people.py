"""The 46 Accrued seats of Brightwater Hale LLP (blueprint 01 §9.1 and §9.2; ADM-02 rows 1 to
46, in the screen's order): 14 named in the seed, 32 from the §9.2 generator list, counted
22 / 14 / 10 by office (SPEC-307 AC-1). All names are fictional. Emails are
first.last@brightwaterhale.com, as ADM-02 shows them; delivery is always rewritten to the
synthetic sink (AC-5). Mirrors `apps/web/src/fixtures/seed/people.ts` until the fixtures are
exported from here (F-04.21)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

OfficeName = Literal["Chicago", "Denver", "New York"]
SeatRole = Literal[
    "Partner",
    "Manager",
    "Tax Reviewer",
    "Senior",
    "Staff",
    "Tax Preparer",
    "Firm Admin",
    "IT / Security",
]
_Flag = Literal["named", "seasonal", "named-seasonal"] | None

FIRM_NAME: Final = "Brightwater Hale LLP"


@dataclass(frozen=True)
class Office:
    name: OfficeName
    hq: bool
    address: str
    seats: int
    named_seats: int


@dataclass(frozen=True)
class Seat:
    n: int  # 1 to 46: the row on ADM-02
    initials: str
    name: str
    role: SeatRole
    title: str  # the line under the role ("Managing Partner, QM owner")
    office: OfficeName
    named: bool  # one of the 14 people the seed names (§9.2)
    seasonal: bool


_ROWS: Final[tuple[tuple[str, str, SeatRole, str, OfficeName, _Flag], ...]] = (
    ("MO", "Margaret Okonkwo", "Partner", "Managing Partner, QM owner", "Chicago", "named"),
    ("DR", "Daniel Reyes", "Partner", "Tax (signer)", "New York", "named"),
    ("PR", "Priya Raman", "Partner", "CAS & Advisory", "Denver", "named"),
    ("TW", "Thomas Whitcombe", "Partner", "EQR", "Chicago", "named"),
    ("VH", "Victor Hammond", "Partner", "Tax", "Denver", None),
    ("CM", "Celia Marsh", "Partner", "Audit", "New York", None),
    ("NA", "Neil Ashcroft", "Partner", "Tax", "Chicago", None),
    ("HL", "Hannah Leclerc", "Manager", "Audit Senior Manager", "Chicago", "named"),
    ("SI", "Samuel Ito", "Tax Reviewer", "Tax Manager", "New York", "named"),
    ("LK", "Laura Kemp", "Manager", "Audit", "Chicago", None),
    ("OH", "Omar Haddad", "Manager", "Audit", "Chicago", None),
    ("IM", "Isaac Moreau", "Tax Reviewer", "Tax Manager", "Denver", None),
    ("TR", "Tanya Reed", "Tax Reviewer", "Tax Manager", "New York", None),
    ("HV", "Helen Voss", "Manager", "CAS", "Denver", None),
    ("OB", "Olivia Brandt", "Senior", "Tax (preparer, first-level reviewer)", "Denver", "named"),
    ("MD", "Marcus Delaney", "Senior", "Audit in-charge", "Chicago", "named"),
    ("RM", "Raj Malhotra", "Senior", "CAS", "Denver", "named"),
    ("CD", "Caleb Dunn", "Senior", "Audit", "Chicago", None),
    ("JB", "Jasper Bell", "Senior", "Audit", "Chicago", None),
    ("SB", "Simone Baptiste", "Senior", "Audit", "Denver", None),
    ("YK", "Yusuf Kaya", "Tax Reviewer", "Tax Senior", "Chicago", None),
    ("NP", "Nadia Petrov", "Tax Reviewer", "Tax Senior", "New York", None),
    ("QL", "Quinn Lowry", "Tax Reviewer", "Tax Senior", "New York", None),
    ("EW", "Erin Walsh", "Senior", "CAS", "Denver", None),
    ("RF", "Rosa Fuentes", "Senior", "CAS", "Chicago", None),
    ("AC", "Ana Cruz", "Staff", "Audit", "Chicago", "named"),
    ("KO", "Kevin Osei", "Tax Preparer", "Tax", "New York", "named"),
    ("AW", "Aiden Ward", "Staff", "Audit", "Chicago", None),
    ("FN", "Fiona Nash", "Staff", "Audit", "Chicago", None),
    ("KR", "Kira Ross", "Staff", "Audit", "Chicago", None),
    ("CH", "Cole Hart", "Staff", "Audit", "Denver", None),
    ("HP", "Hana Pruitt", "Staff", "Audit", "New York", None),
    ("BN", "Bianca Novak", "Tax Preparer", "Tax", "Chicago", None),
    ("GT", "Gabe Torres", "Tax Preparer", "Tax", "Chicago", None),
    ("JL", "Joel Lim", "Tax Preparer", "Tax", "Denver", None),
    ("LW", "Leo Wong", "Tax Preparer", "Tax", "Denver", None),
    ("DS", "Dina Sato", "Tax Preparer", "Tax", "New York", None),
    ("IV", "Ivy Vance", "Staff", "CAS", "Chicago", None),
    ("EG", "Ezra Gold", "Staff", "CAS", "Denver", None),
    ("LP", "Lena Park", "Tax Preparer", "Tax (seasonal)", "Denver", "named-seasonal"),
    ("MA", "Maya Adler", "Tax Preparer", "Tax (seasonal)", "Chicago", "seasonal"),
    ("PS", "Paige Sutton", "Tax Preparer", "Tax (seasonal)", "Chicago", "seasonal"),
    ("NK", "Noel Kirby", "Tax Preparer", "Tax (seasonal)", "Denver", "seasonal"),
    ("RV", "Remy Vidal", "Tax Preparer", "Tax (seasonal)", "New York", "seasonal"),
    ("GH", "Grace Holloway", "Firm Admin", "Client Service Coordinator", "Chicago", "named"),
    ("FA", "Felix Andersen", "IT / Security", "Qualified Individual", "Chicago", "named"),
)

SEATS: Final[tuple[Seat, ...]] = tuple(
    Seat(
        n + 1,
        initials,
        name,
        role,
        title,
        office,
        named=flag in ("named", "named-seasonal"),
        seasonal=flag in ("seasonal", "named-seasonal"),
    )
    for n, (initials, name, role, title, office, flag) in enumerate(_ROWS)
)

OFFICES: Final[tuple[Office, ...]] = (
    Office(
        "Chicago",
        hq=True,
        address="311 West Brannock Street, Suite 1700, Chicago, IL 60606",
        seats=22,
        named_seats=7,
    ),
    Office(
        "Denver",
        hq=False,
        address="1820 Coalbank Street, Suite 400, Denver, CO 80202",
        seats=14,
        named_seats=4,
    ),
    Office(
        "New York",
        hq=False,
        address="60 Quillon Place, 23rd Floor, New York, NY 10006",
        seats=10,
        named_seats=3,
    ),
)

# Seat holders with a firm-level role (identity `firm_role`).
FIRM_ROLES: Final[dict[str, Literal["firm_admin", "practice_leader", "quality_partner"]]] = {
    "GH": "firm_admin",
    "FA": "firm_admin",
    "MO": "practice_leader",
    "TW": "quality_partner",
}


def slug_of(name: str) -> str:
    """The persona slug a screen is seen as (`?as=hannah-leclerc`)."""
    return re.sub(r"[^a-z]+", "-", name.lower())


def email_of(name: str) -> str:
    first, *rest = name.lower().split(" ")
    return f"{first}.{''.join(rest)}@brightwaterhale.com"
