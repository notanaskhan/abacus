"""P-04-T22 acceptance (TASK-1401; R-SO-7; SHL-12 f): bulk sign-off.

"Six workpapers with three ineligible return three signed and three excluded with reasons, and a
replay with the same key returns the stored result." Plus: the same key with another body is
refused, reviewers only, a fresh second factor, never the agent, and a hidden target is excluded
without saying whether it exists.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import cast

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity.api import agent_context_for_run

from .conftest import MigratedDatabase
from .review_support import PROBE, REVIEWER, Cast, as_, make_cast

pytestmark = pytest.mark.asyncio
SEEN = "sha256:" + "a" * 64


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture
async def team(migrated_db: MigratedDatabase) -> Cast:
    return await make_cast(migrated_db.superuser_dsn)


def _body(targets: list[tuple[uuid.UUID, str]], level: str = "L2_reviewer") -> dict[str, object]:
    return {
        "targets": [
            {"target_type": PROBE, "target_id": str(t), "seen_hash": seen} for t, seen in targets
        ],
        "level": level,
        "statement_version": REVIEWER,
    }


async def _six(team: Cast) -> list[tuple[uuid.UUID, str]]:
    """Six prepared workpapers; three can't be signed at L2 by Hannah: one changed since she
    looked, one with an open note, one she prepared herself."""
    papers = [team.probe(label=name) for name in (
        "Trial Balance", "Service Organizations & SOC 1", "Materiality",
        "General Audit Planning", "Internal Control", "Investments & Certification",
    )]  # fmt: skip
    for paper in papers[:5]:
        assert (await team.sign("ana", paper, "L1_preparer")).status_code == 201
    assert (await team.sign("hannah", papers[5], "L1_preparer")).status_code == 201
    await team.seed.as_actor(
        team.tenant,
        ("human", str(team["margaret"].user_id)),
        "INSERT INTO reviewable_notes (tenant_id, engagement_id, target_type, target_id, "
        "anchor, body, raised_by) VALUES ($1, $2, $3, $4, 'RA!C14', 'Tie this.', $5)",
        team.tenant,
        team.engagement,
        PROBE,
        papers[4],
        team["margaret"].user_id,
    )
    seen = [SEEN] * 6
    seen[3] = "sha256:" + "0" * 64  # General Audit Planning changed since Hannah looked
    return list(zip(papers, seen, strict=True))


async def test_ac_six_with_three_ineligible_and_a_replay_returns_the_stored_result(
    team: Cast,
) -> None:
    six = await _six(team)
    key = str(uuid.uuid4())
    call = team.call("hannah")
    first = await call(
        "POST", "/v1/sign-offs:bulk", json=_body(six), headers={"Idempotency-Key": key}
    )
    assert first.status_code == 200, first.text
    result = first.json()
    assert (result["signed"], result["excluded"]) == (3, 3)
    by_target = {r["target_id"]: r for r in result["results"]}
    assert [by_target[str(t)]["detail"] for t, _ in six] == [
        None,
        None,
        None,
        "content_changed",
        "open_review_notes",
        "segregation",
    ]
    assert all(by_target[str(t)]["sign_off_id"] for t, _ in six[:3])

    rows = await team.seed.rows(
        "SELECT target_id, bulk_request_id FROM sign_offs WHERE tenant_id = $1 AND level = 2",
        team.tenant,
    )
    assert sorted(str(r["target_id"]) for r in rows) == sorted(str(t) for t, _ in six[:3])
    assert len({r["bulk_request_id"] for r in rows}) == 1 and rows[0]["bulk_request_id"]
    assert str(rows[0]["bulk_request_id"]) != key  # derived, never the key itself
    audited = await team.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'sign_off.recorded'"
        " AND after_ref->>'level' = '2'",
        team.tenant,
    )
    assert audited == 3

    replay = await call(
        "POST", "/v1/sign-offs:bulk", json=_body(six), headers={"Idempotency-Key": key}
    )
    assert replay.status_code == 200 and replay.json() == result
    assert (
        await team.value(
            "SELECT count(*) FROM sign_offs WHERE tenant_id = $1 AND level = 2", team.tenant
        )
        == 3
    )

    other = await call(
        "POST", "/v1/sign-offs:bulk", json=_body(six[:2]), headers={"Idempotency-Key": key}
    )
    assert (other.status_code, other.json()["detail"]) == (422, "idempotency_key_reused")


async def test_a_key_is_the_callers_own(team: Cast) -> None:
    """The same key from another reviewer is their own request, not a replay of Hannah's."""
    six = await _six(team)
    key = str(uuid.uuid4())
    first = await team.call("hannah")(
        "POST", "/v1/sign-offs:bulk", json=_body(six[:1]), headers={"Idempotency-Key": key}
    )
    assert first.json()["signed"] == 1
    margaret = await team.call("margaret")(
        "POST",
        "/v1/sign-offs:bulk",
        json=_body(six[:1], "L3_manager"),
        headers={"Idempotency-Key": key},
    )
    assert margaret.status_code == 200, margaret.text
    assert margaret.json()["signed"] == 1


