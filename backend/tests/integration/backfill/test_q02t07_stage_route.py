"""Q-02-T07 and T08 code gaps (TASK-1318; DEC-414; SPEC-036 Q1, Q3, Q5), against the app over HTTP
and the migrated Postgres:

- `PUT /v1/platform/agent-stages/{firm_id}/{agent_id}` answers only platform staff (the staff
  issuer with MFA): no token and a firm member's token are 401.
- Staff set `shadow` with a note: one `agent_stages` row naming the staff member, its
  `agent_stage.changed` audit event, and an `ai_boundary.facts_changed` outbox event for the firm.
- `live` before 50 shadow runs over 14 days is 409 `stage_not_ready`; an agent the registry
  does not declare is 422 `unknown_agent`; an unknown firm is 404. Nothing is written for any.
- The relay's handler for `ai_boundary.facts_changed` forgets the firm's cached boundary facts.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from abacus.ai_gateway import boundary
from abacus.ai_gateway.boundary import on_boundary_facts_changed
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import configure_staff_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Net, Seeder

STAGES = "/v1/platform/agent-stages"
CLEARED = "evidence.screener"


@pytest.fixture
def staff() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider(issuer="https://staff.example.test", kid="staff-1")
    configure_staff_verifier(provider.verifier())
    yield provider
    configure_staff_verifier(None)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _stages(seed: Seeder, tenant: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT stage FROM agent_stages WHERE tenant_id = $1 ORDER BY created_at", tenant
    )
    return [str(r["stage"]) for r in rows]


async def test_only_platform_staff_reach_the_stage_route(
    net: Net, seed: Seeder, staff: FakeIdentityProvider
) -> None:
    tenant = await seed.firm()
    body = {"stage": "shadow", "note": "first stage"}
    assert (await net.http.put(f"{STAGES}/{tenant}/{CLEARED}", json=body)).status_code == 401
    member = net.idp.token("someone-in-a-firm", mfa=True)
    answered = await net.http.put(
        f"{STAGES}/{tenant}/{CLEARED}", json=body, headers=_bearer(member)
    )
    assert answered.status_code == 401
    no_mfa = staff.token("staff-without-mfa")
    answered = await net.http.put(
        f"{STAGES}/{tenant}/{CLEARED}", json=body, headers=_bearer(no_mfa)
    )
    assert answered.status_code == 401
    assert await _stages(seed, tenant) == []


async def test_staff_set_shadow_with_its_audit_and_boundary_events(
    net: Net, seed: Seeder, staff: FakeIdentityProvider
) -> None:
    tenant = await seed.firm()
    token = staff.token("staff-operator", mfa=True)
    answered = await net.http.put(
        f"{STAGES}/{tenant}/{CLEARED}",
        json={"stage": "shadow", "note": "first stage"},
        headers=_bearer(token),
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert (body["firm_id"], body["agent_id"], body["stage"]) == (str(tenant), CLEARED, "shadow")
    rows = await seed.rows(
        "SELECT id, changed_by, note FROM agent_stages WHERE tenant_id = $1", tenant
    )
    assert len(rows) == 1
    assert str(rows[0]["id"]) == body["id"]
    assert str(rows[0]["changed_by"]).startswith("staff:")
    assert rows[0]["note"] == "first stage"
    audit = await seed.rows(
        "SELECT actor_kind, actor_id, target_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'agent_stage.changed'",
        tenant,
    )
    assert [(r["actor_kind"], r["actor_id"], r["target_id"]) for r in audit] == [
        ("system", rows[0]["changed_by"], body["id"])
    ]
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'ai_boundary.facts_changed'",
        tenant,
    )
    assert outbox == 1


async def test_live_too_early_unknown_agent_and_unknown_firm_write_nothing(
    net: Net, seed: Seeder, staff: FakeIdentityProvider
) -> None:
    tenant = await seed.firm()
    headers = _bearer(staff.token("staff-operator", mfa=True))
    live = await net.http.put(
        f"{STAGES}/{tenant}/{CLEARED}",
        json={"stage": "live", "note": "too early"},
        headers=headers,
    )
    assert live.status_code == 409
    assert live.json()["detail"] == "stage_not_ready"
    uncleared = await net.http.put(
        f"{STAGES}/{tenant}/agents.not_declared",
        json={"stage": "shadow", "note": "not a declared agent"},
        headers=headers,
    )
    assert uncleared.status_code == 422
    assert uncleared.json()["detail"] == "unknown_agent"
    unknown = await net.http.put(
        f"{STAGES}/{uuid.uuid4()}/{CLEARED}",
        json={"stage": "shadow", "note": "no such firm"},
        headers=headers,
    )
    assert unknown.status_code == 404
    assert await _stages(seed, tenant) == []


async def test_the_relay_handler_forgets_the_firms_boundary_facts() -> None:
    tenant, other = uuid.uuid4(), uuid.uuid4()
    boundary._cache[tenant] = (True, float("inf"))  # pyright: ignore[reportPrivateUsage] -- the cache under test
    boundary._cache[other] = (True, float("inf"))  # pyright: ignore[reportPrivateUsage] -- the cache under test
    event = OutboxEvent(uuid.uuid4(), tenant, "ai_boundary.facts_changed", {})
    await on_boundary_facts_changed(event)
    await on_boundary_facts_changed(event)  # at least once: a redelivery changes nothing
    assert tenant not in boundary._cache  # pyright: ignore[reportPrivateUsage] -- the cache under test
    assert other in boundary._cache  # pyright: ignore[reportPrivateUsage] -- the cache under test
    boundary.clear_cache(other)
