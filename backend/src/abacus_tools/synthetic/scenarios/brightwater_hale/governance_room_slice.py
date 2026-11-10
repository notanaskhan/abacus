"""The `governance_room` slice (R-02-T13 remainder; R-02 §3 POR-15; DEC-3029): Northwind's
Benefits Committee as the portal's governance room, from the figures book
(`backend/tests/golden/scenario/brightwater_hale/portal_figures.json` → `governance`).

- **The body.** "Benefits Committee" (`benefits_committee`) for Northwind Robotics, Inc., the id
  the fixture slice uses (`governance-body:northwind-benefits-committee`).
- **Its members** from Sep 1, 2026: Victoria Lam (chair), Robert Haines and Dana Kowalski, each a
  client-person contact linked to the portal user `audit_core` seeds (`audits.PORTAL_USERS`).
- **Their room.** Each member holds `tcwg` on the room (scope `governance_room` = the body),
  granted by the engagement partner, Margaret Okonkwo, as the governance send does (DEC-3026).

Not here (DEC-3029): the planning letter itself (its sealed sections need the firm's sealing key,
which only the app holds; it is composed and sent through AUD-22 once A-07-T33 wires it), and the
two inquiries (R-02-T16). The entries POR-08 shows are the `completion` slice's: Dana's decisions
there are recorded from her email (record channel), so the live portal list stays empty until a
firm sends an entry through the portal. Opt-in (`--slice governance_room`).
"""

from __future__ import annotations

from datetime import date
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import on_date
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "governance_room"
NEEDS: Final = ("audit_core",)
CLIENT: Final = "Northwind Robotics, Inc."
BODY_NAME: Final = "Benefits Committee"
BODY_ID: Final = stable_id("governance-body:northwind-benefits-committee")
SINCE: Final = date(2026, 9, 1)
# (person, role), chair first: the book's `members` with its `chair`.
MEMBERS: Final[tuple[tuple[str, str], ...]] = (
    ("Victoria Lam", "chair"),
    ("Robert Haines", "member"),
    ("Dana Kowalski", "member"),
)
BY: Final = "MO"  # Margaret Okonkwo, the engagement partner


def contact_id_of(name: str) -> str:
    return stable_id(f"contact:governance:{CLIENT}:{name}")


def grant_id_of(name: str) -> str:
    return stable_id(f"grant:tcwg:{BODY_ID}:{name}")


@register_slice(SLICE)
def governance_room_events() -> list[Event]:
    return [
        Event(
            f"governance-body:{BODY_ID}",
            on_date(SINCE),
            "assurance.governance_body_seeded",
            BY,
            SLICE,
            {
                "body": BODY_NAME,
                "kind": "benefits_committee",
                "members": [list(m) for m in MEMBERS],
                "since": SINCE.isoformat(),
            },
            client=CLIENT,
        )
    ]
