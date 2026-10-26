"""P-07-T41 security review (DEC-429; TASK-1325): SPEC-025's route can no longer meet G2 (H1), an
independence answer is the acting person's own at the database (M1), a conclusion supersedes one
of the same engagement (L1), a decided NAS row is the partner's (L2), and conflict hits on a
client the reader is walled from carry no result id in the banner (L4).

Northwind's world comes from P-07-T43's suite (`test_p07t43_independence_independent`), which
stays unmodified.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow

from .support import Net
from .test_p07t43_independence_independent import (
    Json,
    Northwind,
    _json,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
    _ready,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
    _refusal,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
    _world,  # pyright: ignore[reportPrivateUsage] -- the suite's helpers
)

pytestmark = pytest.mark.asyncio

LEGACY = {
    "decision": "accepted",
    "documented_at": "Acceptance memo, 12 Oct",
    "independence_concluded": True,
    "independence_documented_at": "Independence memo",
}


@pytest.fixture
async def nw(net: Net) -> Northwind:
    return await _world(net)


# --- H1: SPEC-025's route never meets G2 -------------------------------------------------------


async def test_h1_with_v2_on_the_old_route_refuses_a_conclusion(nw: Northwind) -> None:
    refused = await nw.call("PUT", f"/v1/engagements/{nw.eid}/acceptance", nw.margaret, LEGACY)
    _refusal(refused, 409, "decision_locked")
    assert (await nw.gate("G2"))["met"] is False
    concluded = await nw.seed.value(
        "SELECT count(*) FROM engagement_acceptance WHERE engagement_id = $1 "
        "AND independence_concluded_at IS NOT NULL",
        nw.eid,
    )
    assert concluded == 0


async def test_h1_with_v2_off_a_conclusion_written_now_does_not_meet_g2(nw: Northwind) -> None:
    await nw.seed.run(
        "DELETE FROM feature_flag_states WHERE tenant_id = $1 "
        "AND flag = 'engagements.acceptance_v2'",
        nw.tenant,
    )
    forget_flags()
    recorded = await nw.call("PUT", f"/v1/engagements/{nw.eid}/acceptance", nw.margaret, LEGACY)
    assert recorded.status_code == 200, recorded.text
    rows = await nw.seed.rows(
        "SELECT legacy_g2, independence_concluded_at FROM engagement_acceptance "
        "WHERE engagement_id = $1",
        nw.eid,
    )
    assert [(r["legacy_g2"], r["independence_concluded_at"] is not None) for r in rows] == [
        (False, True)
    ]
    assert (await nw.gate("G2"))["met"] is False
    # A row from before 0175 (written outside the app) still stands until P-07-T59.
    await nw.seed.run(
        "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
        "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
        "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', 'seed', "
        "'Memo', 'seed', clock_timestamp(), 'Memo')",
        nw.tenant,
        nw.eid,
    )
    assert (await nw.gate("G2"))["met"] is True


# --- M1: an answer is the acting person's own ----------------------------------------------------


async def _answer_as(nw: Northwind, kind: str, actor: uuid.UUID, user: uuid.UUID) -> None:
    async with uow(TenantContext(nw.tenant, cast(ActorKind, kind), str(actor))) as tx:
        await tx.session.execute(
            text(
                "UPDATE independence_confirmations SET status = 'confirmed', "
                "answered_at = clock_timestamp() WHERE engagement_id = :e AND user_id = :u"
            ),
            {"e": nw.eid, "u": user},
        )
        tx.record("independence.probed", target=Target("engagement", nw.eid))


async def test_m1_the_database_refuses_an_answer_for_someone_else(nw: Northwind) -> None:
    with pytest.raises(DBAPIError):
        await _answer_as(nw, "human", nw.hannah.user_id, nw.ana.user_id)
    for kind in ("system", "agent"):
        with pytest.raises(DBAPIError):
            await _answer_as(nw, kind, nw.ana.user_id, nw.ana.user_id)
    status = await nw.seed.value(
        "SELECT status FROM independence_confirmations WHERE engagement_id = $1 AND user_id = $2",
        nw.eid,
        nw.ana.user_id,
    )
    assert status == "requested"
    # Reminders still count on other people's rows.
    sent = await nw.call(
        "POST", f"{nw.ind}/reminders", nw.hannah, {"user_ids": [str(nw.ana.user_id)]}
    )
    assert sent.status_code == 200, sent.text


# --- L1: a conclusion supersedes one of the same engagement -------------------------------------


async def test_l1_a_conclusion_cannot_supersede_another_engagements(nw: Northwind) -> None:
    await _ready(nw)
    first = _json(await nw.conclude(), 201)
    other = await nw.seed.site(nw.tenant, nw.grace.user_id, "Other", opened=False)
    await nw.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'engagement_partner')",
        nw.tenant,
        other.engagement_id,
        nw.margaret.user_id,
    )
    # As Margaret through the app's unit of work (the guard binds the acting person).
    with pytest.raises(IntegrityError) as refused:
        async with uow(TenantContext(nw.tenant, "human", str(nw.margaret.user_id))) as tx:
            await tx.session.execute(
                text(
                    "INSERT INTO independence_conclusions (tenant_id, engagement_id, option, "
                    "concluded_by, mfa_verified_at, supersedes_id) VALUES (:t, :e, "
                    "'independent', :by, now(), :prior)"
                ),
                {
                    "t": nw.tenant,
                    "e": other.engagement_id,
                    "by": nw.margaret.user_id,
                    "prior": uuid.UUID(cast(str, first["id"])),
                },
            )
            tx.record("independence.probed", target=Target("engagement", other.engagement_id))
    assert isinstance(refused.value.orig, Exception)
    assert "foreign key" in str(refused.value.orig).lower()


# --- L2: the partner's NAS decision stands -------------------------------------------------------


async def test_l2_a_manager_cannot_reopen_a_decided_nas_row_or_invent_a_service(
    nw: Northwind,
) -> None:
    await nw.designate_ske()
    await nw.evaluate_nas()
    reopened = await nw.call(
        "PUT",
        f"{nw.ind}/nas/tax_compliance",
        nw.hannah,
        {"provided": True, "status": "pending", "evaluation": "Reopen."},
    )
    _refusal(reopened, 409, "decision_locked")
    invented = await nw.call(
        "PUT",
        f"{nw.ind}/nas/bookkeeping",
        nw.margaret,
        {"provided": True, "status": "concluded", "evaluation": "Permitted."},
    )
    assert invented.status_code == 422, invented.text
    rows = cast(list[Json], _json(await nw.call("GET", f"{nw.ind}/nas", nw.margaret))["rows"])
    assert [(r["service_code"], r["status"]) for r in rows] == [("tax_compliance", "concluded")]


# --- L4: walled conflict hits carry no result id -------------------------------------------------


async def test_l4_a_walled_reader_sees_the_blocker_without_the_result(nw: Northwind) -> None:
    harborline = cast(
        uuid.UUID,
        await nw.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            nw.tenant,
            f"Harborline Capital {nw.site.marker}",
        ),
    )
    check = _json(
        await nw.call(
            "POST",
            "/v1/conflict-checks",
            nw.hannah,
            {
                "subject": {"kind": "client", "id": str(nw.site.client_id)},
                "names": [f"Harborline Capital {nw.site.marker}"],
            },
        ),
        201,
    )
    hit_ids = {cast(str, r["id"]) for r in cast(list[Json], check["results"])}
    _json(
        await nw.call(
            "POST",
            "/v1/walls",
            nw.grace,
            {"user_id": str(nw.mia.user_id), "client_id": str(harborline)},
        ),
        201,
    )

    def conflicts(summary: Json) -> list[tuple[str, str]]:
        return [
            (cast(str, b["ref_type"]), cast(str, b["ref_id"]))
            for b in cast(list[Json], summary["blockers"])
            if b["reason_code"] == "conflict_not_cleared"
        ]

    walled = conflicts(await nw.summary(nw.mia))
    assert walled == [("engagement", str(nw.eid))]
    seen = conflicts(await nw.summary(nw.hannah))
    assert {ref for kind, ref in seen if kind == "conflict_result"} == hit_ids
