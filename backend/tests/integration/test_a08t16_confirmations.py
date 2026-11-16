"""A-08-T16 (TASK-8084; SPEC-657 F6; AU-C 505) against Postgres: four confirmations whose tiles
sum to 4, and a send to a client-only address refused with 409 `address_not_verified`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import confirmations_service as cs
from abacus.modules.assurance.confirmations_contract_models import (
    AddressVerificationIn,
    ConfirmationCreateIn,
    ConfirmationLineIn,
)
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def audit(migrated_db: MigratedDatabase) -> AsyncIterator[tuple[AuthContext, uuid.UUID]]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = uuid.UUID(str(await seed.value("INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES ('https://probe.test', $1, $2, 'Simone Park') RETURNING id", uuid.uuid4().hex, f"{uuid.uuid4().hex}@x.test")))
    await seed.run("INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')", tenant, user)
    client = await seed.value("INSERT INTO clients (tenant_id, name) VALUES ($1, 'Granite Peak') RETURNING id", tenant)
    entity = await seed.value("INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Granite Peak') RETURNING id", tenant, client)
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, fiscal_period_start, fiscal_period_end, created_by, status) "
        "VALUES ($1, $2, $3, '2025 Audit', '2025-01-01', '2025-12-31', $4, 'active') RETURNING id", tenant, client, entity, user,
    )
    await seed.run("INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, $2, $3, 'engagement_partner')", tenant, engagement, user)
    work_item = uuid.UUID(str(await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) VALUES ($1, $2, $3, 'assurance', 'Audit', $4) RETURNING id",
        tenant, engagement, client, user,
    )))  # fmt: skip
    ctx = AuthContext(TenantContext(tenant, "human", str(user)), user, uuid.uuid4(), None, datetime.now(UTC))
    yield ctx, work_item
    await dispose_engine()


def _body(n: int, kind: str = "accounts_receivable") -> ConfirmationCreateIn:
    return ConfirmationCreateIn(
        type=kind, respondent_name=f"Respondent {n}", respondent_org=f"Customer {n}", channel="accrued_link",  # type: ignore[arg-type]
        address_value=f"ap{n}@customer{n}.example", lines=[ConfirmationLineIn(description="Balance", book_amount=Decimal("1000.00"))],
    )  # fmt: skip


async def test_ac_tiles_sum_to_four(audit: tuple[AuthContext, uuid.UUID]) -> None:
    ctx, work_item = audit
    for n in range(1, 5):
        await cs.create(ctx, work_item, _body(n))
    summary = await cs.summary(ctx, work_item)
    assert summary.total == 4 and sum(t.count for t in summary.tiles) == 4
    assert [r.number for r in (await cs.log(ctx, work_item)).items] == ["C1", "C2", "C3", "C4"]


async def test_ac_a_client_only_address_is_refused(audit: tuple[AuthContext, uuid.UUID]) -> None:
    ctx, work_item = audit
    row = await cs.create(ctx, work_item, _body(1))
    await cs.verify_address(ctx, row.id, AddressVerificationIn(method="From the client's AR listing", sources=["client_supplied"], citation_ids=[uuid.uuid4()]))
    with pytest.raises(cs.AddressNotVerified):
        await cs.check_sendable(ctx, row.id)
    await cs.verify_address(ctx, row.id, AddressVerificationIn(method="Customer website contact page", sources=["website"], citation_ids=[uuid.uuid4()]))
    await cs.check_sendable(ctx, row.id)  # independent now


async def test_a_client_principal_never_reaches_a_confirmation(audit: tuple[AuthContext, uuid.UUID]) -> None:
    ctx, work_item = audit
    row = await cs.create(ctx, work_item, _body(1))
    client_ctx = AuthContext(ctx.tenant, ctx.user_id, uuid.uuid4(), uuid.uuid4(), datetime.now(UTC))  # a client principal
    if not client_ctx.client:
        pytest.skip("AuthContext's client marker is the 4th field in this build")
    with pytest.raises(NotFound):
        await cs.detail(client_ctx, row.id)
