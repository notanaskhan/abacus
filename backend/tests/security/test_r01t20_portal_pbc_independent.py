# ac-test-author: ayushkbhatia
"""R-01-T20 (ADR-078, TASK-1351): independent AC tests for AY's amber R-01-T07 (the portal PBC
read model), T08 (the ignore note and the undos), T11 (the scenario slice) and T13 (the
third-party room), written from the contract alone.

Sources: `docs/contracts/portal-pbc.md` (C5 section `portal-pbc`: §1 to §7), the screen
contracts `docs/screens/POR-03.md`, `POR-04.md` and `POR-14.md`, DEC-240, DEC-333, DEC-334,
DEC-387 and DEC-388, and the R-01 rows. Every call is a client's, over a portal session minted
through the pre-session routes on the firm's own host; the firm's acts (waive, delegate) go
through the firm's routes as a person.

The cast (synthetic): Brightwater Hale's Feld household binder; Claire Feld (client admin) and
Jonah Feld (a second owner); Dana Kowalski (contributor, her own requests only); Sam Ortiz of
Keystone Retirement Services (a third party with delegated requests).
"""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterator
from typing import cast

import httpx
import pytest

from abacus.modules.identity.api import RULES
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp

from .portal_pbc_support import (
    ACTIONS,
    CLIENT_WORDS,
    FIRM_WORDS,
    Binder,
    Json,
    new_binder,
    rows_of,
    signed_in,
)
from .support import Net


def _ok(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _refused(response: httpx.Response, status: int, detail: str) -> Json:
    assert response.status_code == status, response.text
    body = cast(Json, response.json())
    assert body["detail"] == detail, body
    return cast(Json, body.get("facts") or {})


@pytest.fixture(autouse=True)
def _portal_idp() -> Iterator[None]:
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)


async def _feld(net: Net) -> Binder:
    b = await new_binder(net, "Feld")
    await b.request("Form W-2 From Mercer Hill", "Income", status="received")
    await b.request("Form 1099-B From Halvard", "Income")
    await b.request("Form 1098 From Hudson Mutual", "Income", status="uploaded")
    await b.request("Form 1095-C From Mercer Hill Health", "Health & Medical")
    await b.request("Internal tie-out", "Income", visible=False)
    return b


# ================================================================================================
# R-01-T07: the read model (POR-03, POR-04)
# ================================================================================================


async def test_t07_claires_binder_is_in_client_words_and_its_counts_foot(net: Net) -> None:
    b = await _feld(net)
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    picker = _ok(await claire.get("/v1/portal/binders"))
    assert [i["id"] for i in cast(list[Json], picker["items"])] == [str(b.binder)]

    binder = _ok(await claire.get(f"/v1/portal/binders/{b.binder}?filter=all"))
    rows = rows_of(binder)
    titles = {cast(str, r["title"]) for r in rows}
    assert titles == {
        "Form W-2 From Mercer Hill",
        "Form 1099-B From Halvard",
        "Form 1098 From Hudson Mutual",
        "Form 1095-C From Mercer Hill Health",
    }
    words = {cast(str, r["title"]): r["client_status"] for r in rows}
    assert words["Form W-2 From Mercer Hill"] == "done"  # received → Done
    assert words["Form 1098 From Hudson Mutual"] == "done"  # uploaded → Done
    assert words["Form 1099-B From Halvard"] == "to_do"
    assert {r["client_status"] for r in rows} <= CLIENT_WORDS
    assert binder["total"] == len(rows) == 4
    assert binder["done_count"] == 2
    assert binder["open_count"] == 2
    # A category is complete when every request in it is Done or Ignored (code-computed).
    complete = {c["label"]: c["complete"] for c in cast(list[Json], binder["categories"])}
    assert complete == {"Income": False, "Health & Medical": False}
    for row in rows:
        assert set(cast(list[str], row["allowed_actions"])) <= ACTIONS, row
    assert set(cast(list[str], binder["allowed_actions"])) <= ACTIONS
    for word in FIRM_WORDS:
        assert word not in str(binder), word


