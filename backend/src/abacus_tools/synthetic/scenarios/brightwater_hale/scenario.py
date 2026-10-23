"""The Brightwater Hale scenario at a snapshot (F-04-T10; SPEC-307).

`build(snapshot, holdouts)` is deterministic: the firm, offices, seats, the clients (less any
held out, plus those the epoch adds once their slices exist) and the timeline events dated up to
the snapshot. `fingerprint()` hashes its canonical form; `SCENARIO_HASH` pins it to
`SCENARIO_VERSION`, so any content change must bump both (a golden test holds them together).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import audit_events
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import Client, build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT, Snapshot, snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.holdouts import held_out
from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    FIRM_NAME,
    FIRM_ROLES,
    OFFICES,
    SEATS,
    Office,
    Seat,
    email_of,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice, slice_events
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event, ordered

SCENARIO_VERSION: Final = "bh-2026.10.2"
SCENARIO_HASH: Final = "f25ed109665dc4167f1b5f460ee3f760cf05fe71ece99f7904ad2d904ff40016"
FIRM_ID: Final = stable_id("firm:brightwater-hale")
# The firm, its offices, seats and clients exist before the demo week opens.
SETUP_AT: Final = datetime(2026, 9, 1, 8, 0, tzinfo=CT)


@register_slice("audit_core")
def _audit_core() -> list[Event]:
    """F-04's slice: the firm, offices, people and clients, then the 27 audits, the Northwind and
    Granite Peak PBC lists, their portal people and the E0 firm settings (F-04-T20, `audits`)."""
    events = [Event("firm", SETUP_AT, "identity.firm_created", "system", "audit_core")]
    events += [
        Event(f"office:{o.name}", SETUP_AT, "organisations.office_created", "system", "audit_core")
        for o in OFFICES
    ]
    events += [
        Event(
            f"seat:{slug_of(s.name)}",
            SETUP_AT,
            "identity.staff_member_added",
            "system",
            "audit_core",
            {"initials": s.initials, "office": s.office, "firm_role": FIRM_ROLES.get(s.initials)},
        )
        for s in SEATS
    ]
    events += [
        Event(
            f"client:{c.slug}",
            SETUP_AT,
            "organisations.client_created",
            c.partner,
            "audit_core",
            {"kind": c.kind, "office": c.office, "entities": list(c.entities)},
            client=c.name,
        )
        for c in build_clients()
    ]
    return events + audit_events(SETUP_AT)


@dataclass(frozen=True)
class Scenario:
    version: str
    snapshot: Snapshot
    holdouts: tuple[str, ...]
    firm_id: str
    firm_name: str
    offices: tuple[Office, ...]
    seats: tuple[Seat, ...]
    clients: tuple[Client, ...]
    events: tuple[Event, ...]

    def canonical(self) -> dict[str, object]:
        """A plain, ordered form: what the fingerprint hashes."""
        return {
            "version": self.version,
            "snapshot": [self.snapshot.name, self.snapshot.at.isoformat()],
            "holdouts": list(self.holdouts),
            "firm": [self.firm_id, self.firm_name],
            "offices": [asdict(o) for o in self.offices],
            "seats": [asdict(s) | {"email": email_of(s.name)} for s in self.seats],
            "clients": [asdict(c) | {"id": c.id} for c in self.clients],
            "events": [
                [e.id, e.at.isoformat(), e.kind, e.actor, e.slice, dict(e.data), e.client]
                for e in self.events
            ],
        }

    def fingerprint(self) -> str:
        text = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()


def build(
    at: str = "E0", holdouts: tuple[str, ...] = (), slices: tuple[str, ...] = ("audit_core",)
) -> Scenario:
    """The scenario at a named snapshot, less the holdouts, with the given slices' events."""
    when = snapshot(at)
    out = held_out(holdouts)
    clients = tuple(c for c in build_clients() if c.name not in out)
    events = ordered(
        e
        for name in slices
        for e in slice_events(name)
        if e.at <= when.at and (e.client is None or e.client not in out)
    )
    return Scenario(
        SCENARIO_VERSION,
        when,
        tuple(sorted(holdouts)),
        FIRM_ID,
        FIRM_NAME,
        OFFICES,
        SEATS,
        clients,
        tuple(events),
    )
