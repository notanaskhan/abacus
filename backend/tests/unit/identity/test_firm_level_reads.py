"""SPEC-014 AC-6 and the fail-closed rules (TASK-029 D1, D2): on firm-level reads a person's
engagement roles count; agents and the platform never get them, nothing is guessed when the
lookup is missing or fails, and the lookup is only made when it can matter, once per request.

The lookup of the roles themselves is faked here (`engagement_roles_in_firm`); the integration
suite runs the real query. Expectations come from the spec, not the implementation.
"""

from __future__ import annotations

import uuid
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Select

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
)
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.repository import FirmRole

READ_VERBS = {"read", "read_metadata", "read_log"}
# Firm-level reads an engagement role alone is enough for: allowed to a senior, no MFA, no reason.
FIRM_READS = sorted(
    action
    for action, rule in RULES.items()
    if action.split(".", 1)[1] in READ_VERBS
    and rule.decisions.get("senior") == "allow"
    and not (rule.mfa_recent or rule.requires_reason or rule.notify or rule.independence)
)
ACTION = "knowledge.read"  # senior, staff and the rest of the team allowed; quality_partner too


class Lookup:
    """Stands in for the database read of the user's roles on the firm's active engagements."""

    def __init__(self) -> None:
        self.roles: frozenset[str] = frozenset({"senior"})
        self.fails = False
        self.calls = 0

    async def __call__(self, tenant: object, user_id: uuid.UUID, active: object) -> frozenset[str]:
        self.calls += 1
        if self.fails:
            raise ConnectionError("database unavailable")
        return self.roles


@pytest.fixture
def lookup(monkeypatch: pytest.MonkeyPatch) -> Lookup:
    found = Lookup()

    async def no_walls(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    monkeypatch.setattr(authz, "engagement_roles_in_firm", found)
    monkeypatch.setattr(authz, "_active_engagements", lambda: None)
    monkeypatch.setattr(authz, "walled_clients", no_walls)
    return found


def _person(firm_role: str | None = None) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(FirmRole | None, firm_role),
        None,
    )


async def _denied_layer(ctx: AuthContext | AgentContext, action: str) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    return raised.value.layer


# --- AC-6: agents and the platform never get a person's engagement roles


def test_ac6_the_probe_set_is_not_empty() -> None:
    assert ACTION in FIRM_READS
    assert len(FIRM_READS) >= 3


@pytest.mark.parametrize("action", FIRM_READS)
async def test_ac6_an_agent_run_on_an_engagement_has_no_firm_level_read(
    lookup: Lookup, action: str
) -> None:
    initiator = _person()  # whose engagement role would grant the read if it were counted
    run_id = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(initiator.tenant_id, "agent", f"agent:evidence.screener:{run_id}"),
        agent_id="evidence.screener",
        agent_run_id=run_id,
        engagement_id=uuid.uuid4(),
        task_scope=frozenset(FIRM_READS),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )
    assert await _denied_layer(agent, action) == "relationship"
    assert lookup.calls == 0


@pytest.mark.parametrize("action", FIRM_READS)
async def test_ac6_a_system_run_has_no_firm_level_read(lookup: Lookup, action: str) -> None:
    system = system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        on_behalf_of=uuid.uuid4(),
    )
    with pytest.raises(Forbidden) as raised:
        await authorise(system, action, Resource.firm(system.tenant_id))
    assert raised.value.layer == "relationship"
    assert lookup.calls == 0


# --- fail closed


async def test_d1_without_the_engagements_registration_engagement_roles_never_count(
    lookup: Lookup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_active_engagements", None)
    assert await _denied_layer(_person(), ACTION) == "relationship"
    assert lookup.calls == 0


async def test_a_lookup_that_fails_grants_nothing(lookup: Lookup) -> None:
    lookup.fails = True
    assert await _denied_layer(_person(), ACTION) == "relationship"
    assert lookup.calls == 1


async def test_the_registration_is_made_once_and_only_once(lookup: Lookup) -> None:
    def other() -> Select[UUID]:
        raise AssertionError("never called")

    registered = authz._active_engagements  # pyright: ignore[reportPrivateUsage]
    assert registered is not None
    authz.register_active_engagements(registered)  # the same one again is fine
    with pytest.raises(RuntimeError, match="already registered"):
        authz.register_active_engagements(other)


# --- D2: the lookup is made only when it can matter, once per request


async def test_d2_a_firm_role_that_already_allows_the_read_skips_the_lookup(
    lookup: Lookup,
) -> None:
    ctx = _person("firm_admin")
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))
    assert lookup.calls == 0


async def test_d2_a_firm_role_that_does_not_allow_it_still_counts_engagement_roles(
    lookup: Lookup,
) -> None:
    ctx = _person("quality_partner")
    action = next(
        a
        for a in FIRM_READS
        if RULES[a].decisions.get("quality_partner") != "allow"
        and RULES[a].decisions.get("senior") == "allow"
    )
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    assert lookup.calls == 1


async def test_a_write_never_asks_for_engagement_roles(lookup: Lookup) -> None:
    ctx = _person()
    write = next(
        a for a, r in RULES.items() if not r.reads and r.decisions.get("senior") == "allow"
    )
    assert await _denied_layer(ctx, write) == "relationship"
    assert lookup.calls == 0


async def test_the_roles_are_read_once_per_request(lookup: Lookup) -> None:
    ctx = _person()
    with authz.recording_checks():
        for action in FIRM_READS[:3]:
            await authorise(ctx, action, Resource.firm(ctx.tenant_id))
        assert lookup.calls == 1
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))  # outside a request: asked again
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))
    assert lookup.calls == 3


async def test_the_cache_is_per_person(lookup: Lookup) -> None:
    first, second = _person(), _person()
    with authz.recording_checks():
        await authorise(first, ACTION, Resource.firm(first.tenant_id))
        await authorise(second, ACTION, Resource.firm(second.tenant_id))
        await authorise(first, ACTION, Resource.firm(first.tenant_id))
    assert lookup.calls == 2
