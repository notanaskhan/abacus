"""P-07-T47 the day-12 invitation notice against Postgres (P-07 §4.8; DEC-540, DEC-1000).

A client invitation lives 14 days. On day 12 (two days or fewer left) the firm's admins are told
once (`invitation.expiring`, C16 `invitation_expiring`) with an audit row; a second pass does
nothing; an invitation with more than two days left, accepted, revoked or already expired is never
noticed; a resent invitation's new expiry is noticed again; another firm is untouched. The hourly
identity activity runs the pass after access ends.

Expectations come from P-07 §4.8 and DEC-540, not from the implementation."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity import invitation_expiry
from abacus.modules.notifications.api import CATALOGUE
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


class Firm:
    def __init__(
        self, seed: Seeder, tenant: uuid.UUID, inviter: Person, engagement: uuid.UUID
    ) -> None:
        self.seed = seed
        self.tenant = tenant
        self.inviter = inviter
        self.engagement = engagement

    async def invite(self, expires_in: timedelta, *, status: str = "pending") -> uuid.UUID:
        address = f"c-{uuid.uuid4().hex[:8]}@example.com"
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO client_invitations (tenant_id, engagement_id, email, role, "
                "invited_by, expires_at, status) VALUES ($1, $2, $3, 'client_contributor', $4, "
                "now() + $5::interval, $6) RETURNING id",
                self.tenant,
                self.engagement,
                address,
                self.inviter.user_id,
                expires_in,
                status,
            ),
        )

    async def outbox(self) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = "
            "'invitation.expiring' ORDER BY occurred_at, id",
            self.tenant,
        )
        return [
            json.loads(r["payload"]) if isinstance(r["payload"], str) else dict(r["payload"])
            for r in rows
        ]

    async def audit(self) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, target_id::text AS target_id, after_ref::text AS a "
            "FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'client_invitation.expiry_notified' ORDER BY seq",
            self.tenant,
        )
        return [dict(r) for r in rows]


async def _firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    grace = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, grace.user_id)
    return Firm(seed, tenant, grace, engagement)


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return await _firm(seed)


async def test_day_12_firm_admins_are_told_once(firm: Firm) -> None:
    due = await firm.invite(timedelta(hours=47))
    await firm.invite(timedelta(days=3))  # day 11: not yet
    assert await invitation_expiry.sweep_firm(firm.tenant) == 1
    assert await invitation_expiry.sweep_firm(firm.tenant) == 0  # once per invitation and expiry
    [event] = await firm.outbox()
    assert event["invitation_id"] == str(due)
    assert event["engagement_id"] == str(firm.engagement)
    assert "email" not in event  # identifiers only
    [row] = await firm.audit()
    assert (row["actor_kind"], row["target_id"]) == ("system", str(due))
    assert "invitation.expiring" in NOTIFY
    entry = CATALOGUE["invitation.expiring"]
    assert (entry.kind, entry.subject_type, entry.engagement_key) == (
        "invitation_expiring",
        "client_invitation",
        "engagement_id",
    )


@pytest.mark.parametrize("status", ["accepted", "revoked", "expired"])
async def test_a_settled_invitation_is_never_noticed(firm: Firm, status: str) -> None:
    await firm.invite(timedelta(days=1), status=status)
    assert await invitation_expiry.sweep_firm(firm.tenant) == 0
    assert await firm.outbox() == []


async def test_a_lapsed_invitation_is_never_noticed(firm: Firm) -> None:
    await firm.invite(timedelta(hours=-1))
    assert await invitation_expiry.sweep_firm(firm.tenant) == 0


async def test_a_resent_invitation_is_noticed_again_before_its_new_end(firm: Firm) -> None:
    due = await firm.invite(timedelta(days=1))
    assert await invitation_expiry.sweep_firm(firm.tenant) == 1
    # A resend moves the expiry (P-07 §4.4): the new end is a new day 12.
    await firm.seed.run(
        "UPDATE client_invitations SET expires_at = now() + interval '40 hours' WHERE id = $1",
        due,
    )
    assert await invitation_expiry.sweep_firm(firm.tenant) == 1
    assert len(await firm.outbox()) == 2


async def test_another_firm_is_untouched(firm: Firm, seed: Seeder) -> None:
    other = await _firm(seed)
    await other.invite(timedelta(days=1))
    assert await invitation_expiry.sweep_firm(firm.tenant) == 0
    assert await firm.outbox() == []
    swept = await invitation_expiry.sweep_invitation_expiry()
    assert swept.notices >= 1 and swept.failed_firms == 0
    assert len(await other.outbox()) == 1


async def test_notices_are_insert_only(firm: Firm) -> None:
    await firm.invite(timedelta(days=1))
    await invitation_expiry.sweep_firm(firm.tenant)
    with pytest.raises(Exception, match="insert-only"):
        await firm.seed.run(
            "DELETE FROM invitation_expiry_notices WHERE tenant_id = $1", firm.tenant
        )
