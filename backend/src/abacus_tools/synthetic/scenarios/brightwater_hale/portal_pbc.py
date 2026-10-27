"""The `portal_pbc` slice (R-01-T11; R-01 §5.4; POR-03, POR-04, POR-14, AUD-03; DEC-348): what
the portal's documents, request detail and third-party room need from the live seed beyond the
`portal` slice, as events the loader replays through service APIs.

DEC-348 (decided 2026-10-27, the proposed option) sets the terms: the portal handoffs win for the
client-facing `title` only, set through `requests.api` on AUD-03's rows where a row matches;
AUD-03 keeps its 24 rows and their descriptions; whatever no source names goes back to the handoff
as a gap. So the slice seeds only what is named:

- **Dana Kowalski's client titles** (POR-03 i). Four of AUD-03's open Dana rows take the title
  POR-03 i gives them, through `requests.api.update_item` as Marcus Delaney (SHL-14's firm
  viewer on Northwind) when the list is published (Sep 1). "IRS opinion letter on the
  pre-approved plan document" reads the same on both screens, so it is not edited.

Not here (DEC-348; gaps recorded in TASK-1221 and the POR-03, POR-04, POR-14 and AUD-03
Deviations):
- "Employee census file — 2025": AUD-03's "Employee Census File" is received, and a received
  request is not editable (`request_closed`), so its title stays AUD-03's.
- Claire's 9:12 AM email (POR-03 c and c2; INB-02): `Feld_1095C_2025.pdf` reaching the Feld
  Inbox. The Feld TY2025 engagement has no client acceptance (`binders` bootstraps it and no
  source gives one), so `evidence.api`'s client-data gate (SPEC-025 AC-7) refuses any client file
  on it with `acceptance`; the email channel itself is N-01's.
- The delegations to Keystone, Harborline, PayGrid and Summit. `delegate_item` gives a request to
  a contact who is a portal user. At E0 Sam Ortiz's invitation is pending (POR-01d), and no source
  names a Harborline, PayGrid or Summit person; POR-14 a (Sam in the room at E0, 4 of 9 uploaded)
  disagrees with POR-01d and with AUD-03's statuses. Keystone's 9 stay the invitation's grant
  template (`portal`).
- The returned 2024 form (POR-03 g, POR-04 d: a holdout, not the seeded day). Kevin Osei's return
  is a person's review decision (`evidence.decide`), which runs only while that person serves a
  request (ADR-005, REVIEW-001), so a loader cannot take it and the slice does not bootstrap one.
- The Feld received rows' files (the W-2 and 1098 emailed Aug 3, Jonah's 1099 Aug 5, Claire's
  donations Aug 7): the same client-data gate refuses them, and Jonah Feld has no portal sign-in
  in any slice.
- POR-02's "19 of 21 · 37 sorted": the 14 unnamed requests and 37 unnamed files (DEC-348).

Opt-in (`--slice portal_pbc`, which brings `binders` and `portal`); `build()` keeps its default,
so SCENARIO_HASH is unchanged.
"""

from __future__ import annotations

from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PBC_LISTS
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "portal_pbc"
NEEDS: Final = ("binders", "portal")  # `expand_slices` expands one level
NORTHWIND: Final = "Northwind Robotics, Inc."
# Marcus Delaney (Audit Manager on Northwind) edits the requests (SHL-14 a and b's viewer).
BY: Final = "MD"

# --- POR-03 i: Dana's own requests in the portal's words (DEC-348) ------------------------------

# AUD-03's title -> POR-03 i's, for the open rows Dana owns.
CLIENT_TITLES: Final[dict[str, str]] = {
    "W-3 Form": "W-3 for 2025",
    "Opt-Out Elections": "Opt-out elections — auto-enrolled employees",
    "Pay Rate Authorizations": "Pay rate authorizations",
    "Participant Complaints Log and Support": "Participant complaints log and support",
}
_NORTHWIND_LIST: Final = next(p for p in PBC_LISTS if p.key == "northwind")


def retitled() -> tuple[tuple[int, str, str], ...]:
    """(position, AUD-03's title, the client's title) for each request the slice retitles."""
    return tuple(
        (n, r.title, CLIENT_TITLES[r.title])
        for n, r in enumerate(_NORTHWIND_LIST.requests, 1)
        if r.title in CLIENT_TITLES
    )


@register_slice(SLICE)
def portal_pbc_events() -> list[Event]:
    return [
        Event(
            f"request-title:northwind:{position}",
            _NORTHWIND_LIST.created,
            "requests.item_retitled",
            BY,
            SLICE,
            {"list": _NORTHWIND_LIST.key, "position": position, "title": title},
            client=NORTHWIND,
        )
        for position, _, title in retitled()
    ]
