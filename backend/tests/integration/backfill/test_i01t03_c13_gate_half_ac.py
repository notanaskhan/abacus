# ac-test-author: ayushkbhatia
"""I-01-T03 (TASK-1304; ADR-078): the C13 gate half's acceptance suite, written before I-01-T04
and T07 open, against P-04's projection (`docs/contracts/home-and-gates.md`; I-01 §3, §4.3).

What the gate half must do for Home, tested from outside `review`:
- **one count source** by DF-25 band: `GET /v1/human-gates/counts` reads Daniel Reyes's
  11 = 3 + 6 + 2 as decisions, sign-offs and approvals & sends, and equals the list's total;
- **walls** leave a client out of every count (INV-3, DEC-43): nothing counts what was left out;
- **office** narrows the counts, never authorises them (DEC-30);
- **snooze** takes a gate out of every surface until `until`, within its due date (OQ-4);
- **reassign** goes through the owner's hook only (409 `not_reassignable` without one);
- **presentation facts** come with every row (band, title, blocked, bulk eligibility, route,
  overlay, glyph, actions, version, proposed_by for attribution, INV-5).

What already holds on main passes now (the list's counts per kind, the walls on the list). What
I-01-T04 and T07 add is a strict xfail citing TASK-1304, so the suite fails against the stub and
turns green when the gate half lands; I-01-T07 (TASK-1506) removed the last
xfails. The matrix and wire checks are in
`tests/contracts/c13_home/test_c13_gate_half.py`.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Final, cast

import pytest

from .support import Json, Person
from .test_p04t17_human_gates_independent import (
    Firm,
    _daniels_eleven,  # pyright: ignore[reportPrivateUsage] -- P-04-T17's seed of Daniel's eleven
    _deliver,  # pyright: ignore[reportPrivateUsage] -- the projector, driven as the worker drives it
    _event,  # pyright: ignore[reportPrivateUsage] -- a C13 event, as the relay hands it over
    _waiting,  # pyright: ignore[reportPrivateUsage] -- what a consumer source says waits now
    firm,
)

__all__ = ["firm"]
pytestmark = pytest.mark.asyncio

COUNTS: Final = "/v1/human-gates/counts"


async def _get(f: Firm, path: str, who: Person) -> tuple[int, Json]:
    response = await f.net.call("GET", path, who)
    return response.status_code, cast(Json, response.json())


# --- What holds on main: one query, Daniel's eleven by kind; walls on the list ----------------


async def test_ac_the_list_counts_daniels_eleven_per_kind_today(firm: Firm) -> None:
    await _daniels_eleven(firm)
    status, page = await firm.gates(firm.daniel)
    assert status == 200, page
    counts = {k: v for k, v in cast(dict[str, int], page["counts"]).items() if v}
    assert counts == {"decision": 3, "sign_off_request": 6, "export": 2}


async def test_inv3_a_walled_person_is_listed_nothing_of_the_walled_client(firm: Firm) -> None:
    _waiting(firm.tenant_id, "consumer_decision", firm.ashford.engagement_id, assignee=firm.lena)
    _waiting(firm.tenant_id, "consumer_decision", firm.bayside.engagement_id, assignee=firm.lena)
    for site in (firm.ashford, firm.bayside):
        await _deliver(_event(firm.tenant_id, site.engagement_id))
    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    status, page = await firm.gates(firm.lena)
    assert status == 200, page
    items = cast(list[Json], page["items"])
    assert {i["engagement_id"] for i in items} == {str(firm.bayside.engagement_id)}
    assert page["total"] == 1


# --- I-01-T04 (landed, TASK-1425): the one count source -------------------------------------


async def test_ac_f1_one_count_source_reads_eleven_as_three_six_two_by_band(firm: Firm) -> None:
    await _daniels_eleven(firm)
    status, counts = await _get(firm, COUNTS, firm.daniel)
    assert status == 200, counts
    assert counts["bands"] == {
        "decisions": 3,
        "sign_offs": 6,
        "agent_outputs": 0,
        "approvals_sends": 2,  # an export is Approvals & sends (DF-25)
    }
    assert counts["total"] == 11
    _status, page = await firm.gates(firm.daniel)
    assert page["total"] == counts["total"]  # the list and the badge agree


async def test_inv3_walls_leave_a_client_out_of_every_count(firm: Firm) -> None:
    await _daniels_eleven(firm)
    await firm.net.wall(firm.admin, firm.daniel, firm.ashford)
    status, counts = await _get(firm, COUNTS, firm.daniel)
    assert status == 200, counts
    # Ashford held 2 decisions and 4 sign-offs; nothing says anything was left out (DEC-43).
    assert counts["total"] == 5
    assert counts["bands"] == {
        "decisions": 1,
        "sign_offs": 2,
        "agent_outputs": 0,
        "approvals_sends": 2,
    }
    assert set(counts) <= {"total", "bands", "overdue", "snoozed"}


async def test_dec30_an_office_narrows_the_counts_and_never_authorises(firm: Firm) -> None:
    await _daniels_eleven(firm)
    unknown_office = uuid.uuid4()
    status, counts = await _get(firm, f"{COUNTS}?office_id={unknown_office}", firm.daniel)
    assert status == 200, counts
    assert counts["total"] == 0  # a filter, not a refusal
    status, counts = await _get(firm, COUNTS, firm.daniel)
    assert counts["total"] == 11


# --- I-01-T07: snooze, reassign, presentation facts ------------------------------------------


async def test_ac83_a_snoozed_gate_leaves_every_surface_until_its_time(firm: Firm) -> None:
    due = date.today() + timedelta(days=9)
    _waiting(
        firm.tenant_id,
        "consumer_decision",
        firm.bayside.engagement_id,
        assignee=firm.daniel,
        due_on=due,
    )
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    _status, page = await firm.gates(firm.daniel)
    gate = cast(list[Json], page["items"])[0]
    until = f"{(due - timedelta(days=1)).isoformat()}T09:00:00Z"
    response = await firm.net.call(
        "POST",
        f"/v1/human-gates/{gate['id']}/snooze",
        firm.daniel,
        body={"until": until},
    )
    assert response.status_code == 200, response.text
    _status, page = await firm.gates(firm.daniel)
    assert page["total"] == 0
    _status, counts = await _get(firm, COUNTS, firm.daniel)
    assert (counts["total"], counts["snoozed"]) == (0, 1)
    # Snoozing is per person: Hannah still sees the unassigned-to-her gate only if hers; the
    # snooze is Daniel's alone, so another assignee's counts are untouched.
    _status, hannah = await _get(firm, COUNTS, firm.hannah)
    assert hannah["snoozed"] == 0


async def test_oq4_a_snooze_is_never_past_due_or_in_the_past(firm: Firm) -> None:
    due = date.today() + timedelta(days=2)
    _waiting(
        firm.tenant_id,
        "consumer_decision",
        firm.bayside.engagement_id,
        assignee=firm.daniel,
        due_on=due,
    )
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    _status, page = await firm.gates(firm.daniel)
    gate_id = cast(list[Json], page["items"])[0]["id"]
    for until, code in (
        (f"{(due + timedelta(days=3)).isoformat()}T09:00:00Z", "snooze_past_due"),
        ("2020-01-01T09:00:00Z", "snooze_in_past"),
    ):
        response = await firm.net.call(
            "POST", f"/v1/human-gates/{gate_id}/snooze", firm.daniel, body={"until": until}
        )
        assert (response.status_code, response.json()["detail"]) == (422, code)


async def test_ac_reassign_needs_the_owners_hook(firm: Firm) -> None:
    """The consumer's decision source registered no reassign hook: the gate is not
    reassignable, and nothing changes."""
    _waiting(firm.tenant_id, "consumer_decision", firm.bayside.engagement_id, assignee=firm.daniel)
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    _status, page = await firm.gates(firm.daniel)
    gate = cast(list[Json], page["items"])[0]
    response = await firm.net.call(
        "POST",
        f"/v1/human-gates/{gate['id']}/reassign",
        firm.daniel,
        body={"to_user_id": str(firm.hannah.user_id), "seen_version": gate["version"]},
    )
    assert (response.status_code, response.json()["detail"]) == (409, "not_reassignable")
    _status, page = await firm.gates(firm.daniel)
    assert page["total"] == 1


async def test_ac_rows_carry_presentation_facts_and_attribution(firm: Firm) -> None:
    await _daniels_eleven(firm)
    _status, page = await firm.gates(firm.daniel)
    for item in cast(list[Json], page["items"]):
        assert {
            "subkind",
            "band",
            "title",
            "context",
            "blocked",
            "bulk_eligible",
            "subject_route",
            "overlay",
            "glyph",
            "allowed_actions",
            "version",
            "proposed_by",
        } <= set(item)
        assert item["band"] in {"decisions", "sign_offs", "agent_outputs", "approvals_sends"}
        # INV-5: a row names who proposed it (a run and its person), never the agent as decider.
        proposed = cast(Json | None, item["proposed_by"])
        assert proposed is None or set(proposed) == {"run_id", "initiator_user_id", "at"}
