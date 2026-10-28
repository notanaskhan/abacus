"""The `connections` slice (A-02-T27; A-02 §5.3; POR-16a): Copperleaf Coffee Roasters, Inc.'s
connections at their POR-16a states, as events the loader replays through the connections
module's synthetic-only seed (`connections.api.seed_synthetic_connection`). Synthetic, Brightwater
Hale only; nothing here is platform content.

POR-16a (Tess Moreno, Mon Sep 14, 9:24 AM): QuickBooks Online connected by Tess on Mar 4, 2026,
last sync 9:15 AM; Front Range Bank ••4410 connected, bank feed, last sync 6:02 AM; American
Express ••1009 **Needs reauth** (`token_expired`; "Brightwater Hale asked on Sep 10" is the
firm's reconnect request, A-02-T23, left to the scenario's reconnect events); Square connected,
last sync 6:00 AM. Shopify and the payroll provider are not connected (catalogue rows only). Each
connection's provider is a tooling fake (`abacus_tools.fakes.ledgers`), which reaches no host.

Honours the `copperleaf` holdout: with it, J02 creates Copperleaf itself and this slice adds
nothing (its events carry the client name, so the holdout filter drops them). The scenario's
trial balance files (`ledgers.py`) ship beside it under `files/`.

Opt-in (`--slice connections`, which brings `portal` for Tess Moreno and Ben Ashby's grants).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.binders import COPPERLEAF
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "connections"
NEEDS: Final = ("portal",)
CONNECTED_BY: Final = "Tess Moreno"


@dataclass(frozen=True)
class SeededConnection:
    label: str  # the card's name (the masked account label shown to the client)
    provider: str
    category: str
    status: str
    reason: str | None
    connected_at: datetime
    last_sync_at: datetime | None


CONNECTIONS: Final = (
    SeededConnection(
        "QuickBooks Online",
        "fake_quickbooks_online",
        "ledger",
        "active",
        None,
        datetime(2026, 3, 4, 10, 12, tzinfo=CT),
        datetime(2026, 9, 14, 9, 15, tzinfo=CT),
    ),
    SeededConnection(
        "Front Range Bank ••4410",
        "fake_bank_feed",
        "bank_feed",
        "active",
        None,
        datetime(2026, 3, 4, 10, 20, tzinfo=CT),
        datetime(2026, 9, 14, 6, 2, tzinfo=CT),
    ),
    SeededConnection(
        "American Express ••1009",
        "fake_card_feed",
        "card_feed",
        "needs_attention",
        "token_expired",
        datetime(2026, 3, 4, 10, 25, tzinfo=CT),
        datetime(2026, 9, 8, 6, 0, tzinfo=CT),
    ),
    SeededConnection(
        "Square",
        "fake_sales_feed",
        "sales",
        "active",
        None,
        datetime(2026, 3, 4, 10, 31, tzinfo=CT),
        datetime(2026, 9, 14, 6, 0, tzinfo=CT),
    ),
)


@register_slice(SLICE)
def connections_events() -> list[Event]:
    return [
        Event(
            f"connection:copperleaf:{c.provider}",
            SETUP_AT,
            "connections.connection_seeded",
            "system",
            SLICE,
            {
                "entity": COPPERLEAF,
                "provider": c.provider,
                "category": c.category,
                "label": c.label,
                "status": c.status,
                "reason": c.reason,
                "connected_by": CONNECTED_BY,
                "connected_at": c.connected_at.isoformat(),
                "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            },
            client=COPPERLEAF,
        )
        for c in CONNECTIONS
    ]
