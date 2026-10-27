"""The `portal_pbc` slice (R-01-T11; R-01 §5.4; POR-03, POR-04, POR-14, AUD-03; DEC-348, DEC-471):
what the portal's documents, request detail and third-party room need from the live seed beyond
the `portal` slice, as events the loader replays.

DEC-348 (decided 2026-10-27, the proposed option): the portal handoffs win for the client-facing
`title` only; AUD-03 keeps its 24 rows and their descriptions. DEC-471 (Ayush Bhatia, 2026-10-27)
fills the rest of the slice even where no source names a value or no service will write it. Every
such value is synthetic and marked "DEC-471" below; the bootstraps carry the audit row the
missing service would write.

- **Dana Kowalski's client titles** (POR-03 i) on five of AUD-03's Dana rows, through
  `requests.api.update_item` as Marcus Delaney when the list is published (Sep 1). "Employee
  Census File" is received, which the service refuses to edit, so its title is bootstrapped
  (DEC-471). The list is named "PY2025 Audit requests" (POR-03 i), bootstrapped: no service
  names a PBC list.
- **The delegations** behind POR-03 i's "Some requests go to Keystone, Harborline, PayGrid and
  Summit directly" (DEC-471, bootstrapped: `delegate_item` needs a contact with a portal
  sign-in, and none has one at E0). Keystone gets the 9 requests of Sam Ortiz's invitation
  (`portal`), on his contact, when it is sent (Sep 2). Harborline, PayGrid and Summit get the rest
  of AUD-03's rows they own, each on an organisation contact of its own, at publish (Sep 1). No
  delegation has a grant (`grant_id` null): nobody has signed in yet.
- **Claire Feld's 9:12 AM email** (POR-03 c; INB-02 files it in c2): `Feld_1095C_2025.pdf` waits
  in the Feld engagement's Inbox, from Claire, at Mon Sep 14, 9:12 AM CT. Bootstrapped (DEC-471):
  the seeded Feld engagement has no client acceptance, so `evidence.api`'s client-data gate
  (SPEC-025 AC-7) refuses `add_to_inbox`. The bytes are a synthetic Form 1095-C from the
  generator (`abacus_tools.synthetic.documents`), stored through `evidence.api.stage_content`.

The slice `portal_pbc_returned` is POR-03 g and POR-04 d's alternate path (the screen contracts'
"holdout" snapshot, not the seeded day), opt-in on its own: Claire uploads `Feld_1095C_2024.pdf`
to the 1095-C request (Sep 14, 8:40 AM, DEC-471) and Kevin Osei returns it with reason
`wrong_period` (read "wrong year" on a tax binder) and POR-03 g's note (9:05 AM, DEC-471). The
return is a person's review decision, which `evidence.decide` takes only while that person serves
a request (ADR-005, REVIEW-001), so it is bootstrapped as Kevin's.

Still not here: POR-02's "19 of 21 · 37 sorted" (DEC-348 (1), (2); the seed reads 5 of 7, which
`test_p08t22_portal_seed_footing.py` asserts), and POR-14 a's "4 of 9", which contradicts AUD-03's
statuses (6 of Keystone's 9 are done).

Opt-in (`--slice portal_pbc`, which brings `binders` and `portal`); `build()` keeps its default,
so SCENARIO_HASH is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from abacus_tools.synthetic.documents import form_1095c_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PBC_LISTS, on_date
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import (
    FELD,
    SAM_ORTIZ,
    delegated_requests,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "portal_pbc"
RETURNED_SLICE: Final = "portal_pbc_returned"
NEEDS: Final = ("binders", "portal")  # `expand_slices` expands one level
NORTHWIND: Final = "Northwind Robotics, Inc."
# Marcus Delaney (Audit Manager on Northwind) edits the requests (SHL-14 a and b's viewer).
BY: Final = "MD"

# --- POR-03 i: Dana's own requests in the portal's words (DEC-348) ------------------------------

# AUD-03's title -> POR-03 i's, for the rows Dana owns.
CLIENT_TITLES: Final[dict[str, str]] = {
    "W-3 Form": "W-3 for 2025",
    "Opt-Out Elections": "Opt-out elections — auto-enrolled employees",
    "Pay Rate Authorizations": "Pay rate authorizations",
    "Employee Census File": "Employee census file — 2025",
    "Participant Complaints Log and Support": "Participant complaints log and support",
}
BINDER_NAME: Final = "PY2025 Audit requests"  # POR-03 i: "PY2025 Audit requests ⌄"
_NORTHWIND_LIST: Final = next(p for p in PBC_LISTS if p.key == "northwind")


def retitled() -> tuple[tuple[int, str, str], ...]:
    """(position, AUD-03's title, the client's title) for each request the slice retitles."""
    return tuple(
        (n, r.title, CLIENT_TITLES[r.title])
        for n, r in enumerate(_NORTHWIND_LIST.requests, 1)
        if r.title in CLIENT_TITLES
    )


# --- the delegations (DEC-471) -------------------------------------------------------------------

KEYSTONE: Final = "Keystone Retirement Services"
# POR-03 i's note names the organisations in this order.
OTHER_PARTIES: Final = (
    KEYSTONE,
    "Harborline Trust Company",
    "PayGrid Payroll",
    "Summit Plan Administrators",
)


@dataclass(frozen=True)
class Delegation:
    org: str
    positions: tuple[int, ...]  # the Northwind PBC list's request positions
    at: datetime

    @property
    def contact_id(self) -> str:
        """Sam Ortiz's contact for Keystone (`portal`), else the organisation's own."""
        if self.org == KEYSTONE:
            return SAM_ORTIZ.contact_id
        return stable_id(f"contact:{self.org}:northwind")


def delegations() -> tuple[Delegation, ...]:
    keystone_ids = set(delegated_requests(SAM_ORTIZ))
    position_of = {
        _NORTHWIND_LIST.request_id(n): n for n in range(1, len(_NORTHWIND_LIST.requests) + 1)
    }
    keystone = tuple(sorted(position_of[i] for i in keystone_ids))
    out = [Delegation(KEYSTONE, keystone, on_date(SAM_ORTIZ.sent))]
    for org in OTHER_PARTIES[1:]:
        positions = tuple(
            n
            for n, r in enumerate(_NORTHWIND_LIST.requests, 1)
            if r.owner == org and n not in keystone
        )
        out.append(Delegation(org, positions, _NORTHWIND_LIST.created))
    return tuple(out)


DELEGATION_BY_ORG: Final = {d.org: d for d in delegations()}

# --- POR-03 c: Claire's 9:12 AM email; POR-03 g: the returned 2024 form -------------------------


@dataclass(frozen=True)
class ClientFile:
    key: str
    client: str
    sender: str  # the portal person the file came from
    file_name: str
    at: datetime
    content: Callable[[], bytes]


FELD_1095C: Final = ClientFile(
    "feld-1095c-2025",
    FELD,
    "Claire Feld",
    "Feld_1095C_2025.pdf",
    datetime(2026, 9, 14, 9, 12, tzinfo=CT),  # "9:12 AM · Claire emailed" (BND-01, POR-03 c)
    lambda: form_1095c_pdf(tax_year=2025, employer="Mercer Hill Health", employee="Claire Feld"),
)
FELD_1095C_2024: Final = ClientFile(
    "feld-1095c-2024",
    FELD,
    "Claire Feld",
    "Feld_1095C_2024.pdf",
    datetime(2026, 9, 14, 8, 40, tzinfo=CT),  # DEC-471
    lambda: form_1095c_pdf(tax_year=2024, employer="Mercer Hill Health", employee="Claire Feld"),
)
CLIENT_FILES: Final = (FELD_1095C, FELD_1095C_2024)
CLIENT_FILE_BY_KEY: Final = {f.key: f for f in CLIENT_FILES}
# The Feld request the 1095-C answers (`binders.FELD_REQUESTS`, position 5).
FELD_1095C_REQUEST: Final = "Form 1095-C From Mercer Hill Health"


@dataclass(frozen=True)
class Return:
    file: str  # the client file's key
    by: str  # the firm person's initials
    reason_code: str
    note: str
    at: datetime


# POR-03 g: "Returned · wrong year" + "This is the 2024 form. We need the 2025 Form 1095-C. —
# Kevin Osei" (the signature is the reader's).
FELD_RETURN: Final = Return(
    "feld-1095c-2024",
    "KO",
    "wrong_period",
    "This is the 2024 form. We need the 2025 Form 1095-C.",
    datetime(2026, 9, 14, 9, 5, tzinfo=CT),  # DEC-471
)
_LIST_PUBLISHED: Final = _NORTHWIND_LIST.created


@register_slice(SLICE)
def portal_pbc_events() -> list[Event]:
    events = [
        Event(
            f"request-title:northwind:{position}",
            _LIST_PUBLISHED,
            "requests.item_retitled",
            BY,
            SLICE,
            {"list": _NORTHWIND_LIST.key, "position": position, "title": title},
            client=NORTHWIND,
        )
        for position, _, title in retitled()
    ]
    events.append(
        Event(
            "request-list-name:northwind",
            _LIST_PUBLISHED,
            "requests.list_named",
            BY,
            SLICE,
            {"list": _NORTHWIND_LIST.key, "name": BINDER_NAME},
            client=NORTHWIND,
        )
    )
    events += [
        Event(
            f"delegation:northwind:{d.org.lower().replace(' ', '-')}",
            d.at,
            "requests.items_delegated",
            BY,
            SLICE,
            {"list": _NORTHWIND_LIST.key, "org": d.org, "requests": len(d.positions)},
            client=NORTHWIND,
        )
        for d in delegations()
    ]
    events.append(
        Event(
            f"inbox-file:{FELD_1095C.key}",
            FELD_1095C.at,
            "evidence.inbox_file_added",
            "system",
            SLICE,
            {"file": FELD_1095C.key, "sender": FELD_1095C.sender},
            client=FELD_1095C.client,
        )
    )
    return events


@register_slice(RETURNED_SLICE)
def portal_pbc_returned_events() -> list[Event]:
    return [
        Event(
            f"client-upload:{FELD_1095C_2024.key}",
            FELD_1095C_2024.at,
            "evidence.client_file_uploaded",
            "system",
            RETURNED_SLICE,
            {"file": FELD_1095C_2024.key, "request": FELD_1095C_REQUEST},
            client=FELD,
        ),
        Event(
            f"file-returned:{FELD_RETURN.file}",
            FELD_RETURN.at,
            "evidence.file_returned",
            FELD_RETURN.by,
            RETURNED_SLICE,
            {"file": FELD_RETURN.file, "reason": FELD_RETURN.reason_code},
            client=FELD,
        ),
    ]
