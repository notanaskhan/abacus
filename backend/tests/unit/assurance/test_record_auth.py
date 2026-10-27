"""A-01-T23 (DEC-598): a record-mode write answers `mfa_required` only when the stale second factor
is the sole blocker; any other attribute refusal (independence, for one) reads as itself."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import record_auth
from abacus.modules.assurance.record_auth import RecordNeedsMfa, authorise_record
from abacus.modules.identity.api import AuthContext, Forbidden, Resource

ACTION = "assurance.record_release"


def _ctx(mfa_minutes_ago: int) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), "human", str(uuid.uuid4())),
        user_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago),
    )


def _resource(ctx: AuthContext) -> Resource:
    return Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False, client_id=uuid.uuid4())


async def test_a_stale_factor_alone_asks_for_a_step_up(monkeypatch: pytest.MonkeyPatch) -> None:
    async def only_mfa(ctx: AuthContext, action: str, resource: Resource) -> None:
        if ctx.mfa_at is None or datetime.now(UTC) - ctx.mfa_at > timedelta(minutes=15):
            raise Forbidden(action, "attribute")

    async def every_other_layer_allows(
        ctx: AuthContext, resource: Resource, candidates: list[str]
    ) -> frozenset[str]:
        return frozenset(candidates)

    monkeypatch.setattr(record_auth, "authorise", only_mfa)
    monkeypatch.setattr(record_auth, "allowed_actions", every_other_layer_allows)
    ctx = _ctx(30)
    with pytest.raises(RecordNeedsMfa) as refused:
        await authorise_record(ctx, ACTION, _resource(ctx))
    assert refused.value.facts == {"reason": "mfa_required"}


async def test_another_attribute_refusal_is_not_hidden_behind_a_step_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def not_independent(ctx: AuthContext, action: str, resource: Resource) -> None:
        raise Forbidden(action, "attribute")  # fails whatever the factor's age

    async def independence_also_refuses(
        ctx: AuthContext, resource: Resource, candidates: list[str]
    ) -> frozenset[str]:
        return frozenset()

    monkeypatch.setattr(record_auth, "authorise", not_independent)
    monkeypatch.setattr(record_auth, "allowed_actions", independence_also_refuses)
    ctx = _ctx(30)
    with pytest.raises(Forbidden) as refused:
        await authorise_record(ctx, ACTION, _resource(ctx))
    assert not isinstance(refused.value, RecordNeedsMfa)


async def test_a_fresh_factor_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[AuthContext] = []

    async def allow(ctx: AuthContext, action: str, resource: Resource) -> None:
        seen.append(ctx)

    monkeypatch.setattr(record_auth, "authorise", allow)
    ctx = _ctx(1)
    await authorise_record(ctx, ACTION, _resource(ctx))
    assert seen == [ctx]  # checked once, with the caller's own context


async def test_an_agent_is_refused_before_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    async def never(*_: object) -> None:
        raise AssertionError("authorise must not run for an agent")

    monkeypatch.setattr(record_auth, "authorise", never)
    ctx = _ctx(1)
    agent = replace(ctx, tenant=TenantContext(ctx.tenant_id, "agent", "agent:x:1"))
    with pytest.raises(Forbidden):
        await authorise_record(agent, ACTION, _resource(ctx))
