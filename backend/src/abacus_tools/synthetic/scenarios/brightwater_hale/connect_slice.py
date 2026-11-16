"""The `connect` slice (W-01-T11; SPEC-659 AC-1 to AC-3, AC-6, AC-20, AC-23; DF-34): Brightwater
Hale's Connect installs at E0 and CCH Axcess Tax's timeline, as events the loader replays
through `integrations.api.seed_synthetic_install` and `seed_synthetic_event`.

E0 (Mon Sep 14, 2026, 9:24 AM CT), viewed by Felix Andersen (IT / Security): nine tiles connected
(WB-10 c): CCH Axcess Tax, CCH Axcess Practice, QuickBooks Online, NetSuite, Sage Intacct, Xero,
Box, Microsoft 365 and DocuSign. CCH Axcess Tax is in file-bridge mode (OQ-3, AC-23: "File bridge
· a person exports and imports", no token, no Reconnect) and grants no Workstream scope, so
CCH Axcess Workstream reads its prerequisite reason (WB-10 a). The four ledgers are firm apps
(each client authorizes its own company). Box and Microsoft 365 are Felix's own; Hannah Leclerc
has Box too (WB-10 d: "✓ Connected as you"). DF-34: CCH was connected Jan 14, 2026 9:12 AM by
Felix everywhere; its timeline ends at the Sep 14 import, with the Aug 17 9:05 AM import as the
snapshot WB-11 replays.

The catalogue itself is platform content, imported by the operator first (`make seed-demo` runs
`abacus_tools.integration_catalog import` with `catalogue/connect_v2.yaml`); never seeded here.
Opt-in: `--slice connect` (brings `people`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "connect"
NEEDS: Final = ("people",)
FELIX: Final = "Felix Andersen"
HANNAH: Final = "Hannah Leclerc"
JAN_14: Final = datetime(2026, 1, 14, 9, 12, tzinfo=CT)


@dataclass(frozen=True)
class Install:
    key: str
    scope: str  # firm · user
    person: str | None  # a personal install's person
    mode: str  # token · file_bridge · firm_app (firm); personal installs have none
    connected_at: datetime
    last_sync_at: datetime | None
    granted_scopes: tuple[str, ...] = ()
    consent_version: int | None = None


INSTALLS: Final[tuple[Install, ...]] = (
    Install(
        "cch",
        "firm",
        None,
        "file_bridge",
        JAN_14,
        datetime(2026, 9, 14, 9, 0, tzinfo=CT),
        ("returns.read",),
    ),
    Install(
        "cchpm",
        "firm",
        None,
        "token",
        JAN_14,
        datetime(2026, 9, 14, 6, 0, tzinfo=CT),
        ("practice.read",),
    ),
    Install(
        "quickbooks_online",
        "firm",
        None,
        "firm_app",
        datetime(2026, 3, 4, 10, 0, tzinfo=CT),
        None,
        consent_version=1,
    ),
    Install("netsuite", "firm", None, "firm_app", datetime(2026, 3, 9, 9, 0, tzinfo=CT), None),
    Install("intacct", "firm", None, "firm_app", datetime(2026, 3, 9, 9, 5, tzinfo=CT), None),
    Install("xero", "firm", None, "firm_app", datetime(2026, 3, 9, 9, 10, tzinfo=CT), None),
    Install(
        "docusign",
        "firm",
        None,
        "token",
        datetime(2026, 2, 2, 10, 0, tzinfo=CT),
        None,
        ("files.read",),
    ),
    Install(
        "box",
        "user",
        FELIX,
        "token",
        datetime(2026, 1, 20, 8, 30, tzinfo=CT),
        None,
        ("files.read",),
        1,
    ),
    Install(
        "m365",
        "user",
        FELIX,
        "token",
        datetime(2026, 1, 20, 8, 35, tzinfo=CT),
        None,
        ("messages.read",),
        1,
    ),
    Install(
        "box",
        "user",
        HANNAH,
        "token",
        datetime(2026, 2, 3, 9, 0, tzinfo=CT),
        None,
        ("files.read",),
        1,
    ),
)
# CCH Axcess Tax's timeline (WB-11 c, AC-20: five events), Jan 14 to Sep 14: the connect, then
# the file bridge's imports, the Aug 17 one the snapshot WB-11 replays.
CCH_TIMELINE: Final[tuple[tuple[str, datetime], ...]] = (
    ("synced", datetime(2026, 3, 2, 9, 0, tzinfo=CT)),
    ("synced", datetime(2026, 4, 15, 9, 0, tzinfo=CT)),
    ("synced", datetime(2026, 8, 17, 9, 5, tzinfo=CT)),
)


def viewer_connected(person: str = FELIX) -> list[str]:
    """The keys connected for `person` (the firm's and their own): WB-10 c's nine for Felix."""
    return [i.key for i in INSTALLS if i.scope == "firm" or i.person == person]


@register_slice(SLICE)
def connect_events() -> list[Event]:
    events = [
        Event(
            f"integration:{i.scope}:{i.key}:{i.person or 'firm'}",
            SETUP_AT,
            "integrations.install_seeded",
            "system",
            SLICE,
            {
                "key": i.key,
                "scope": i.scope,
                "person": i.person,
                "mode": i.mode,
                "status": "connected",
                "connected_by": FELIX if i.scope == "firm" else i.person,
                "connected_at": i.connected_at.isoformat(),
                "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
                "granted_scopes": list(i.granted_scopes),
                "consent_version": i.consent_version,
            },
        )
        for i in INSTALLS
    ]
    events += [
        Event(
            f"integration:firm:cch:event:{n}",
            SETUP_AT,
            "integrations.event_seeded",
            "system",
            SLICE,
            {"key": "cch", "scope": "firm", "kind": kind, "at": at.isoformat(), "actor": FELIX},
        )
        for n, (kind, at) in enumerate(CCH_TIMELINE)
    ]
    return events
