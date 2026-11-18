"""The `harlow_pike` slice (A-09-T39, stage 1; TASK-8543; DEC-5529): Harlow & Pike's FY2026 group
audit under the demo clock (epoch E1, from 10:05 AM on Mon Sep 14, 2026), through the services as
the people the design names, so every row carries its real audit event.

- **Client and entities**: "Harlow & Pike" with its five entities (AUD-31 to AUD-33), created as
  Margaret Okonkwo (the EP; AUD-01 g "MO / OH").
- **Engagement**: "Harlow & Pike Holdings, Inc." FY2026 group audit on Harlow & Pike Holdings, the
  other four entities its components; MO engagement partner, Omar Haddad manager, Caleb Dunn
  senior; due Fri Mar 19, 2027 (AUD-01 g).
- **Independence** (G2): Margaret, Omar and Caleb each confirm their own at 10:07 AM (the
  conclusion waits on an SKE designee the handoff does not name: stage 2).
- **Source**: the NetSuite OneWorld connection on Holdings ("NetSuite OneWorld · pulled 10:38 AM",
  AUD-31), covering the five entities once the structure is saved.
- **Consolidation** (AUD-32 a, c): "FY2026 group consolidation", year end Dec 31, 2026, interim
  Aug 31, 2026, prior Dec 31, 2025; three tiers at 100% (Holdings; Operating Co. and Real Estate;
  Manufacturing and Distribution under Operating Co.), saved by Omar.
- **Interim trial balances** (AUD-32 d): each entity's Aug 31, 2026 trial balance at the AUD-33 a
  captions (`assurance.group_fixtures.ROWS`), pulled at 10:38 AM and attached by Omar.
- **Eliminations** (AUD-33 a, b): E1a, E1b, E2, E3, E4 and E5 proposed by Caleb at 1:40 PM, then
  approved and posted by Omar at 2:01 PM (AUD-33 "approved_by Omar Haddad · posted 2:01 PM").

Each elimination line names the entity that carries the caption (DEC-5529): the investment lines
the parent (Operating Co. holds Investment in Manufacturing and Distribution; Holdings holds
Investment in Operating Co. and Real Estate), the contributed-capital lines the subsidiary whose
equity is eliminated (E1a: Manufacturing 14,000,000 and Distribution 6,000,000; E1b: Operating Co.
20,000,000 and Real Estate 6,000,000, so the debit side splits by subsidiary), the intercompany
sale the seller's sales and the buyer's cost of goods sold, the unrealized profit Distribution's
inventory, the balances Manufacturing's receivable and Distribution's payable, the rent Real
Estate's income and Manufacturing's expense. The totals are group_fixtures' to the cent.

Not here (stage 2, recorded in TASK-8543): the AUD-31 account-level mapping (the 244 accounts with
the FY2025 prior mapping; the handoff names about 15 accounts and the counts, so the rest cannot be
seeded without inventing rows), which the consolidated TB reads; the FY2025 prior trial balances
(the handoff gives no prior figures); inventory and forecast evidence files; group materiality
decided at 3:40 PM (the AUD-34 card waits on the mapped TB); Pruett & Lang as Distribution's
component auditor with its dates (Sep 10, 2026 to Mar 19, 2027; the auditor attaches to a scoped
component); the letter and POR-20 templates through admin import (DF-40). Opt-in
(`--slice harlow_pike`).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "harlow_pike"
NEEDS: Final = ("people",)
CLIENT: Final = "Harlow & Pike"
ENGAGEMENT: Final = "Harlow & Pike Holdings, Inc."
CONSOLIDATION: Final = "FY2026 group consolidation"
CONNECTION_LABEL: Final = "NetSuite OneWorld"
YEAR: Final = (date(2026, 1, 1), date(2026, 12, 31))
INTERIM_END: Final = date(2026, 8, 31)
PRIOR_END: Final = date(2025, 12, 31)
DUE_ON: Final = date(2027, 3, 19)
TEAM: Final = (("MO", "engagement_partner"), ("OH", "manager"), ("CD", "senior"))

# group_fixtures' entity keys, with each entity's name (AUD-33 a) and place in the structure.
ENTITY_KEYS: Final = ("holdings", "operating", "manufacturing", "distribution", "real_estate")
ENTITY_NAMES: Final = {
    "holdings": "Harlow & Pike Holdings, Inc.",
    "operating": "Harlow & Pike Operating Co.",
    "manufacturing": "Harlow & Pike Manufacturing, Inc.",
    "distribution": "Harlow & Pike Distribution, Inc.",
    "real_estate": "Harlow & Pike Real Estate, LLC",
}
STRUCTURE: Final = (
    ("holdings", 1, None),
    ("operating", 2, "holdings"),
    ("real_estate", 2, "holdings"),
    ("manufacturing", 3, "operating"),
    ("distribution", 3, "operating"),
)

D = Decimal
_Z: Final = D(0)
# (code, level, description, lines as (caption, entity, debit, credit)); DEC-5529 above.
ELIMINATIONS: Final = (
    ("E1a", 2, "Investment in subsidiaries vs contributed capital", (
        ("Common stock / contributed capital", "manufacturing", D(14_000_000), _Z),
        ("Common stock / contributed capital", "distribution", D(6_000_000), _Z),
        ("Investment in Manufacturing", "operating", _Z, D(14_000_000)),
        ("Investment in Distribution", "operating", _Z, D(6_000_000)),
    )),
    ("E1b", 1, "Investment in subsidiaries vs contributed capital", (
        ("Common stock / contributed capital", "operating", D(20_000_000), _Z),
        ("Common stock / contributed capital", "real_estate", D(6_000_000), _Z),
        ("Investment in Operating Co.", "holdings", _Z, D(20_000_000)),
        ("Investment in Real Estate", "holdings", _Z, D(6_000_000)),
    )),
    ("E2", 2, "Intercompany sales, Manufacturing → Distribution", (
        ("Net sales — intercompany", "manufacturing", D(18_000_000), _Z),
        ("Cost of goods sold", "distribution", _Z, D(18_000_000)),
    )),
    ("E3", 2, "Unrealized profit in Distribution's ending inventory", (
        ("Cost of goods sold", "distribution", D(240_000), _Z),
        ("Inventory", "distribution", _Z, D(240_000)),
    )),
    ("E4", 2, "Intercompany balances", (
        ("Intercompany payable", "distribution", D(2_400_000), _Z),
        ("Intercompany receivable", "manufacturing", _Z, D(2_400_000)),
    )),
    ("E5", 1, "Intercompany rent, Real Estate → Manufacturing", (
        ("Rental income — intercompany", "real_estate", D(1_200_000), _Z),
        ("Rent expense — intercompany", "manufacturing", _Z, D(1_200_000)),
    )),
)  # fmt: skip


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 14, hour, minute, tzinfo=CT)


def _event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"harlow:{key}", at, kind, actor, SLICE, data, client=CLIENT)


@register_slice(SLICE)
def harlow_pike_events() -> list[Event]:
    events = [
        _event("client", _at(10, 5), "harlow.client_created", "MO"),
        _event("engagement", _at(10, 6), "harlow.engagement_created", "MO"),
    ]
    # G2: each member confirms their own independence (the conclusion needs an SKE designee the
    # handoff does not name for Harlow & Pike: stage 2).
    events += [
        _event(f"independence:{who}", _at(10, 7), "harlow.independence_confirmed", who)
        for who, _role in TEAM
    ]
    events += [
        _event("connection", _at(10, 30), "harlow.connection_added", "OH"),
        _event("consolidation", _at(10, 32), "harlow.consolidation_created", "OH"),
        _event("structure", _at(10, 34), "harlow.structure_saved", "OH"),
    ]
    events += [
        _event(f"tb:{key}", _at(10, 38), "harlow.interim_tb_attached", "OH", entity=key)
        for key in ENTITY_KEYS
    ]
    events += [
        _event(f"elimination:{code}", _at(13, 40), "harlow.elimination_proposed", "CD", code=code)
        for code, _level, _desc, _lines in ELIMINATIONS
    ]
    events.append(_event("eliminations:posted", _at(14, 1), "harlow.eliminations_posted", "OH"))
    return events


__all__ = [
    "CLIENT",
    "CONSOLIDATION",
    "ELIMINATIONS",
    "ENTITY_KEYS",
    "ENTITY_NAMES",
    "NEEDS",
    "SLICE",
    "STRUCTURE",
    "harlow_pike_events",
]
