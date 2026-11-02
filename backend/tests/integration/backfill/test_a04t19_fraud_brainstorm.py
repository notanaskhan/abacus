"""A-04-T19 (TASK-3005; A-04 §3.2 AC2.3-AC2.5; SPEC-620; DEC-2055).

Row acceptance: "Margaret approves the minutes while Marcus gets 403, Escalate on the PBC GAP flag
yields a draft request nothing sends, and Dana's questionnaire stays Draft until Hannah sends it."

Boundary: `create_app()` over HTTP on the migrated test database (the A-04 backfill world: the
engagement partner, a manager and a senior on Northwind). The partner approves; the senior is
refused by the matrix; an edit of the minutes after approval returns them to Awaiting approval at
the new hash; the EQR is never an attendee; a stale hash answers 409 `minutes_changed`.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.fraud_brainstorm import minutes_gate, minutes_hash

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("assurance.risk_register",)
MINUTES: Final = (
    "The team discussed how fraud could occur in contributions and benefit payments; management "
    "override is presumed; no team member raised an override not already in the register."
)


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T19') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    return found


def _path(world: Books, rest: str = "") -> str:
    return f"/v1/engagements/{world.site.engagement_id}/fraud-brainstorm{rest}"


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _session(world: Books, version: int = 0) -> Json:
    response = await world.call(
        "PUT",
        _path(world),
        world.senior,
        {
            "expected_version": version,
            "held_at": "2026-09-10T15:00:00Z",
            "medium": "video",
            "led_by_user_id": str(world.partner.user_id),
            "attendee_user_ids": [
                str(p.user_id) for p in (world.partner, world.manager, world.senior)
            ],
            "excluded": [],
        },
        headers=_keyed(),
    )
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def _minutes(world: Books, version: int, text: str = MINUTES) -> Json:
    response = await world.call(
        "PUT",
        _path(world, "/minutes"),
        world.senior,
        {"expected_version": version, "text": text},
        headers=_keyed(),
    )
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def test_ac2_4_the_partner_approves_the_minutes_and_the_senior_is_refused(
    world: Books,
) -> None:
    session = await _session(world)
    written = await _minutes(world, cast(int, session["row_version"]))
    assert written["minutes_status"] == "awaiting_approval"
    assert written["minutes_source"] == "human"
    assert written["minutes_hash"] == minutes_hash(MINUTES)
    assert not await minutes_gate(
        TenantContext(world.tenant_id, "system", "a04t19"), world.site.engagement_id
    )

    refused = await world.call(
        "POST",
        _path(world, "/minutes/approve"),
        world.senior,
        {"minutes_hash": written["minutes_hash"]},
        headers=_keyed(),
    )
    assert refused.status_code == 403, refused.text

    approved = await world.call(
        "POST",
        _path(world, "/minutes/approve"),
        world.partner,
        {"minutes_hash": written["minutes_hash"]},
        headers=_keyed(),
    )
    assert approved.status_code == 200, approved.text
    body = cast(Json, approved.json())
    assert body["minutes_status"] == "approved"
    assert body["approved_by_name"] == "Hannah Leclerc"
    assert await minutes_gate(
        TenantContext(world.tenant_id, "system", "a04t19"), world.site.engagement_id
    )
    rows = await world.seed.value(
        "SELECT count(*) FROM fraud_minutes_approvals WHERE tenant_id = $1 AND actor_kind = 'human'",
        world.tenant_id,
    )
    assert rows == 1


async def test_ac2_4_a_stale_hash_is_refused_and_an_edit_resets_approval(world: Books) -> None:
    session = await _session(world)
    written = await _minutes(world, cast(int, session["row_version"]))
    stale = await world.call(
        "POST",
        _path(world, "/minutes/approve"),
        world.partner,
        {"minutes_hash": "0" * 64},
        headers=_keyed(),
    )
    assert stale.status_code == 409 and cast(Json, stale.json())["code"] == "minutes_changed"
    await world.call(
        "POST",
        _path(world, "/minutes/approve"),
        world.partner,
        {"minutes_hash": written["minutes_hash"]},
        headers=_keyed(),
    )
    current = cast(Json, (await world.call("GET", _path(world), world.senior)).json())
    edited = await _minutes(world, cast(int, current["row_version"]), MINUTES + " Revised.")
    assert edited["minutes_status"] == "awaiting_approval"
    assert edited["approved_by_name"] is None


async def test_ac2_4_the_eqr_is_never_an_attendee(world: Books) -> None:
    eqr = await world.seed.person(world.tenant_id)
    await world.seed.member(world.site, eqr, "eqr_reviewer")
    response = await world.call(
        "PUT",
        _path(world),
        world.senior,
        {"expected_version": 0, "attendee_user_ids": [str(eqr.user_id)], "excluded": []},
        headers=_keyed(),
    )
    assert response.status_code == 422
    assert cast(Json, response.json())["code"] == "eqr_must_be_excluded"


async def test_ac2_4_a_stale_session_edit_answers_version_conflict(world: Books) -> None:
    await _session(world)
    again = await world.call(
        "PUT",
        _path(world),
        world.senior,
        {"expected_version": 0, "attendee_user_ids": [], "excluded": []},
        headers=_keyed(),
    )
    assert again.status_code == 409


async def test_ac2_4_adopting_goes_through_the_suggestion_route(world: Books) -> None:
    session = await _session(world)
    response = await world.call(
        "PUT",
        _path(world, "/minutes"),
        world.senior,
        {"expected_version": session["row_version"], "adopt_suggestion_id": str(uuid.uuid4())},
        headers=_keyed(),
    )
    assert response.status_code == 422
    assert cast(Json, response.json())["code"] == "adopt_through_suggestion"


async def test_ac2_5_a_governance_inquiry_is_recorded_and_reads_requested(world: Books) -> None:
    response = await world.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/fraud-inquiries",
        world.manager,
        {
            "governance_body_ref": "Plan administrative committee",
            "questionnaire_template_id": str(uuid.uuid4()),
        },
        headers=_keyed(),
    )
    assert response.status_code == 201, response.text
    body = cast(Json, response.json())
    assert body["status"] == "requested" and body["sent"] is False
    assert body["questionnaire_id"] is None
