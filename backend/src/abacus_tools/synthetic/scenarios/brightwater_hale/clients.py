"""The 184 clients of Brightwater Hale LLP at E0 (SPEC-307 AC-1; DEC-47): 16 named (blueprint 01
§9.3 and the CLI-01 rows), 66 roster clients (§9.7 tax returns, closes, audits and signature
envelopes) and 102 deterministic filler clients that never reuse a canonical surname or word.
Every name is fictional, none carries " (Synthetic)", and no client carries an identifier of any
kind. Mirrors `apps/web/src/fixtures/seed/clients.ts` bit for bit (same draws, same order) until
the fixtures are exported from here (F-04.21); a golden file holds both to it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS, OfficeName
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import Rng, stable_id

ClientKind = Literal[
    "individual", "household", "business", "partnership", "exempt_org", "trust", "estate", "plan"
]
Portal = Literal["active", "invited", "not_invited"]
ServiceLine = Literal["tax", "audit", "cas", "advisory"]
ClientOrigin = Literal["named", "roster", "filler"]


@dataclass(frozen=True)
class Client:
    slug: str  # the label every id for this client is derived from
    name: str
    kind: ClientKind
    origin: ClientOrigin
    office: OfficeName
    partner: str  # the relationship partner's initials (a seat holder)
    services: tuple[ServiceLine, ...]
    attest: bool  # audit and review clients (CLI-01 "Attest")
    portal: Portal
    entities: tuple[str, ...]  # the first is the primary entity
    recency: int | None  # CLI-01 order for the 16 named (1 = most recent); None otherwise

    @property
    def id(self) -> str:
        return stable_id(f"client:{self.slug}")


@dataclass(frozen=True)
class Named:
    name: str
    kind: ClientKind
    office: OfficeName
    partner: str
    services: tuple[ServiceLine, ...]
    attest: bool = False
    portal: Portal = "active"
    entities: tuple[str, ...] | None = None


# CLI-01 rows 1 to 16, newest activity first (the screen's order).
NAMED: Final[tuple[Named, ...]] = (
    Named("Jonah & Claire Feld", "household", "New York", "DR", ("tax",)),
    Named(
        "Copperleaf Coffee Roasters, Inc.",
        "business",
        "Denver",
        "PR",
        (
            "cas",
            "tax",
        ),
    ),
    Named("Meera Shah", "individual", "Chicago", "NA", ("tax",)),
    Named(
        "Northwind Robotics, Inc.",
        "business",
        "Chicago",
        "MO",
        ("audit",),
        attest=True,
        entities=(
            "Northwind Robotics, Inc.",
            "Northwind Robotics 401(k) Plan",
        ),
    ),
    Named(
        "Ridgeline Property Partners, LP",
        "partnership",
        "New York",
        "DR",
        (
            "tax",
            "advisory",
        ),
    ),
    Named(
        "Granite Peak Outdoor Supply, Inc.",
        "business",
        "Denver",
        "MO",
        ("audit",),
        attest=True,
        entities=(
            "Granite Peak Outdoor Supply, Inc.",
            "Granite Peak Outdoor Supply 401(k) Plan",
        ),
    ),
    Named("Harborview Dental Properties, LP", "partnership", "New York", "DR", ("tax",)),
    Named("Marcus & Dana Whitley", "household", "Denver", "DR", ("tax",)),
    Named(
        "Estate of Walter Thornbury",
        "estate",
        "Chicago",
        "DR",
        ("tax",),
        portal="invited",
        entities=(
            "Walter Thornbury",
            "Estate of Walter Thornbury",
        ),
    ),
    Named(
        "Bluestem Analytics, LLC",
        "business",
        "New York",
        "PR",
        (
            "tax",
            "cas",
        ),
    ),
    Named(
        "Lakeshore Literacy Alliance",
        "exempt_org",
        "Chicago",
        "CM",
        (
            "audit",
            "tax",
        ),
        attest=True,
    ),
    Named("Elena Varga", "individual", "Chicago", "NA", ("tax",)),
    Named("Calloway Family Trust", "trust", "Chicago", "DR", ("tax",)),
    Named("Ashford Manufacturing Co.", "business", "Chicago", "NA", ("tax",)),
    Named("Juniper & Oak Interiors, LLC", "business", "Denver", "PR", ("cas",)),
    Named("Daniel & Ruth Okafor", "household", "Chicago", "NA", ("tax",)),
)

# (name, kind, office or None (drawn from the name), service lines): §9.7 tax returns R1 to R30,
# closes C1 to C22, audits A1 to A27 and signature envelopes E5 to E10 not already named.
ROSTER: Final[tuple[tuple[str, ClientKind, OfficeName | None, tuple[ServiceLine, ...]], ...]] = (
    ("Mateo & Lucia Alvarez", "household", "Chicago", ("tax",)),
    ("Priyanka & Sam Iyer", "household", "New York", ("tax",)),
    ("Harold Stein", "individual", "Chicago", ("tax",)),
    ("Wren & Avery Collins", "household", "Denver", ("tax",)),
    ("Gloria Mendez", "individual", "Denver", ("tax",)),
    ("Thomas & Irene Kowal", "household", "Chicago", ("tax",)),
    ("Benjamin Osterberg", "individual", "New York", ("tax",)),
    ("Nina & Paul Haddox", "household", "Chicago", ("tax",)),
    ("Rafael Quintero", "individual", "Denver", ("tax",)),
    ("Sunil & Asha Rao", "household", "New York", ("tax",)),
    (
        "Cedar Hollow Farms, LLC",
        "partnership",
        "Denver",
        (
            "tax",
            "cas",
        ),
    ),
    ("Northgate Medical Partners, LLP", "partnership", "Chicago", ("tax",)),
    ("Marlowe Street Holdings, LP", "partnership", "New York", ("tax",)),
    ("Kestrel Ventures Fund I, LP", "partnership", "New York", ("tax",)),
    (
        "Bramble & Finch Design, LLC",
        "partnership",
        "Chicago",
        (
            "tax",
            "cas",
        ),
    ),
    (
        "Two Rivers Brewing Co.",
        "business",
        "Denver",
        (
            "tax",
            "cas",
        ),
    ),
    (
        "Summit Line Logistics, Inc.",
        "business",
        "Chicago",
        (
            "tax",
            "cas",
        ),
    ),
    (
        "Pinecrest Pediatrics, PC",
        "business",
        "Denver",
        (
            "tax",
            "cas",
        ),
    ),
    (
        "Oakline Software, Inc.",
        "business",
        "New York",
        (
            "tax",
            "audit",
        ),
    ),
    (
        "Meridian Tool & Die, Inc.",
        "business",
        "Chicago",
        (
            "tax",
            "audit",
        ),
    ),
    (
        "Fenwick Family Foundation",
        "exempt_org",
        "Chicago",
        (
            "tax",
            "audit",
        ),
    ),
    (
        "Riverbend Community Theater",
        "exempt_org",
        "Denver",
        (
            "tax",
            "audit",
        ),
    ),
    ("Pryor Irrevocable Trust", "trust", "Chicago", ("tax",)),
    ("Estate of Eugene Barlow", "estate", "New York", ("tax",)),
    ("Delia Fortune", "individual", "Denver", ("tax",)),
    ("Morgan & Kai Ferris", "household", "New York", ("tax",)),
    ("Aurelio Santos", "individual", "Chicago", ("tax",)),
    (
        "Hollis Creek Veterinary, PC",
        "business",
        "Denver",
        (
            "tax",
            "cas",
        ),
    ),
    ("Vantage Point Realty, LLC", "partnership", "Chicago", ("tax",)),
    ("Juliet Okonjo", "individual", "Chicago", ("tax",)),
    (
        "Larkspur Floral, Inc.",
        "business",
        "Chicago",
        (
            "tax",
            "cas",
        ),
    ),
    ("Alder & Ash Furniture Co.", "business", "Chicago", ("cas",)),
    ("Bluebird Bakery Co.", "business", "Chicago", ("cas",)),
    ("Canyon Pass Climbing Gym, LLC", "business", "Denver", ("cas",)),
    ("Foxglove Studio, LLC", "business", "Chicago", ("cas",)),
    ("Granary Row Market, Inc.", "business", "Chicago", ("cas",)),
    ("Ironwood Landscape Co.", "business", "Denver", ("cas",)),
    (
        "Kettle & Kiln Pottery, LLC",
        "business",
        "Chicago",
        (
            "cas",
            "audit",
        ),
    ),
    ("Lumen Dental Lab, Inc.", "business", "Denver", ("cas",)),
    ("Maple & Main Hardware, Inc.", "business", "Chicago", ("cas",)),
    ("Northfield Pet Clinic, PC", "business", "Denver", ("cas",)),
    ("Orchard Lane Wellness, LLC", "business", "Chicago", ("cas",)),
    ("Prairie Wind Solar Installers, Inc.", "business", "Denver", ("cas",)),
    ("Quill & Press Printing Co.", "business", "Chicago", ("cas",)),
    ("Cobalt Ridge Manufacturing 401(k) Plan", "plan", None, ("audit",)),
    ("Halden Health 403(b) Plan", "plan", None, ("audit",)),
    ("Fairhaven Foods 401(k) Plan", "plan", "Chicago", ("audit",)),
    ("Sterling Freight 401(k) Plan", "plan", None, ("audit",)),
    ("Westbrook Engineering 401(k) Plan", "plan", None, ("audit",)),
    ("Arbor Senior Living 401(k) Plan", "plan", None, ("audit",)),
    ("Keel & Compass Marine 401(k) Plan", "plan", None, ("audit",)),
    ("Redtail Construction 401(k) Plan", "plan", None, ("audit",)),
    ("Clearwater Credit Union 401(k) Plan", "plan", None, ("audit",)),
    ("Hearthstone Hospitality 401(k) Plan", "plan", None, ("audit",)),
    ("Bayside Electric Cooperative 401(k) Plan", "plan", None, ("audit",)),
    ("Tamarack Health System 403(b) Plan", "plan", None, ("audit",)),
    ("Larimer Cooperative Grocery", "business", None, ("audit",)),
    ("Sable Creek Homeowners Association", "exempt_org", None, ("audit",)),
    ("Halcyon Foods Distribution, Inc.", "business", None, ("audit",)),
    ("Hillcrest Montessori School", "exempt_org", None, ("audit",)),
    ("Wildflower Land Trust", "exempt_org", None, ("audit",)),
    ("Corinne Abbott", "individual", None, ("tax",)),
    ("Dev & Mira Kapoor", "household", None, ("tax",)),
    ("Hugo Brandvold", "individual", None, ("tax",)),
    ("Noor & Adam Farouk", "household", None, ("tax",)),
    ("Brightline Optics, Inc.", "business", None, ("tax",)),
)

# The audit partner of each audit-only roster client (blueprint §9.7 A5 to A27, the EP column).
AUDIT_PARTNER: Final[dict[str, str]] = {
    "Cobalt Ridge Manufacturing 401(k) Plan": "TW",
    "Halden Health 403(b) Plan": "CM",
    "Fairhaven Foods 401(k) Plan": "MO",
    "Sterling Freight 401(k) Plan": "TW",
    "Westbrook Engineering 401(k) Plan": "CM",
    "Arbor Senior Living 401(k) Plan": "MO",
    "Keel & Compass Marine 401(k) Plan": "TW",
    "Redtail Construction 401(k) Plan": "CM",
    "Clearwater Credit Union 401(k) Plan": "MO",
    "Hearthstone Hospitality 401(k) Plan": "TW",
    "Bayside Electric Cooperative 401(k) Plan": "CM",
    "Tamarack Health System 403(b) Plan": "CM",
    "Larimer Cooperative Grocery": "TW",
    "Sable Creek Homeowners Association": "CM",
    "Halcyon Foods Distribution, Inc.": "TW",
    "Hillcrest Montessori School": "TW",
    "Wildflower Land Trust": "CM",
    "Oakline Software, Inc.": "CM",
    "Meridian Tool & Die, Inc.": "MO",
    "Riverbend Community Theater": "CM",
    "Fenwick Family Foundation": "PR",
    "Kettle & Kiln Pottery, LLC": "PR",
}
_NOT_ATTEST: Final = frozenset({"Fenwick Family Foundation", "Kettle & Kiln Pottery, LLC"})

OFFICE_NAMES: Final[tuple[OfficeName, ...]] = ("Chicago", "Denver", "New York")
_TAX_PARTNER: Final[dict[str, str]] = {"Chicago": "NA", "Denver": "VH", "New York": "DR"}
FILLER_COUNT: Final = 102


def _draw_office(rng: Rng) -> OfficeName:
    """The returns split of §9.1 (98 / 64 / 62 of 224), as cut points over [0, 1)."""
    x = rng.next()
    return "Chicago" if x < 98 / 224 else "Denver" if x < 162 / 224 else "New York"


def _partner_for(services: tuple[ServiceLine, ...], office: OfficeName, ep: str) -> str:
    if "audit" in services:
        return ep
    if "cas" in services and "tax" not in services:
        return "PR"
    return _TAX_PARTNER[office]


def _portal_for(rng: Rng) -> Portal:
    x = rng.next()
    return "active" if x < 0.7 else "invited" if x < 0.85 else "not_invited"


def slug_of_client(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", " and "))
    return slug.strip("-")


def entity_id_of(client_slug: str, entity_name: str) -> str:
    """The id of one of a client's entities (the client itself, a plan, an estate)."""
    return stable_id(f"entity:{client_slug}:{slug_of_client(entity_name)}")


