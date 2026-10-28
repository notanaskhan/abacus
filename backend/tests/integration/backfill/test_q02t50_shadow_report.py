"""Q-02-T50 (DEC-811; SPEC-036 Q1; QD-10), against the migrated Postgres and the app over HTTP:

- The shadow score read from the database reproduces a hand-computed agreement, disagreement and
  override rate; a live run, an agent's other runs and a decision after `as_of` are not counted.
- `live` is refused without a named report (`shadow_report_required`), with a digest that is not
  the score as of the named instant (`shadow_report_changed`), with a report older than seven days
  (`shadow_report_stale`), and on data that fails QD-10 (`stage_not_ready`); a passing report
  named by its digest sets the stage. Nothing is written for a refusal.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import ShadowScore, shadow_score
from abacus.modules.identity.api import configure_staff_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Net, Seeder

STAGES = "/v1/platform/agent-stages"
SCREENER = "evidence.screener"

RUN = (
    "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
    "evidence_version_id, initiator_user_id, task_scope, status, started_at, finished_at, "
    "shadow, failure_code) VALUES ($1, $2, $3, 1, $4, $5, $6, ARRAY['evidence.read'], "
    "'completed', $7, $7, $8, $9)"
)
RESULT = (
    "INSERT INTO screening_results (id, tenant_id, engagement_id, evidence_version_id, "
    "agent_run_id, action, confidence, rationale, citations, unverified, created_by_kind, "
    "created_at) VALUES ($1, $2, $3, $4, $5, $6, 0.5, 'Scored in shadow', '[]', '[]', 'agent', $7)"
)
DECISION = (
    "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
    "request_item_id, decision, reason_code, screening_result_id, corrects_proposal, actor_kind, "
    "actor_id, decision_seq, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, false, 'human', "
    "'reviewer', 1, $8)"
)


@pytest.fixture
def staff() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider(issuer="https://staff.example.test", kid="staff-1")
    configure_staff_verifier(provider.verifier())
    yield provider
    configure_staff_verifier(None)


async def _shadow(
    seed: Seeder,
    tenant: uuid.UUID,
    first: datetime,
    runs: int,
    scored: list[tuple[str, str]],
    *,
    extra: list[tuple[str, bool, str, str, datetime]] | None = None,
) -> None:
    """`runs` shadow screener runs six hours apart from `first`; the first `len(scored)` of them
    proposed `action` and a person decided `decision` an hour later. `extra`: (agent, shadow,
    action, decision, decided at) runs that must not count. Prerequisite rows no test builds
    (engagement, versions, items) are skipped: triggers and foreign keys off for the seed."""
    engagement, user = uuid.uuid4(), uuid.uuid4()
    rows: list[tuple[str, bool, str | None, str | None, datetime, datetime]] = []
    for i in range(runs):
        at = first + timedelta(hours=6 * i)
        action, decision = scored[i] if i < len(scored) else (None, None)
        rows.append((SCREENER, True, action, decision, at, at + timedelta(hours=1)))
    rows += [(a, s, act, d, first, when) for a, s, act, d, when in extra or []]
    statements: list[tuple[str, tuple[object, ...]]] = []
    for agent, shadow, action, decision, at, decided in rows:
        run, version, result = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        statements.append((RUN, (run, tenant, agent, engagement, version, user, at, shadow, None)))
        if action is None or decision is None:
            continue
        statements.append((RESULT, (result, tenant, engagement, version, run, action, at)))
        reason = None if decision == "accept" else "other"
        item = uuid.uuid4()
        statements.append(
            (DECISION, (tenant, engagement, version, item, decision, reason, result, decided))
        )
    await seed.run_untriggered_many(statements)


def _passing() -> list[tuple[str, str]]:
    # 30 scored: 20 ready and accepted, 8 flagged and sent back, 2 flagged but accepted.
    return (
        [("ready_for_review", "accept")] * 20
        + [("needs_revision", "send_back")] * 8
        + [("needs_revision", "accept")] * 2
    )


async def _score(tenant: uuid.UUID, as_of: datetime) -> ShadowScore:
    return await shadow_score(TenantContext(tenant, "system", "q02t50"), SCREENER, as_of)


async def _stages(seed: Seeder, tenant: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT stage FROM agent_stages WHERE tenant_id = $1 ORDER BY created_at", tenant
    )
    return [str(r["stage"]) for r in rows]


async def test_the_score_from_the_database_reproduces_the_hand_count(
    seed: Seeder,
) -> None:
    tenant = await seed.firm()
    as_of = system_now().replace(microsecond=0)
    first = as_of - timedelta(days=20)
    later = as_of + timedelta(hours=1)
    await _shadow(
        seed,
        tenant,
        first,
        60,
        _passing(),
        extra=[
            (SCREENER, False, "ready_for_review", "reject", first),  # a live run
            ("evidence.matcher", True, "ready_for_review", "reject", first),  # another agent
            (SCREENER, True, "ready_for_review", "reject", later),  # decided after as_of
        ],
    )
    found = await _score(tenant, as_of)
    assert (found.runs, found.days, found.scored, found.agreed) == (61, 20, 30, 28)
    assert found.disagreement == "0.0667"
    assert found.override.rate == Decimal("0.0667")
    assert (found.de1_misses, found.de4_misses, found.de5_misses) == (0, 0, 0)
    assert found.passes
    assert (await _score(tenant, as_of)).sha256 == found.sha256
    # Once the late decision is in, the score as of a later instant is a different report.
    afterwards = await _score(tenant, later + timedelta(minutes=1))
    assert afterwards.de1_misses == 1 and not afterwards.passes
    assert afterwards.sha256 != found.sha256


async def test_live_needs_the_named_passing_report(
    net: Net, seed: Seeder, staff: FakeIdentityProvider
) -> None:
    tenant = await seed.firm()
    now = system_now().replace(microsecond=0)
    as_of = now - timedelta(hours=1)
    await _shadow(seed, tenant, now - timedelta(days=20), 60, _passing())
    report = await _score(tenant, as_of)
    assert report.passes
    headers = {"Authorization": f"Bearer {staff.token('staff-operator', mfa=True)}"}
    path = f"{STAGES}/{tenant}/{SCREENER}"

    async def live(**named: object) -> tuple[int, str]:
        answered = await net.http.put(
            path, json={"stage": "live", "note": "after shadow", **named}, headers=headers
        )
        return answered.status_code, answered.json().get("detail", "")

    assert await live() == (409, "shadow_report_required")
    assert await live(report_sha256="0" * 64, report_as_of=as_of.isoformat()) == (
        409,
        "shadow_report_changed",
    )
    old = (now - timedelta(days=8)).isoformat()
    assert await live(report_sha256=report.sha256, report_as_of=old) == (
        409,
        "shadow_report_stale",
    )
    ahead = (now + timedelta(days=1)).isoformat()
    assert await live(report_sha256=report.sha256, report_as_of=ahead) == (
        409,
        "shadow_report_stale",
    )
    assert await seed.value("SELECT count(*) FROM agent_stages WHERE tenant_id = $1", tenant) == 0
    status, _ = await live(report_sha256=report.sha256, report_as_of=as_of.isoformat())
    assert status == 200
    assert await _stages(seed, tenant) == ["live"]


async def test_failing_data_is_not_ready_with_or_without_a_report(
    net: Net, seed: Seeder, staff: FakeIdentityProvider
) -> None:
    tenant = await seed.firm()
    now = system_now().replace(microsecond=0)
    as_of = now - timedelta(hours=1)
    # 25 scored, 3 flagged-but-accepted: 12% disagreement, over QD-10's 8%.
    scored = [("ready_for_review", "accept")] * 22 + [("needs_revision", "accept")] * 3
    await _shadow(seed, tenant, now - timedelta(days=20), 60, scored)
    report = await _score(tenant, as_of)
    assert (report.spec036_q1, report.qd10, report.disagreement) == (True, False, "0.1200")
    headers = {"Authorization": f"Bearer {staff.token('staff-operator', mfa=True)}"}
    for named in ({}, {"report_sha256": report.sha256, "report_as_of": as_of.isoformat()}):
        answered = await net.http.put(
            f"{STAGES}/{tenant}/{SCREENER}",
            json={"stage": "live", "note": "too soon", **named},
            headers=headers,
        )
        assert answered.status_code == 409
        assert answered.json()["detail"] == "stage_not_ready"
    assert await _stages(seed, tenant) == []
