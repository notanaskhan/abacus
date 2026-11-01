"""A-03's Brightwater Hale populations by inverse construction (A-03-T16, TASK-2715; A-03 §5.4;
DEC-1659, DEC-1766). Synthetic content for the scenario loader, never product code.

The frozen `2.3` sampler draws, for the designed seed, the canonical ordinals recorded below; the
generators place the designed participants and payments at those ordinals, so a real draw returns
the design's names and amounts in the design's order (the A-03-T09 goldens hold the same
construction and fail if a selection line changes):

- **Northwind census v2** (412 rows, seed `0x5E2A91`, Participants Version 2): keyed by census
  row ("NWC-0001" ...), the participant's census ID a column; the 25 designed participants at
  `CENSUS_ORDINALS`.
- **Northwind census v1** (409 rows, seed `0x3C77D0`, Version 1, superseded): the same rows less
  the last three; its tie is off by $182,300.00 (AUD-11 a's struck Version 1).
- **Granite Peak disbursements** (1,912 payments, $38,640,200.00, seed `0x7C31B4`): 24 at or
  above $50,000 (SURL-01 to 24), 1,102 from $7,750 (SURL-25 to 40 at `GL_RANDOM_ORDINALS`), 786
  below; 24 + 16 = 40 drawn, $3,698,700.00.
- **Northwind distributions** (64 records, seed `0x7B13C4`): the picker's second set.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from openpyxl import Workbook

from abacus.modules.sampling.compute import Record, StratumRule

# The scenario's seeds (A-03 §5.4): each draw passes its own through the loader.
SEEDS: Final = {
    "northwind-participants-v1": 0x3C77D0,
    "northwind-participants-v2": 0x5E2A91,
    "granite-peak-disbursements-v1": 0x7C31B4,
    "northwind-distributions-v1": 0x7B13C4,
}

# AUD-11 a card 3, in draw order: name and census ID (the A-03-T09 golden's transcription).
PARTICIPANTS: Final[tuple[tuple[str, str], ...]] = (
    ("Alicia Brennan", "NW-1184"),
    ("Tomás Ibarra", "NW-0962"),
    ("Priyanka Desai", "NW-1203"),
    ("Gordon Whitfield", "NW-0418"),
    ("Mei Tanaka", "NW-1150"),
    ("Darnell Hughes", "NW-1022"),
    ("Sofia Marchetti", "NW-1219"),
    ("Kwame Mensah", "NW-1196"),
    ("Rebecca Lindgren", "NW-0877"),
    ("Hiroshi Nakamura", "NW-1171"),
    ("Ingrid Solberg", "NW-0731"),
    ("Felipe Navarro", "NW-1088"),
    ("Aisha Rahman", "NW-1230"),
    ("Connor Gallagher", "NW-0659"),
    ("Yuki Mori", "NW-1189"),
    ("Patrick Doyle", "NW-0990"),
    ("Leila Farahani", "NW-1142"),
    ("Andre Wilkins", "NW-1065"),
    ("Natalie Brooks", "NW-1211"),
    ("Vikram Sethi", "NW-0804"),
    ("Chloe Dubois", "NW-0712"),
    ("Benjamin Okoro", "NW-1158"),
    ("Teresa Romero", "NW-0935"),
    ("Ethan Caldwell", "NW-1004"),
    ("Fatima Qureshi", "NW-1224"),
)
# Inverse construction, recorded once from v2.3 (A-03-T09): each designed participant's canonical
# ordinal in census v2, in draw order; stratum 2's 16 random payments, in draw order.
CENSUS_ORDINALS: Final[tuple[int, ...]] = (
    214, 165, 323, 327, 194, 159, 43, 390, 205, 57, 300, 255, 224,
    73, 311, 295, 160, 139, 144, 337, 240, 28, 52, 408, 153,
)  # fmt: skip
GL_RANDOM_ORDINALS: Final[tuple[int, ...]] = (
    651, 520, 393, 403, 911, 885, 801, 519, 118, 983, 1010, 663, 966, 246, 1113, 774,
)  # fmt: skip
# AUD-11 f and SHT-01 c: the 40 SURL rows in draw order (key, vendor, paid, amount).
SURL: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("SURL-01", "Talus Climbing Gear, Inc.", "Jul 2", "186400.00"),
    ("SURL-02", "Cascade Footwear Group", "Jul 6", "248900.00"),
    ("SURL-03", "Mesa Packaging Supply", "Jul 8", "57250.00"),
    ("SURL-04", "Alpine Thread Mills", "Jul 14", "132600.00"),
    ("SURL-05", "Front Range Freight Co.", "Jul 22", "68400.00"),
    ("SURL-06", "Peakline Apparel Co.", "Jul 24", "214800.00"),
    ("SURL-07", "Basecamp Optics, Inc.", "Jul 27", "96300.00"),
    ("SURL-08", "Clear Creek Properties, LLC", "Jul 31", "74500.00"),
    ("SURL-09", "Talus Climbing Gear, Inc.", "Aug 4", "171200.00"),
    ("SURL-10", "Front Range Freight Co.", "Aug 19", "71900.00"),
    ("SURL-11", "Cascade Footwear Group", "Aug 21", "305600.00"),
    ("SURL-12", "Highline Retail Systems, Inc.", "Aug 25", "58800.00"),
    ("SURL-13", "Peakline Apparel Co.", "Sep 2", "189700.00"),
    ("SURL-14", "Front Range Freight Co.", "Sep 16", "66250.00"),
    ("SURL-15", "Talus Climbing Gear, Inc.", "Sep 16", "162400.00"),
    ("SURL-16", "Alpine Thread Mills", "Sep 16", "118300.00"),
    ("SURL-17", "Ridgeway Tent & Tarp Co.", "Sep 16", "142600.00"),
    ("SURL-18", "Mesa Packaging Supply", "Sep 17", "61300.00"),
    ("SURL-19", "Basecamp Optics, Inc.", "Sep 17", "88450.00"),
    ("SURL-20", "Peakline Apparel Co.", "Sep 17", "203900.00"),
    ("SURL-21", "Highline Retail Systems, Inc.", "Sep 18", "52700.00"),
    ("SURL-22", "Clear Creek Properties, LLC", "Sep 18", "74500.00"),
    ("SURL-23", "Talus Climbing Gear, Inc.", "Sep 18", "158200.00"),
    ("SURL-24", "Cascade Footwear Group", "Sep 18", "281450.00"),
    ("SURL-25", "Mesa Packaging Supply", "Jul 3", "18400.00"),
    ("SURL-26", "Front Range Freight Co.", "Jul 9", "12650.00"),
    ("SURL-27", "Basecamp Optics, Inc.", "Jul 15", "9875.00"),
    ("SURL-28", "Granite Rock Logistics", "Jul 21", "23940.00"),
    ("SURL-29", "Summit Signage Co.", "Jul 28", "31200.00"),
    ("SURL-30", "Evergreen Janitorial Services", "Aug 3", "8600.00"),
    ("SURL-31", "Ridgeway Tent & Tarp Co.", "Aug 7", "49750.00"),
    ("SURL-32", "Alpine Thread Mills", "Aug 12", "27300.00"),
    ("SURL-33", "Highline Retail Systems, Inc.", "Aug 18", "15980.00"),
    ("SURL-34", "Peak Power Utilities", "Aug 24", "21460.00"),
    ("SURL-35", "Mesa Packaging Supply", "Aug 28", "36120.00"),
    ("SURL-36", "Front Range Freight Co.", "Sep 2", "19875.00"),
    ("SURL-37", "Talus Climbing Gear, Inc.", "Sep 8", "47600.00"),
    ("SURL-38", "Northgate Insurance Brokers", "Sep 10", "12300.00"),
    ("SURL-39", "Basecamp Optics, Inc.", "Sep 14", "28450.00"),
    ("SURL-40", "Cascade Footwear Group", "Sep 17", "48800.00"),
)
GL_STRATA: Final = (
    StratumRule(Decimal("50000.00"), None, "all"),
    StratumRule(Decimal("7750.00"), Decimal("50000.00"), "random", 16),
    StratumRule(None, Decimal("7750.00"), "none"),
)
GL_BIG, GL_MID, GL_LOW = 24, 1102, 786
GL_TOTAL: Final = Decimal("38640200.00")
CENSUS_V2_COUNT, CENSUS_V1_COUNT, DISTRIBUTIONS_COUNT = 412, 409, 64
CENSUS_TOTAL: Final = Decimal("14560000.00")  # = PayGrid YTD register (AUD-11 a)
CENSUS_V1_OFF: Final = Decimal("182300.00")  # Version 1's census is short by this
HEADER: Final = ("Census row", "Participant ID", "Name", "Hire date", "Compensation")


@dataclass(frozen=True)
class CensusRow:
    row_key: str
    census_id: str
    name: str
    hired: date
    compensation: Decimal


def _spread(count: int, target: Decimal, width: int, step: int) -> list[Decimal]:
    """`count` whole-dollar amounts that sum to exactly `target`: the mean, varied by +d and -d in
    pairs (every amount within `width` of the mean), the remainder on the last."""
    mean, rest = divmod(int(target), count)
    amounts: list[Decimal] = []
    for n in range(count):
        d = (n // 2 * step) % (width + 1)
        amounts.append(Decimal(mean + (d if n % 2 == 0 else -d)))
    if count % 2 == 1:
        amounts[-1] = Decimal(mean)
    amounts[-1] += rest
    return amounts


def census(count: int = CENSUS_V2_COUNT, total: Decimal = CENSUS_TOTAL) -> list[CensusRow]:
    """The census in canonical order: the designed participants at their ordinals (census v2),
    every other row a synthetic participant; compensation foots to `total`."""
    designed: dict[int, tuple[str, str]] = dict(zip(CENSUS_ORDINALS, PARTICIPANTS, strict=True))
    pay = _spread(count, total, 20000, 131)
    rows: list[CensusRow] = []
    for n in range(count):
        name, census_id = designed.get(n, (f"Participant {n + 1:04d}", f"NW-{2000 + n:04d}"))
        rows.append(CensusRow(f"NWC-{n + 1:04d}", census_id, name, date(2020, 1, 6), pay[n]))
    return rows


def census_v1() -> list[CensusRow]:
    """409 rows (v2 less its last three), short of the register by $182,300.00."""
    return census(CENSUS_V1_COUNT, CENSUS_TOTAL - CENSUS_V1_OFF)


def census_records(rows: Sequence[CensusRow]) -> list[Record]:
    return [Record(r.row_key) for r in rows]


def census_xlsx(rows: Sequence[CensusRow]) -> bytes:
    """The census as Dana Kowalski uploads it (AUD-11 a's file): one sheet, the header first."""
    book = Workbook()
    sheet = book.active
    if sheet is None:  # a new Workbook always has its first sheet
        sheet = book.create_sheet()
    sheet.title = "Census"
    sheet.append(list(HEADER))
    for r in rows:
        sheet.append([r.row_key, r.census_id, r.name, r.hired.isoformat(), str(r.compensation)])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def disbursements() -> list[Record]:
    """1,912 payments keyed "GP-AP-00001" ... in canonical order, footing to $38,640,200.00."""
    surl = [Decimal(a) for _, _, _, a in SURL]
    low = _spread(GL_LOW, Decimal("2358000"), 500, 53)
    big_total = sum(surl[:GL_BIG], Decimal(0))
    mid_total = GL_TOTAL - big_total - sum(low, Decimal(0))
    random_at = dict(zip(GL_RANDOM_ORDINALS, surl[GL_BIG:], strict=True))
    fillers = _spread(GL_MID - len(random_at), mid_total - sum(surl[GL_BIG:]), 10000, 97)
    amounts = list(surl[:GL_BIG])
    filler = iter(fillers)
    for ordinal in range(GL_BIG, GL_BIG + GL_MID):
        amounts.append(random_at[ordinal] if ordinal in random_at else next(filler))
    amounts += low
    return [Record(f"GP-AP-{n:05d}", a) for n, a in enumerate(amounts, start=1)]


def distributions() -> list[Record]:
    """Northwind's 64 distributions (the picker's "Distributions · 10 of 64")."""
    return [Record(f"NWD-{n:04d}") for n in range(1, DISTRIBUTIONS_COUNT + 1)]


__all__ = [
    "CENSUS_ORDINALS",
    "GL_RANDOM_ORDINALS",
    "GL_STRATA",
    "HEADER",
    "PARTICIPANTS",
    "SEEDS",
    "SURL",
    "CensusRow",
    "census",
    "census_records",
    "census_v1",
    "census_xlsx",
    "disbursements",
    "distributions",
]