# Words generic enough to repeat; every other word a canonical name uses is reserved.
_GENERIC: Final = frozenset(
    [
        "inc",
        "llc",
        "llp",
        "pc",
        "lp",
        "the",
        "and",
        "plan",
        "trust",
        "family",
        "estate",
        "partners",
        "holdings",
        "foundation",
        "group",
        "company",
    ]
)


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z]+", text.lower()) if len(w) >= 3 and w not in _GENERIC]


_FIRST: Final = [
    "Adrian",
    "Beatrice",
    "Colin",
    "Delphine",
    "Edmund",
    "Farah",
    "Gideon",
    "Honora",
    "Ignatius",
    "Josephine",
    "Kaito",
    "Leontine",
    "Matteo",
    "Nadira",
    "Orson",
    "Philippa",
    "Quentin",
    "Rowena",
    "Soren",
    "Tamsin",
    "Ulrich",
    "Vesna",
    "Wendell",
    "Xiomara",
    "Yuri",
    "Zelda",
    "Abel",
    "Bryn",
    "Cyrus",
    "Dalia",
    "Emeric",
    "Freya",
    "Gus",
    "Hollis",
    "Ilona",
    "Jules",
    "Kit",
    "Lorna",
    "Milo",
    "Neve",
    "Otis",
    "Pia",
]

