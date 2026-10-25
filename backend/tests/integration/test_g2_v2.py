"""G2 v2 against Postgres (P-07-T24; SPEC-332 AC-13 to AC-16; ADR-164 items 2 to 4): "Ana Cruz can
open the Northwind engagement but cannot be assigned or sign off until Ana confirms, and a
non-attest close is not gated." The attest flag is the database's derived one (an active EBP
audit makes its client an attest client, DEC-128); the confirmations and the firm setting are real
rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from abacus.kernel.db import TenantContext, configure_engine, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import (
    assign_work_item,
    create_work_item,
    g2_blocks,
    independence_cleared,
)
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, visible
from abacus.modules.identity.authz import recording_checks

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
_ACTIVATE = text("UPDATE engagements SET status = 'active' WHERE id = :id")


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()

    async def user(self) -> uuid.UUID:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
            self.tenant,
            user,
        )
        return user

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", self.tenant
        )
        self.partner = await self.user()
        self.ana = await self.user()
        return self

    async def engagement(self, type_: str) -> tuple[uuid.UUID, uuid.UUID]:
        """An active engagement of `type_` on a new client with the partner and Ana (staff,
        asked to confirm), and a work item (the assurance one from the defaults trigger, or an
        advisory project)."""
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            self.tenant,
            f"Probe client {uuid.uuid4().hex[:6]}",
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Probe entity') RETURNING id",
            self.tenant,
            client,
        )
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, 'Probe engagement', '2025-01-01', '2025-12-31', $4, "
                    "$5, 'prospect') RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    self.partner,
                    type_,
                )
            )
        )
        # As the app does: the attest trigger reads under the request's tenant (DEC-128).
        async with uow(self.ctx(self.partner).tenant) as tx:
            await tx.session.execute(_ACTIVATE, {"id": engagement})
            tx.record("engagement.probed", target=Target("engagement", engagement))
        for user, role in ((self.partner, "engagement_partner"), (self.ana, "staff")):
            await self.seed.run(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4)",
                self.tenant,
                engagement,
                user,
                role,
            )
        await self.seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status) "
            "VALUES ($1, $2, $3, 'requested') ON CONFLICT DO NOTHING",
            self.tenant,
            engagement,
            self.ana,
        )
        found = await self.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1", engagement
        )
        if found is None:  # only the assurance kind gets one from the trigger
            return engagement, await create_work_item(
                self.ctx(self.partner), engagement, "advisory_project", name="Probe project"
            )
        return engagement, uuid.UUID(str(found))

    async def confirm(self, engagement: uuid.UUID) -> None:
        await self.seed.run(
            "UPDATE independence_confirmations SET status = 'confirmed', answered_at = now() "
            "WHERE engagement_id = $1 AND user_id = $2",
            engagement,
            self.ana,
        )

    async def blocks_view(self) -> None:
        await self.seed.run(
            "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
            "VALUES ($1, 'g2_blocks_view', true, $2)",
            self.tenant,
            self.partner,
        )

    def ctx(self, user: uuid.UUID) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(user))
        return AuthContext(tenant, user, uuid.uuid4(), None, datetime.now(UTC))

    def on(self, engagement: uuid.UUID) -> Resource:
        return Resource.engagement(self.tenant, engagement, archived=False)

    async def assignments(self, work_item: uuid.UUID) -> int:
        return int(
            str(
                await self.seed.value(
                    "SELECT count(*) FROM work_item_assignments WHERE work_item_id = $1 "
                    "AND user_id = $2",
                    work_item,
                    self.ana,
                )
            )
        )

    async def listed(self, user: uuid.UUID, action: str) -> set[uuid.UUID]:
        ctx = self.ctx(user)
        async with tenant_session(ctx.tenant) as session:
            rows = await session.scalars(
                select(Engagement.id).where(visible(ctx, action, Engagement.id))
            )
            return set(rows)


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


async def _refused(ctx: AuthContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource)
    return raised.value.layer


async def test_ac13_ana_opens_the_attest_engagement_but_cannot_be_assigned_or_sign_off(
    firm: _Firm,
) -> None:
    northwind, work_item = await firm.engagement("ebp_audit")
    ana = firm.ctx(firm.ana)
    assert not await independence_cleared(ana.tenant, northwind, firm.ana)
    assert await g2_blocks(ana.tenant, northwind, firm.ana)
    with recording_checks():
        await authorise(ana, "evidence.read", firm.on(northwind))  # she can view it
        assert await _refused(ana, "sign_off.prepare", firm.on(northwind)) == "independence"
    assert northwind in await firm.listed(firm.ana, "evidence.read")
    with pytest.raises(GateUnmet) as refused:
        await assign_work_item(firm.ctx(firm.partner), work_item, firm.ana, "preparer")
    assert refused.value.facts == {"gate": "G2", "user_id": str(firm.ana)}
    assert await firm.assignments(work_item) == 0


async def test_ac16_once_ana_confirms_she_is_cleared_assigned_and_signs(firm: _Firm) -> None:
    northwind, work_item = await firm.engagement("ebp_audit")
    await firm.confirm(northwind)
    ana = firm.ctx(firm.ana)
    assert await independence_cleared(ana.tenant, northwind, firm.ana)
    assert not await g2_blocks(ana.tenant, northwind, firm.ana)
    await assign_work_item(firm.ctx(firm.partner), work_item, firm.ana, "preparer")
    assert await firm.assignments(work_item) == 1
    with recording_checks():
        await authorise(ana, "sign_off.prepare", firm.on(northwind))
    audited = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'work_item.assigned'",
        firm.tenant,
    )
    assert int(str(audited)) == 1


async def test_ac14_a_non_attest_close_is_not_gated(firm: _Firm) -> None:
    close, work_item = await firm.engagement("cas_monthly_close")
    ana = firm.ctx(firm.ana)
    assert not await g2_blocks(ana.tenant, close, firm.ana)
    await firm.blocks_view()  # even with the stricter setting on
    with recording_checks():
        await authorise(ana, "evidence.read", firm.on(close))
        await authorise(ana, "sign_off.prepare", firm.on(close))
    await assign_work_item(firm.ctx(firm.partner), work_item, firm.ana, "preparer")
    assert await firm.assignments(work_item) == 1


async def test_ac15_g2_blocks_view_restores_the_read_gate_on_attest_engagements(
    firm: _Firm,
) -> None:
    northwind, _ = await firm.engagement("ebp_audit")
    close, _ = await firm.engagement("cas_monthly_close")
    await firm.blocks_view()
    ana = firm.ctx(firm.ana)
    with recording_checks():
        assert await _refused(ana, "evidence.read", firm.on(northwind)) == "independence"
        await authorise(ana, "evidence.read", firm.on(close))
    listed = await firm.listed(firm.ana, "evidence.read")
    assert northwind not in listed and close in listed  # visible() agrees with authorise


async def test_ac13_assignment_is_the_partners_or_managers_never_the_staff_members(
    firm: _Firm,
) -> None:
    _, work_item = await firm.engagement("cas_monthly_close")
    with pytest.raises(Forbidden):
        await assign_work_item(firm.ctx(firm.ana), work_item, firm.ana, "preparer")
    assert await firm.assignments(work_item) == 0


# --- P-07-T30 (ED-042): the assignee is on the team and not walled --------------------------


async def test_p07t30_an_assignee_off_the_team_is_404_and_nothing_is_written(
    firm: _Firm,
) -> None:
    close, work_item = await firm.engagement("cas_monthly_close")  # never gated by G2
    stranger = await firm.user()
    with pytest.raises(NotFound):
        await assign_work_item(firm.ctx(firm.partner), work_item, stranger, "preparer")
    written = await firm.seed.value(
        "SELECT count(*) FROM work_item_assignments WHERE work_item_id = $1", work_item
    )
    assert int(str(written)) == 0
    assert close


async def test_p07t30_a_walled_team_member_is_404_like_a_stranger(firm: _Firm) -> None:
    close, work_item = await firm.engagement("cas_monthly_close")
    client = await firm.seed.value("SELECT client_id FROM engagements WHERE id = $1", close)
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        firm.ana,
        client,
        firm.partner,
    )
    with pytest.raises(NotFound):
        await assign_work_item(firm.ctx(firm.partner), work_item, firm.ana, "preparer")
    assert await firm.assignments(work_item) == 0


async def test_p07t30_review_the_eqr_function_is_the_eqrs_alone(firm: _Firm) -> None:
    close, work_item = await firm.engagement("cas_monthly_close")  # never gated by G2
    eqr = await firm.user()
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'eqr_reviewer')",
        firm.tenant,
        close,
        eqr,
    )
    with pytest.raises(DomainInvalid):  # the EQR takes no other function
        await assign_work_item(firm.ctx(firm.partner), work_item, eqr, "preparer")
    with pytest.raises(DomainInvalid):  # and no one else takes `eqr`
        await assign_work_item(firm.ctx(firm.partner), work_item, firm.ana, "eqr")
    await assign_work_item(firm.ctx(firm.partner), work_item, eqr, "eqr")
    written = await firm.seed.value(
        "SELECT count(*) FROM work_item_assignments WHERE work_item_id = $1", work_item
    )
    assert int(str(written)) == 1