async def test_t07_por04_reads_one_request_and_nothing_firm_side(net: Net) -> None:
    b = await _feld(net)
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    item = b.items["Form 1095-C From Mercer Hill Health"]
    request = _ok(await claire.get(f"/v1/portal/request-items/{item}"))
    assert (request["id"], request["binder_id"]) == (str(item), str(b.binder))
    assert request["client_status"] == "to_do"
    assert request["variant"] == "request"
    assert cast(Json, request["category"])["label"] == "Health & Medical"
    assert set(cast(list[str], request["allowed_actions"])) <= ACTIONS
    for word in FIRM_WORDS:
        assert word not in str(request), word
    internal = await claire.get(f"/v1/portal/request-items/{b.items['Internal tie-out']}")
    assert internal.status_code == 404


async def test_t07_dana_reads_only_her_own_requests(net: Net) -> None:
    b = await new_binder(net, "Northwind", kind="pbc", categories=("Census & Payroll",))
    dana, email = await b.client("Dana Kowalski", role="contributor")
    mine = await b.request("Census file — 2025", "Census & Payroll", assignee=dana)
    theirs = await b.request("Plan document and amendments", "Census & Payroll")
    portal = await signed_in(b, email)
    binder = _ok(await portal.get(f"/v1/portal/binders/{b.binder}?filter=all"))
    assert binder["layout"] == "bands"  # an audit binder (POR-03 i)
    assert [r["id"] for r in rows_of(binder)] == [str(mine)]
    assert "Plan document and amendments" not in str(binder)
    assert (await portal.get(f"/v1/portal/request-items/{theirs}")).status_code == 404
    assert binder.get("other_parties") in ([], None)  # admin grants only


async def test_t07_a_closed_binder_is_read_only(net: Net) -> None:
    b = await new_binder(net, "Feld-2024", status="closed")
    item = await b.request("Form 1099-INT From Harbor Bank", "Income")
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    binder = _ok(await claire.get(f"/v1/portal/binders/{b.binder}?filter=all"))
    assert cast(Json, binder["binder"])["read_only"] is True
    assert binder["allowed_actions"] == []
    assert all(r["allowed_actions"] == [] for r in rows_of(binder))
    request = _ok(await claire.get(f"/v1/portal/request-items/{item}"))
    assert request["allowed_actions"] == []