_LAST: Final = [
    "Abernathy",
    "Bellamy",
    "Castellano",
    "Dunmore",
    "Eastwood",
    "Fairbanks",
    "Galloway",
    "Hartwell",
    "Ingram",
    "Jessup",
    "Kingsley",
    "Lockhart",
    "Montrose",
    "Nakamura",
    "Oyelaran",
    "Prescott",
    "Quigley",
    "Radcliffe",
    "Sandoval",
    "Thackeray",
    "Underhill",
    "Vasquez",
    "Winslow",
    "Yarborough",
    "Zimmerman",
    "Ackerman",
    "Blackwood",
    "Carrow",
    "Delacroix",
    "Everhart",
    "Fontaine",
    "Gladstone",
    "Hollander",
    "Ivanov",
    "Jarrett",
    "Kessler",
    "Lindqvist",
    "Merriweather",
    "Nightingale",
    "Oswald",
    "Pemberton",
    "Quinlan",
    "Rutherford",
    "Stanhope",
    "Tennant",
    "Ulloa",
    "Vandermeer",
    "Wexford",
    "Xavier",
    "Yoshida",
    "Zeller",
    "Ashby",
    "Marchetti",
    "Cantrell",
    "Dempsey",
    "Elmsworth",
    "Farnsworth",
    "Grayson",
    "Haverford",
    "Isley",
    "Jernigan",
    "Brantley",
    "Lavigne",
    "Mortimer",
    "Nolan",
    "Overby",
    "Pritchard",
    "Rennick",
    "Sutherland",
    "Tolliver",
    "Upshaw",
    "Valentin",
    "Whitaker",
]

