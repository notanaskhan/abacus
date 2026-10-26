"""P-07-T42 security review (TASK-1326; DEC-430): the intake's conflict check is bound to the
draft's names (H1), re-read in the commit's unit of work (L2), a replay re-applies walls (L3),
a committed or discarded draft is final in the database (L1) and keeps identifiers only (L5).

Built on P-07-T44's world (Brightwater Hale: Grace adds the Thornbury estate under Walter)."""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session

from .support import Net
from .test_p07t44_intake_commit_independent import (
    DRAFTS,
    Json,
    World,
    _json,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
    _refusal,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
    _world,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def w(net: Net) -> World:
    return await _world(net)


async def _check(w: World, draft_id: object, names: list[str]) -> Json:
    return _json(
        await w.call(
            "POST",
            "/v1/conflict-checks",
            w.grace,
            {"subject": {"kind": "client_intake_draft", "id": str(draft_id)}, "names": names},
        ),
        201,
    )


async def _clear_all(w: World, check: Json) -> None:
    for result in cast(list[Json], check["results"]):
        _json(
            await w.call(
                "POST",
                f"/v1/conflict-checks/{check['id']}/results/{result['id']}/clear",
                w.samuel,
                {"assessment": "same_family_not_adverse", "reason": "The decedent's estate."},
            )
        )


async def test_h1_scenario_a_the_callers_names_are_not_what_is_searched(w: World) -> None:
    """A check on the draft with names `["zz"]` searches the draft's own names instead (the
    estate, Paul Thornbury and the existing client Walter), so Walter's match stands and the
    commit is refused until a person clears it."""
    draft = await w.draft(w.payload())
    check = await _check(w, draft["id"], ["zz"])
    assert check["names_count"] == 3
    assert check["results"] and check["outcome"] == "hits"
    draft = await w.save(draft, w.payload(check=check["id"]))
    facts = _refusal(await w.commit_intake(draft), 409, "gate_unmet")
    assert facts.get("gate") == "conflict_check"
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")
    # Cleared by Samuel, the same check now lets the commit through.
    await _clear_all(w, check)
    _json(await w.commit_intake(draft), 201)


async def test_h1_a_check_on_a_draft_with_no_names_is_refused(w: World) -> None:
    draft = await w.draft()
    response = await w.call(
        "POST",
        "/v1/conflict-checks",
        w.grace,
        {"subject": {"kind": "client_intake_draft", "id": str(draft["id"])}, "names": ["zz"]},
    )
    _refusal(response, 422, "invalid")


async def test_h1_scenario_b_a_name_changed_after_clearance_needs_a_new_check(w: World) -> None:
    draft = await w.draft(w.payload())
    check = await _check(w, draft["id"], ["anything"])
    await _clear_all(w, check)
    draft = await w.save(draft, w.payload(check=check["id"]))

    # Another contact name under the old clearance: refused.
    swapped = await w.save(
        draft, w.payload(check=check["id"], contact_name=f"Harborline Custodial {w.marker}")
    )
    _refusal(await w.commit_intake(swapped), 409, "gate_unmet")
    # Another client: refused too.
    other = w.payload(check=check["id"])
    cast(Json, other["entity"])["entity_name"] = f"Calloway Family Trust {w.marker}"
    swapped = await w.save(swapped, other)
    _refusal(await w.commit_intake(swapped), 409, "gate_unmet")
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")

    # Back to the names the check searched: the clearance holds again.
    restored = await w.save(swapped, w.payload(check=check["id"]))
    _json(await w.commit_intake(restored), 201)


async def test_l1_l5_a_committed_draft_is_final_and_keeps_identifiers_only(w: World) -> None:
    draft = await w.ready()
    done = _json(await w.commit_intake(draft), 201)
    row = (
        await w.seed.rows(
            "SELECT payload::text AS payload, result FROM client_intake_drafts WHERE id = $1",
            uuid.UUID(cast(str, draft["id"])),
        )
    )[0]
    assert row["payload"] == "{}"
    assert row["result"] is not None and str(done["client_id"]) in str(row["result"])
    discarded = await w.draft()
    _json(await w.call("DELETE", f"{DRAFTS}/{discarded['id']}", w.grace))
    as_app = TenantContext(w.tenant, "human", str(w.grace.user_id))
    for final in (draft["id"], discarded["id"]):
        with pytest.raises(DBAPIError, match="final"):
            async with tenant_session(as_app) as session:
                await session.execute(
                    text("UPDATE client_intake_drafts SET step = 'review' WHERE id = :id"),
                    {"id": uuid.UUID(cast(str, final))},
                )


async def test_l3_a_replay_re_applies_walls(w: World) -> None:
    draft = await w.ready()
    key = f"thornbury-{w.marker}-walled"
    _json(await w.commit_intake(draft, key=key), 201)
    await w.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        w.tenant,
        w.grace.user_id,
        w.walter,
        w.daniel.user_id,
    )
    assert (await w.commit_intake(draft, key=key)).status_code == 404
    assert (await w.call("GET", f"{DRAFTS}/{draft['id']}", w.grace)).status_code == 404
