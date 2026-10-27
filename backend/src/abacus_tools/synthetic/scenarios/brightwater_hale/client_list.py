"""The synthetic CCH Axcess Tax client-list export Grace Holloway uploads at season start
(P-07-T50; P-07 §3.3 Story 3.2, CLI-06 g; DEC-49, DEC-593): 212 rows that score 204 matched,
8 to review and 0 new against the Brightwater Hale clients at the CLI-06 snapshot (Tue Sep 8,
2026, with the `thornbury_estate` holdout: Walter Thornbury is a client, his estate not yet
added).

- **Rows 1 to 184:** one per client, in the scenario's client order, as the practice-management
  system names it: 176 spelled as Accrued has them (score 1.0), and 8 spelled differently
  (`REVIEW`), each scoring between 0.6 and 0.9 against its client only (pg_trgm similarity,
  DEC-441), so a person decides; rows 7 and 8 are two of them (CLI-06 g's "Skip").
- **Rows 185 and 186:** the two 401(k) plans the audits carry as their sponsors' entities.
- **Rows 187 to 212:** 26 grantor trusts ("<client> Revocable Trust") of the first 26 individual
  and household clients, matched to their grantor's client through the fiduciary designator rule
  (0.96).

The headings are the CCH export's as inferred in P-07 §6 (to be checked against a design partner's
export in Pilot 0). No row carries an identifier of any kind (no TIN, not even a 9xx fake), and
every name is fictional. `cch_client_list()` is deterministic; the committed file
(`files/cch-axcess-client-list.csv`) is its output, held to it by a unit test.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.clients import (
    Client,
    ClientKind,
    build_clients,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.holdouts import replaced_name

FILE: Final = Path(__file__).parent / "files" / "cch-axcess-client-list.csv"
HEADINGS: Final = (
    "Client ID",
    "Client Name",
    "Client Type",
    "Office",
    "Responsible Partner",
    "Status",
)
ROWS: Final = 212
MATCHED: Final = 204
TO_REVIEW: Final = 8
NEW: Final = 0
MATCH_AT: Final = 0.9  # auto-match at 90% and above (Story 3.2)
# The practice-management spelling of eight clients: a person reviews each (0.6 <= score < 0.9).
REVIEW: Final[dict[str, str]] = {
    "Harborview Dental Properties, LP": "Harbourview Dental Properties LP",
    "Marcus & Dana Whitley": "Marcus & Dana Whiteley",
    "Bluestem Analytics, LLC": "Blue Stem Analytics LLC",
    "Juniper & Oak Interiors, LLC": "Juniper and Oak Interiors LLC",
    "Summit Line Logistics, Inc.": "Summitline Logistics Inc",
    "Pinecrest Pediatrics, PC": "Pine Crest Pediatrics PC",
    "Riverbend Community Theater": "Riverbend Community Theatre",
    "Kestrel Ventures Fund I, LP": "Kestrel Ventures Fund 1 LP",
}
PLAN_ROWS: Final = (
    ("Northwind Robotics, Inc.", "Northwind Robotics 401(k) Plan"),
    ("Granite Peak Outdoor Supply, Inc.", "Granite Peak Outdoor Supply 401(k) Plan"),
)
TRUSTS: Final = 26
CCH_TYPES: Final[dict[ClientKind, str]] = {
    "individual": "Individual",
    "household": "Individual",
    "business": "Corporation",
    "partnership": "Partnership",
    "exempt_org": "Exempt Organization",
    "trust": "Fiduciary",
    "estate": "Fiduciary",
    "plan": "Employee Benefit Plan",
}


@dataclass(frozen=True)
class Row:
    client_id: str
    name: str
    client_type: str
    office: str
    partner: str
    expected: str  # the client the row belongs to (its name in Accrued at the snapshot)
    review: bool  # spelled differently: a person decides


def _name(client: Client) -> str:
    """The client's name at the CLI-06 snapshot (the holdout keeps Walter Thornbury)."""
    return replaced_name("thornbury_estate", client.name) or client.name


def rows() -> list[Row]:
    clients = build_clients()
    out: list[Row] = []

    def add(name: str, kind: ClientKind, client: Client, *, review: bool = False) -> None:
        out.append(
            Row(
                f"BH{10001 + len(out)}",
                name,
                CCH_TYPES[kind],
                client.office,
                client.partner,
                _name(client),
                review,
            )
        )

    for client in clients:
        spelled = REVIEW.get(client.name)
        kind: ClientKind = "individual" if _name(client) != client.name else client.kind
        add(spelled or _name(client), kind, client, review=spelled is not None)
    by_name = {c.name: c for c in clients}
    for sponsor, plan in PLAN_ROWS:
        add(plan, "plan", by_name[sponsor])
    grantors = [
        c
        for c in clients
        if c.kind in ("individual", "household") and c.name not in REVIEW and _name(c) == c.name
    ][:TRUSTS]
    for grantor in grantors:
        add(f"{grantor.name} Revocable Trust", "trust", grantor)
    return out


def cch_client_list() -> str:
    """The export as CSV text (CRLF line ends, as CCH writes them)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(HEADINGS)
    for r in rows():
        writer.writerow((r.client_id, r.name, r.client_type, r.office, r.partner, "Active"))
    return buffer.getvalue()


def write() -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_bytes(cch_client_list().encode("utf-8"))


if __name__ == "__main__":
    write()