_WORD_A: Final = [
    "Amber",
    "Birchwood",
    "Cinder",
    "Driftwood",
    "Ember",
    "Fernhill",
    "Gable",
    "Hazel",
    "Indigo",
    "Linden",
    "Larch",
    "Marigold",
    "Nutmeg",
    "Opal",
    "Pebble",
    "Quince",
    "Russet",
    "Sorrel",
    "Thistle",
    "Umber",
    "Violet",
    "Willow",
    "Yarrow",
    "Zephyr",
    "Alcove",
    "Beacon",
    "Cobble",
    "Dovetail",
    "Eddy",
    "Fable",
    "Gilded",
    "Hearth",
    "Inlet",
    "Jasper",
    "Kindle",
    "Lantern",
    "Meadow",
    "Nimbus",
    "Orchid",
    "Plover",
    "Quarry",
    "Ripple",
    "Sparrow",
    "Tideway",
    "Upland",
    "Verdant",
    "Wren",
    "Saltmarsh",
    "Brindle",
    "Clover",
]

_NOUN: Final = [
    "Cabinetry",
    "Pottery",
    "Provisions",
    "Cycles",
    "Textiles",
    "Optics",
    "Printing",
    "Outfitters",
    "Supply",
    "Freight",
    "Interiors",
    "Orchards",
    "Roasters",
    "Kitchens",
    "Press",
    "Milling",
    "Glassworks",
    "Lighting",
    "Tailoring",
    "Fabrication",
    "Ceramics",
    "Forge",
    "Salvage",
    "Cartage",
    "Apiaries",
    "Creamery",
    "Distillers",
    "Joinery",
    "Masonry",
    "Plumbing",
    "Surveying",
    "Tutoring",
    "Imaging",
    "Rentals",
    "Storage",
]