def test_t07_the_read_is_a_client_action_the_agent_never_holds() -> None:
    rule = RULES["portal_documents.read"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    staff = {"engagement_partner", "manager", "senior", "staff", "firm_admin"}
    assert not staff & {r for r, d in rule.decisions.items() if d != "deny"}


# ================================================================================================
# R-01-T08: the ignore note and the undos (DEC-24, DEC-334)
# ================================================================================================


async def test_t08_an_ignore_note_is_a_shared_comment_and_undo_returns_to_do(net: Net) -> None:
    b = await _feld(net)
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    item = b.items["Form 1099-B From Halvard"]
    note = f"No brokerage account in 2025 {uuid.uuid4().hex[:6]}"
    _ok(
        await claire.post(
            f"/v1/portal/request-items/{item}/ignore", {"reason": "dont_have", "note": note}
        )
    )
    request = _ok(await claire.get(f"/v1/portal/request-items/{item}"))
    assert request["client_status"] == "ignored"
    stored = await b.seed.rows(
        "SELECT origin, c::text AS t FROM comments c WHERE request_item_id = $1", item
    )
    assert [r["origin"] for r in stored] == ["ignore_note"]
    assert note not in cast(str, stored[0]["t"])  # sealed at rest

    key = uuid.uuid4().hex
    undone = _ok(await claire.post(f"/v1/portal/request-items/{item}/ignore/undo", key=key))
    assert (undone["request_item_id"], undone["client_status"]) == (str(item), "to_do")
    replay = _ok(await claire.post(f"/v1/portal/request-items/{item}/ignore/undo", key=key))
    assert replay == undone
    again = await claire.post(f"/v1/portal/request-items/{item}/ignore/undo", key=uuid.uuid4().hex)
    facts = _refused(again, 409, "nothing_to_undo")
    assert facts == {"request_item_id": str(item)}
    # Undo never deletes the note.
    assert (
        await b.seed.value(
            "SELECT count(*) FROM comments WHERE request_item_id = $1 AND origin = 'ignore_note'",
            item,
        )
        == 1
    )
    status = await b.seed.value("SELECT status FROM request_items WHERE id = $1", item)
    assert status == "requested"
    audit = await b.seed.rows(
        "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'request_item.ignore_undone'",
        b.tenant,
    )
    assert [r["actor_kind"] for r in audit] == ["human"]


async def test_t08_undo_after_the_firm_waived_is_firm_already_acted(net: Net) -> None:
    b = await _feld(net)
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    item = b.items["Form 1099-B From Halvard"]
    _ok(
        await claire.post(
            f"/v1/portal/request-items/{item}/ignore", {"reason": "sent_another_way"}
        )
    )
    waived = await b.firm(
        "POST",
        f"/v1/engagements/{b.eid}/request-items/{item}/waive",
        {"na_reason": "already_sent", "note": "Received from the broker directly."},
    )
    assert waived.status_code == 200, waived.text
    refused = await claire.post(
        f"/v1/portal/request-items/{item}/ignore/undo", key=uuid.uuid4().hex
    )
    facts = _refused(refused, 409, "firm_already_acted")
    assert facts == {"request_item_id": str(item)}


async def test_t08_only_the_person_who_ignored_undoes_it(net: Net) -> None:
    b = await _feld(net)
    _, claire_email = await b.client("Claire Feld")
    _, jonah_email = await b.client("Jonah Feld")
    claire = await signed_in(b, claire_email)
    jonah = await signed_in(b, jonah_email)
    item = b.items["Form 1099-B From Halvard"]
    _ok(await claire.post(f"/v1/portal/request-items/{item}/ignore", {"reason": "dont_have"}))
    refused = await jonah.post(
        f"/v1/portal/request-items/{item}/ignore/undo", key=uuid.uuid4().hex
    )
    assert refused.status_code == 403, refused.text
    assert _ok(await claire.get(f"/v1/portal/request-items/{item}"))["client_status"] == "ignored"


async def test_t08_mark_as_done_can_be_undone_until_the_firm_acts(net: Net) -> None:
    b = await new_binder(net, "Feld-done")
    await b.request("Form W-2 From Mercer Hill", "Income", status="received")
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    marked = await claire.post(f"/v1/portal/binders/{b.binder}/mark-done")
    assert marked.status_code == 200, marked.text
    key = uuid.uuid4().hex
    undone = _ok(await claire.post(f"/v1/portal/binders/{b.binder}/mark-done/undo", key=key))
    assert undone["binder_id"] == str(b.binder)
    assert undone["mark_done"] in ("tonal", "ready")
    assert (
        _ok(await claire.post(f"/v1/portal/binders/{b.binder}/mark-done/undo", key=key)) == undone
    )
    facts = _refused(
        await claire.post(f"/v1/portal/binders/{b.binder}/mark-done/undo", key=uuid.uuid4().hex),
        409,
        "nothing_to_undo",
    )
    assert facts == {"binder_id": str(b.binder)}


async def test_t08_the_undos_need_an_idempotency_key(net: Net) -> None:
    b = await _feld(net)
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    item = b.items["Form 1099-B From Halvard"]
    _ok(await claire.post(f"/v1/portal/request-items/{item}/ignore", {"reason": "dont_have"}))
    assert (await claire.post(f"/v1/portal/request-items/{item}/ignore/undo")).status_code == 422
    assert _ok(await claire.get(f"/v1/portal/request-items/{item}"))["client_status"] == "ignored"


def test_t08_the_agent_holds_no_client_act() -> None:
    for action in ("request_item.ignore", "binder.mark_done"):
        assert RULES[action].decisions.get("agent") == "deny", action


# ================================================================================================
# R-01-T13: the third-party room (POR-14; DEC-387, DEC-388)
# ================================================================================================


async def _keystone(net: Net) -> tuple[Binder, list[uuid.UUID], uuid.UUID, str]:
    b = await new_binder(
        net, "Northwind", kind="pbc", categories=("Recordkeeper reports", "SOC 1 & fees", "Census")
    )
    delegated = [
        await b.request("Schedule of account balances — 12/31/2025", "Recordkeeper reports"),
        await b.request("Annual participant loan roll-forward — 2025", "Recordkeeper reports"),
        await b.request("SOC 1 Type 2 report — Oct 1, 2024 to Sep 30, 2025", "SOC 1 & fees"),
    ]
    await b.request("Census file — 2025", "Census")
    _, contact, email = await b.outsider("Sam Ortiz", "Keystone Retirement Services")
    for item in delegated:
        found = await b.delegate(item, contact)
        assert found.status_code == 201, found.text
    return b, delegated, contact, email


async def test_t13_sams_room_holds_exactly_the_delegated_requests(net: Net) -> None:
    b, delegated, _, email = await _keystone(net)
    sam = await signed_in(b, email)
    room = _ok(await sam.get("/v1/portal/room"))
    ids = [
        str(r["id"])
        for band in cast(list[Json], room["bands"])
        for r in cast(list[Json], band["rows"])
    ]
    assert sorted(ids) == sorted(str(i) for i in delegated)
    assert (room["uploaded_count"], room["total"], room["complete"]) == (0, 3, False)
    assert room["firm_name"] == b.firm_name
    assert room["organisation_name"] == "Keystone Retirement Services"
    bands = {
        cast(str, band["label"]): (band["uploaded"], band["total"])
        for band in cast(list[Json], room["bands"])
    }
    assert bands == {"Recordkeeper reports": (0, 2), "SOC 1 & fees": (0, 1)}
    assert "Census file" not in str(room)
    for band in cast(list[Json], room["bands"]):
        for row in cast(list[Json], band["rows"]):
            assert row["state"] in ("uploaded", "due", "in_review", "returned")
            assert set(cast(list[str], row["allowed_actions"])) <= {
                "upload",
                "withdraw",
                "comment",
            }


async def test_t13_the_client_admin_no_longer_reads_a_delegated_request(net: Net) -> None:
    b, delegated, _, _ = await _keystone(net)
    _, email = await b.client("Dana Kowalski")
    dana = await signed_in(b, email)
    binder = _ok(await dana.get(f"/v1/portal/binders/{b.binder}?filter=all"))
    assert [r["title"] for r in rows_of(binder)] == ["Census file — 2025"]
    assert binder["other_parties"] == ["Keystone Retirement Services"]
    for item in delegated:
        assert (await dana.get(f"/v1/portal/request-items/{item}")).status_code == 404
    # A full-client person has no room.
    assert (await dana.get("/v1/portal/room")).status_code == 404


async def test_t13_suggest_preselects_by_shared_words_and_writes_nothing(net: Net) -> None:
    b, delegated, _, email = await _keystone(net)
    sam = await signed_in(b, email)
    before = await b.seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", b.tenant)
    names = [
        "Keystone_SOC1_Type2_report_2025.pdf",
        "participant_loan_rollforward.xlsx",
        "Scan_0914.pdf",
        "Census_2025.csv",
    ]
    out = _ok(await sam.post("/v1/portal/room/suggest", {"file_names": names}))
    picked = {
        cast(str, s["file_name"]): s.get("request_item_id")
        for s in cast(list[Json], out["suggestions"])
    }
    assert picked[names[0]] == str(delegated[2])
    assert picked[names[1]] == str(delegated[1])
    assert picked[names[2]] is None
    assert picked[names[3]] is None  # never a request outside the room
    after = await b.seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", b.tenant)
    assert after == before
    assert (await sam.post("/v1/portal/room/suggest", {"file_names": []})).status_code == 422


async def test_t13_a_tax_engagement_is_never_delegated_without_consent(net: Net) -> None:
    b = await new_binder(net, "Feld-tax")
    item = await b.request("Form 1099-B From Halvard", "Income")
    await b.seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1040', $5)",
        b.tenant,
        b.eid,
        b.site.client_id,
        b.site.entity_id,
        b.admin.user_id,
    )
    _, contact, _ = await b.outsider("Marta Lindqvist", "Halvard Securities")
    facts = _refused(await b.delegate(item, contact), 409, "consent_required")
    assert facts == {"engagement_id": str(b.eid)}
    assert (
        await b.seed.value(
            "SELECT count(*) FROM request_delegations WHERE request_item_id = $1", item
        )
        == 0
    )
    assert (
        await b.seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1 AND scope_id = $2",
            b.tenant,
            item,
        )
        == 0
    )


async def test_t13_the_room_answers_404_with_its_flag_off(net: Net) -> None:
    b, _, _, email = await _keystone(net)
    sam = await signed_in(b, email)
    await b.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'portal.third_party_room'",
        b.tenant,
    )
    assert (await sam.get("/v1/portal/room")).status_code == 404


# ================================================================================================
# R-01-T11: the scenario slice (blocked: DEC-348 open, TASK-1221)
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1221 (R-01-T11 blocked on DEC-348): the portal_pbc scenario slice is not built, "
        "so `make seed-demo` cannot load the POR-03, POR-04 and POR-14 persona states"
    ),
)
def test_t11_the_portal_pbc_slice_is_registered_for_seed_demo() -> None:
    slice_module = importlib.import_module(
        "abacus_tools.synthetic.scenarios.brightwater_hale.portal_pbc"
    )
    assert slice_module is not None
