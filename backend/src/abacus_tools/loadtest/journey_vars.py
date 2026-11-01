"""The `--var` values the journey profiles need, from the Brightwater Hale scenario (Q-03-T044).

Run: python -m abacus_tools.loadtest.journey_vars   (`make loadtest` passes them itself)

The ids are derived from the scenario, the same ones `make seed-demo` writes, so nothing is read
from a database: Northwind Robotics, Inc. (the client), its 401(k) Plan audit A1 (J04's PBC slice,
the engagement the J02 and J04 groups read and the 300-item import lands in; its team is Margaret
Okonkwo, Hannah Leclerc, Marcus Delaney and Ana Cruz). The J12 sign-in wave types an address on
the scenario's sink domain, written into the profile (a JSON body takes no `--var`).

Q-03-T043's fairness profile also reads the second firm: load firm 1's first audit
(`fleet_engagement_id`, from `abacus_tools.synthetic.fleet`; load it with
`python -m abacus_tools.synthetic.fleet --profile x1`), whose team is seats 2 to 5.
"""

from __future__ import annotations

import sys
from typing import Final

from abacus_tools.synthetic.fleet import plan
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import TO_SEND

NORTHWIND: Final = "Northwind Robotics, Inc."
J04_AUDIT: Final = "A1"


def journey_vars() -> dict[str, str]:
    client = next(c for c in build_clients() if c.name == NORTHWIND)
    audit = BY_LABEL[J04_AUDIT]
    if audit.client != NORTHWIND:
        raise ValueError(f"{J04_AUDIT} is not Northwind's audit; update the journey profiles")
    return {
        "client_id": client.id,
        "engagement_id": audit.id,
        "fleet_engagement_id": str(plan("x1")[0].id("engagement", 0)),
        # N-02-T47's signing surge: Harborview's 8879-PE, E18, the draft to send at E0.
        "e18_envelope_id": next(e.id for e in TO_SEND if e.key == "E18"),
    }


def main() -> int:
    print(" ".join(f"--var {k}={v}" for k, v in journey_vars().items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