_SUFFIX: Final = (", LLC", ", Inc.", " Co.", ", PC")


def _canonical_words(names: list[str]) -> set[str]:
    found = {w for name in names for w in _words(name)}
    return found | {w for seat in SEATS for w in _words(seat.name)}


def _filler_name(rng: Rng, kind: ClientKind) -> str:
    if kind == "individual":
        return f"{rng.pick(_FIRST)} {rng.pick(_LAST)}"
    if kind == "household":
        first = rng.pick(_FIRST)
        second = rng.pick(_FIRST)
        return f"{first} & {'Jules' if second == first else second} {rng.pick(_LAST)}"
    head = f"{rng.pick(_WORD_A)} & {rng.pick(_WORD_A)}" if rng.chance(0.5) else rng.pick(_WORD_A)
    tail = f"{head} {rng.pick(_NOUN)}"
    suffix = rng.pick(_SUFFIX)
    return f"{tail}, LP" if kind == "partnership" else f"{tail}{suffix}"


def _draw_kind(rng: Rng) -> ClientKind:
    x = rng.next()
    if x < 0.25:
        return "individual"
    if x < 0.6:
        return "household"
    return "business" if x < 0.9 else "partnership"


def _fillers(canonical: list[str], count: int) -> list[Client]:
    """`count` filler clients, none sharing a word with a canonical client or the staff."""
    reserved = _canonical_words(canonical)
    taken = {n.lower() for n in canonical}
    out: list[Client] = []
    i = 0
    while len(out) < count:
        if i > 5000:
            raise RuntimeError("filler pools are exhausted")
        rng = Rng(f"filler:{i}")
        i += 1
        kind = _draw_kind(rng)
        name = _filler_name(rng, kind)
        if name.lower() in taken or any(w in reserved for w in _words(name)):
            continue
        taken.add(name.lower())
        office = _draw_office(rng)
        services: tuple[ServiceLine, ...] = (
            ("tax", "cas") if kind == "business" and rng.chance(0.3) else ("tax",)
        )
        out.append(
            Client(
                slug_of_client(name),
                name,
                kind,
                "filler",
                office,
                _partner_for(services, office, "PR"),
                services,
                attest=False,
                portal=_portal_for(rng),
                entities=(name,),
                recency=None,
            )
        )
    return out


def build_clients() -> list[Client]:
    """All 184: the 16 named (CLI-01 order), then the 66 roster, then the 102 filler."""
    named = [
        Client(
            slug_of_client(n.name),
            n.name,
            n.kind,
            "named",
            n.office,
            n.partner,
            n.services,
            attest=n.attest,
            portal=n.portal,
            entities=n.entities or (n.name,),
            recency=index + 1,
        )
        for index, n in enumerate(NAMED)
    ]
    roster: list[Client] = []
    for name, kind, office, services in ROSTER:
        rng = Rng(f"roster:{name}")
        chosen = office or rng.pick(OFFICE_NAMES)
        roster.append(
            Client(
                slug_of_client(name),
                name,
                kind,
                "roster",
                chosen,
                _partner_for(services, chosen, AUDIT_PARTNER.get(name, "MO")),
                services,
                attest="audit" in services and name not in _NOT_ATTEST,
                portal=_portal_for(rng),
                entities=(name,),
                recency=None,
            )
        )
    canonical = [c.name for c in (*named, *roster)]
    return [*named, *roster, *_fillers(canonical, FILLER_COUNT)]
