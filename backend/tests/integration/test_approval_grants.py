"""P-04-T10 against Postgres (migration 0102; ADR-126, ADR-161; DEC-24): an approval grant can't
be consumed before `not_before`, twice, after a void, for another payload, after it expires, or by
an approver who has lost the action. The relay delivers a grant-held event only through
`consume_grant`. An Undo is refused once its decision's grant has been consumed.

The service runs as the app role, so the grants and the settle-once trigger are exercised as
production uses them. Seed rows go through the superuser.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, ClassVar, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
    relay_engine,
)
from abacus.kernel.uow import DomainEvent, Target, event_sha256, uow
from abacus.kernel.uow.relay import InMemoryPublisher, relay_once
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    GrantNotYetDue,
    Resource,
    consume_grant,
    issue_grant,
    void_grant,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

DIGEST = "a" * 64
ACTION = "firm.read_settings"  # firm_admin may; a person with no firm role may not


class HeldProbe(DomainEvent):
    event_type: ClassVar[str] = "probe.grant_held"
    marker: Annotated[uuid.UUID, classified("internal")]


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _approver(seed: Seeder) -> AuthContext:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        person.user_id,
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            person.user_id,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(person.user_id)),
        user_id=person.user_id,
        membership_id=membership,
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _issue(
    ctx: AuthContext,
    *,
    starts_in: timedelta = timedelta(seconds=-1),
    lasts: timedelta = timedelta(minutes=10),
    digest: str = DIGEST,
) -> uuid.UUID:
    now = datetime.now(UTC)
    async with uow(ctx.tenant) as tx:
        grant = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=Resource.firm(ctx.tenant_id),
            subject=Target("proposal", uuid.uuid4()),
            payload_sha256=digest,
            not_before=now + starts_in,
            expires_at=now + starts_in + lasts,
        )
        tx.record("proposal.approved", target=Target("proposal", grant))
    return grant


async def _void(ctx: AuthContext, grant: uuid.UUID) -> bool:
    async with uow(ctx.tenant) as tx:
        voided = await void_grant(tx, grant)
        tx.record("proposal.undone", target=Target("proposal", grant))
    return voided


async def _audits(seed: Seeder, action: str, grant: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE action = $1 AND target_id = $2",
            action,
            str(grant),
        ),
    )


async def test_p04t10_a_grant_is_consumed_once_and_a_retry_of_the_same_effect_stays_consumed(
    seed: Seeder,
) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx)
    effect = uuid.uuid4()
    assert await consume_grant(ctx.tenant_id, grant, effect, DIGEST)
    assert await consume_grant(ctx.tenant_id, grant, effect, DIGEST)  # the relay retried
    assert not await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)  # a second effect
    assert await _audits(seed, "approval_grant.consumed", grant) == 1


async def test_p04t10_a_grant_is_not_consumed_before_not_before(seed: Seeder) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx, starts_in=timedelta(minutes=5))
    with pytest.raises(GrantNotYetDue):
        await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)
    assert await seed.value("SELECT used_at FROM approval_grants WHERE id = $1", grant) is None


async def test_p04t10_a_voided_grant_is_never_consumed(seed: Seeder) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx)
    assert await _void(ctx, grant)
    assert not await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)
    assert not await _void(ctx, grant)  # already void
    assert await _audits(seed, "approval_grant.voided", grant) == 1


async def test_p04t10_a_consumed_grant_cannot_be_voided(seed: Seeder) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx)
    assert await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)
    assert not await _void(ctx, grant)  # the effect started: the caller answers effect_started


async def test_p04t10_an_approver_who_lost_the_action_cannot_consume(seed: Seeder) -> None:
    demoted, revoked = await _approver(seed), await _approver(seed)
    first, second = await _issue(demoted), await _issue(revoked)
    await seed.run(
        "UPDATE memberships SET firm_role = NULL WHERE tenant_id = $1 AND user_id = $2",
        demoted.tenant_id,
        demoted.user_id,
    )
    await seed.run(
        "UPDATE memberships SET status = 'revoked', revoked_at = now() "
        "WHERE tenant_id = $1 AND user_id = $2",
        revoked.tenant_id,
        revoked.user_id,
    )
    assert not await consume_grant(demoted.tenant_id, first, uuid.uuid4(), DIGEST)
    assert not await consume_grant(revoked.tenant_id, second, uuid.uuid4(), DIGEST)


async def test_p04t10_a_grant_is_bound_to_its_payload_and_its_window(seed: Seeder) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx)
    assert not await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), "b" * 64)
    expired = await _issue(ctx, starts_in=timedelta(minutes=-10), lasts=timedelta(minutes=5))
    assert not await consume_grant(ctx.tenant_id, expired, uuid.uuid4(), DIGEST)
    assert await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)  # the right payload


async def test_p04t10_another_firm_cannot_consume_the_grant(seed: Seeder) -> None:
    ctx, other = await _approver(seed), await _approver(seed)
    grant = await _issue(ctx)
    assert not await consume_grant(other.tenant_id, grant, uuid.uuid4(), DIGEST)


async def test_p04t10_only_a_person_holding_the_action_is_issued_a_grant(seed: Seeder) -> None:
    ctx = await _approver(seed)
    await seed.run(
        "UPDATE memberships SET firm_role = NULL WHERE tenant_id = $1 AND user_id = $2",
        ctx.tenant_id,
        ctx.user_id,
    )
    nobody = AuthContext(
        tenant=ctx.tenant,
        user_id=ctx.user_id,
        membership_id=ctx.membership_id,
        firm_role=None,
        mfa_at=ctx.mfa_at,
    )
    with pytest.raises(Forbidden):
        await _issue(nobody)


async def _as_app(ctx: AuthContext, statement: str, grant: uuid.UUID) -> None:
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(text(statement), {"id": grant})
        tx.record("proposal.undone", target=Target("approval_grant", grant))


async def test_p04t10_the_app_role_settles_a_grant_once_and_changes_nothing_else(
    seed: Seeder,
) -> None:
    ctx = await _approver(seed)
    grant = await _issue(ctx)
    with pytest.raises(DBAPIError, match="permission denied"):
        await _as_app(ctx, "UPDATE approval_grants SET action = 'x.y' WHERE id = :id", grant)
    with pytest.raises(DBAPIError, match="permission denied"):
        await _as_app(ctx, "DELETE FROM approval_grants WHERE id = :id", grant)
    await _as_app(ctx, "UPDATE approval_grants SET voided_at = now() WHERE id = :id", grant)
    with pytest.raises(DBAPIError, match="already settled"):
        await _as_app(ctx, "UPDATE approval_grants SET voided_at = NULL WHERE id = :id", grant)


async def _drain() -> None:
    """Leftovers from other tests are marked published, so this pass sees only its own."""
    async with relay_engine().begin() as conn:
        await conn.execute(
            text("UPDATE outbox SET published_at = now() WHERE published_at IS NULL")
        )


async def _emit_held(ctx: AuthContext) -> tuple[uuid.UUID, uuid.UUID]:
    """A decision with a held effect, as a P-06 send or a P-04 return notice will write it."""
    event = HeldProbe(marker=uuid.uuid4())
    now = datetime.now(UTC)
    async with uow(ctx.tenant) as tx:
        grant = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=Resource.firm(ctx.tenant_id),
            subject=Target("proposal", uuid.uuid4()),
            payload_sha256=event_sha256(event),
            not_before=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=10),
        )
        tx.emit(event, grant_id=grant)
        tx.record("proposal.approved", target=Target("proposal", grant))
    return grant, event.event_id


async def test_p04t10_the_relay_delivers_a_held_event_only_through_consume_grant(
    seed: Seeder,
) -> None:
    await _drain()
    ctx = await _approver(seed)
    kept, kept_event = await _emit_held(ctx)
    undone, undone_event = await _emit_held(ctx)
    assert await _void(ctx, undone)
    publisher = InMemoryPublisher()
    for _ in range(5):
        await relay_once(publisher)
    delivered = [e.event_id for e in publisher.published]
    assert kept_event in delivered
    assert undone_event not in delivered
    assert (
        await seed.value("SELECT consumer_ref FROM approval_grants WHERE id = $1", kept)
        == kept_event
    )


# --- the Undo trigger's grant half (0095 + 0102) -------------------------------------------------

DECIDE = (
    "INSERT INTO proposal_decisions (id, tenant_id, proposal_id, decision, seen_version, "
    "decided_by, undoes_decision_id, approval_grant_id) VALUES ($1, $2, $3, $4, 1, $5, $6, $7)"
)


async def _proposal(seed: Seeder, tenant: uuid.UUID) -> uuid.UUID:
    proposal = uuid.uuid4()
    await seed.as_actor(
        tenant,
        ("agent", "agent:probe"),
        "INSERT INTO proposals (id, tenant_id, kind, title, agent_run_id) "
        "VALUES ($1, $2, 'field_change_set', 'Probe', $3)",
        proposal,
        tenant,
        uuid.uuid4(),
    )
    return proposal


async def test_p04t10_an_undo_is_refused_once_the_decisions_grant_is_consumed(
    seed: Seeder,
) -> None:
    ctx = await _approver(seed)
    who = ("human", str(ctx.user_id))
    for consumed in (False, True):
        proposal = await _proposal(seed, ctx.tenant_id)
        grant = await _issue(ctx)
        approved = uuid.uuid4()
        await seed.as_actor(
            ctx.tenant_id,
            who,
            DECIDE,
            approved,
            ctx.tenant_id,
            proposal,
            "approved",
            ctx.user_id,
            None,
            grant,
        )
        if consumed:
            assert await consume_grant(ctx.tenant_id, grant, uuid.uuid4(), DIGEST)
            with pytest.raises(asyncpg.CheckViolationError, match="undo_window_closed"):
                await seed.as_actor(
                    ctx.tenant_id,
                    who,
                    DECIDE,
                    uuid.uuid4(),
                    ctx.tenant_id,
                    proposal,
                    "undone",
                    ctx.user_id,
                    approved,
                    None,
                )
        else:
            await seed.as_actor(
                ctx.tenant_id,
                who,
                DECIDE,
                uuid.uuid4(),
                ctx.tenant_id,
                proposal,
                "undone",
                ctx.user_id,
                approved,
                None,
            )