async def test_reviewers_only_fresh_mfa_and_never_the_agent(team: Cast) -> None:
    six = await _six(team)
    body = _body(six[:2])

    def key() -> dict[str, str]:
        return {"Idempotency-Key": str(uuid.uuid4())}

    staff = await team.call("ana")("POST", "/v1/sign-offs:bulk", json=body, headers=key())
    assert staff.status_code == 403  # reviewers only (R-SO-7)

    stale = await team.call("hannah", mfa_age=timedelta(minutes=20))(
        "POST", "/v1/sign-offs:bulk", json=body, headers=key()
    )
    assert stale.status_code == 403
    assert stale.json() == {"detail": "mfa_required", "facts": {"max_age_s": 900}}

    agent = await agent_context_for_run(
        tenant_id=team.tenant,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=team.engagement,
        task_scope=frozenset({"sign_off.bulk", "sign_off.create", "sign_off.review"}),
        initiator_user_id=team["margaret"].user_id,
    )
    refused = await as_(agent)("POST", "/v1/sign-offs:bulk", json=body, headers=key())
    assert refused.status_code == 403
    no_key = await team.call("hannah")("POST", "/v1/sign-offs:bulk", json=body)
    assert no_key.status_code == 422
    assert (
        await team.value(
            "SELECT count(*) FROM sign_offs WHERE tenant_id = $1 AND level = 2", team.tenant
        )
        == 0
    )


async def test_a_hidden_or_unknown_target_is_excluded_without_saying_which(
    team: Cast, migrated_db: MigratedDatabase
) -> None:
    other = await make_cast(migrated_db.superuser_dsn)
    theirs = other.probe()
    assert (await other.sign("ana", theirs, "L1_preparer")).status_code == 201
    mine = (await _six(team))[0]
    found = await team.call("hannah")(
        "POST",
        "/v1/sign-offs:bulk",
        json=_body([mine, (theirs, SEEN), (uuid.uuid4(), SEEN)]),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert found.status_code == 200, found.text
    details = [r["detail"] for r in found.json()["results"]]
    assert details == [None, "level_not_permitted", "level_not_permitted"]
    assert (
        await other.value(
            "SELECT count(*) FROM sign_offs WHERE target_id = $1 AND level = 2", theirs
        )
        == 0
    )
    only_hidden = await team.call("hannah")(
        "POST",
        "/v1/sign-offs:bulk",
        json=_body([(theirs, SEEN), (uuid.uuid4(), SEEN)]),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert only_hidden.status_code == 403
    duplicate = await team.call("hannah")(
        "POST",
        "/v1/sign-offs:bulk",
        json=_body([mine, mine]),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert duplicate.status_code == 422
    assert cast(str, duplicate.json()["detail"]) == "sign_off_invalid"
