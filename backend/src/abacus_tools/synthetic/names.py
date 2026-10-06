"""Built-in word lists and reserved identifiers (SPEC-001 AC-13, AC-14).

Every identifier is in a range that can never belong to anyone: EIN prefix 00 (never assigned by
the IRS), routing numbers that fail the ABA checksum, 555-01xx phone numbers, example.com emails.
"""

from __future__ import annotations

import random

MARKER = " (Synthetic)"

_FIRST = (
    "Bluefin",
    "Copperleaf",
    "Driftwood",
    "Emberline",
    "Foxglove",
    "Granite",
    "Harbor",
    "Ironbark",
    "Juniper",
    "Kestrel",
    "Lantern",
    "Meadowlark",
    "Northwind",
    "Orchard",
    "Pinecrest",
    "Quarry",
    "Riverstone",
    "Saltmarsh",
    "Tidewater",
    "Umber",
    "Vantage",
    "Willowbrook",
    "Yarrow",
    "Zephyr",
)
_SECOND = (
    "Analytics",
    "Supply",
    "Foods",
    "Logistics",
    "Fabrication",
    "Media",
    "Health",
    "Outfitters",
    "Robotics",
    "Textiles",
    "Design",
    "Tooling",
    "Labs",
    "Freight",
)
_LEGAL = ("Inc.", "Holdings LLC", "Services LLC", "Trading Co.", "Partners LP")
_COUNTERPARTY_A = (
    "Amber",
    "Birch",
    "Cedar",
    "Delta",
    "Echo",
    "Fern",
    "Gale",
    "Hollow",
    "Indigo",
    "Jade",
    "Keel",
    "Lumen",
    "Maple",
    "Nimbus",
    "Onyx",
    "Pebble",
    "Quill",
    "Rook",
    "Sable",
    "Thistle",
)
_COUNTERPARTY_B = (
    "Works",
    "Traders",
    "Goods",
    "Systems",
    "Studio",
    "Wholesale",
    "Partners",
    "Industries",
    "Collective",
    "Mercantile",
)
_BANKS = ("First Fictional Bank", "Placeholder Savings", "Example National Bank")


def client_base(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_SECOND)}"


def client_name(base: str) -> str:
    return f"{base}{MARKER}"


def entity_name(base: str, index: int) -> str:
    return f"{base} {_LEGAL[index % len(_LEGAL)]}{MARKER}"


def counterparties(rng: random.Random, count: int) -> tuple[str, ...]:
    names: list[str] = []
    while len(names) < count:
        name = f"{rng.choice(_COUNTERPARTY_A)} {rng.choice(_COUNTERPARTY_B)}"
        if name not in names:
            names.append(name)
    return tuple(names)


def bank_name(rng: random.Random) -> str:
    return rng.choice(_BANKS)


def ein(rng: random.Random) -> str:
    return f"00-{rng.randrange(10**7):07d}"


def _aba_valid(digits: str) -> bool:
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + d[2] + d[5] + d[8]) % 10 == 0


def routing_number(rng: random.Random) -> str:
    """Nine digits that fail the ABA checksum, so they can never route anywhere."""
    while True:
        candidate = f"{rng.randrange(10**9):09d}"
        if not _aba_valid(candidate):
            return candidate


def account_number(rng: random.Random) -> str:
    return f"{rng.randrange(1000, 10000)}-{rng.randrange(1000, 10000)}"


def phone(rng: random.Random) -> str:
    return f"555-01{rng.randrange(100):02d}"


def email(local: str) -> str:
    return f"{local}@example.com"
