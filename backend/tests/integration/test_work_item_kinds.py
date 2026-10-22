"""F-03-T22 against Postgres (chapter 03 story 1.1): "Copperleaf '2026 Close' holds 12 close work
items and Thornbury's tax engagement holds four returns across two entities, all created through
engagements.api." A 13th close for an existing period answers 409."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

import abacus.modules.closes.api
import abacus.modules.notices.api
import abacus.modules.tax.api  # each registers its work-item kind
from abacus.kernel.db import TenantContext, configure_engine
from abacus.modules.engagements.api import WorkItemExists, create_work_item
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api and abacus.modules.notices.api and abacus.modules.tax.api


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", self.tenant
        )
        self.partner = uuid.UUID(
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
            self.partner,
        )
        return self

    async def engagement(
        self, client_name: str, entities: list[str], type_: str
    ) -> tuple[uuid.UUID, list[uuid.UUID]]:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            self.tenant,
            client_name,
        )
        entity_ids = [
            uuid.UUID(
                str(
                    await self.seed.value(
                        "INSERT INTO client_entities (tenant_id, client_id, name) "
                        "VALUES ($1, $2, $3) RETURNING id",
                        self.tenant,
                        client,
                        name,
                    )
                )
            )
            for name in entities
        ]
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, $4, '2026-01-01', '2026-12-31', $5, $6, 'active') "
                    "RETURNING id",
                    self.tenant,
                    client,
                    entity_ids[0],
                    f"{client_name} engagement",
                    self.partner,
                    type_,
                )
            )
        )
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'engagement_partner')",
            self.tenant,
            engagement,
            self.partner,
        )
        return engagement, entity_ids

    @property
    def person(self) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(self.partner))
        return AuthContext(tenant, self.partner, uuid.uuid4(), None, datetime.now(UTC))

    async def count(self, sql: str, *args: object) -> int:
        return int(str(await self.seed.value(sql, *args)))


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


async def test_copperleafs_2026_close_holds_12_closes(firm: _Firm) -> None:
    engagement, _ = await firm.engagement(
        "Copperleaf Coffee Roasters, Inc.",
        ["Copperleaf Coffee Roasters, Inc."],
        "cas_monthly_close",
    )
    for month in range(1, 13):
        await create_work_item(
            firm.person,
            engagement,
            "close",
            name=f"2026-{month:02d} close",
            details={"period": f"2026-{month:02d}"},
        )
    assert (
        await firm.count(
            "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'close'",
            engagement,
        )
        == 12
    )
    assert (
        await firm.count("SELECT count(*) FROM closes WHERE engagement_id = $1", engagement) == 12
    )
    with pytest.raises(WorkItemExists):
        await create_work_item(
            firm.person, engagement, "close", name="Again", details={"period": "2026-08"}
        )
    assert (
        await firm.count(
            "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'close'",
            engagement,
        )
        == 12  # the refused one left nothing behind
    )


async def test_thornbury_holds_four_returns_across_two_entities(firm: _Firm) -> None:
    engagement, (walter, estate) = await firm.engagement(
        "Estate of Walter Thornbury",
        ["Walter Thornbury", "Estate of Walter Thornbury"],
        "tax_compliance",
    )
    for entity, form in ((walter, "1040"), (estate, "1041"), (estate, "706"), (walter, "709")):
        await create_work_item(
            firm.person,
            engagement,
            "tax_return",
            name=f"2025 Form {form}",
            client_entity_id=entity,
            details={"form": form, "tax_year": 2025},
        )
    rows = await firm.seed.rows(
        "SELECT client_entity_id, form FROM tax_returns WHERE engagement_id = $1", engagement
    )
    assert len(rows) == 4
    assert {r["client_entity_id"] for r in rows} == {walter, estate}


async def test_a_second_assurance_item_is_refused(firm: _Firm) -> None:
    engagement, _ = await firm.engagement("Probe Audit", ["Probe Audit"], "fs_audit")
    with pytest.raises(WorkItemExists):  # the engagement's trigger made the first
        await create_work_item(
            firm.person,
            engagement,
            "assurance",
            name="Another",
            details={"assurance_type": "fs_audit"},
        )


async def test_notices_and_projects_are_kinds_too(firm: _Firm) -> None:
    engagement, _ = await firm.engagement("Probe Notices", ["Probe Notices"], "notice_response")
    await create_work_item(
        firm.person,
        engagement,
        "notice",
        name="CP2000",
        details={"notice_code": "CP2000", "received_on": datetime(2026, 9, 1).date()},
    )
    await create_work_item(
        firm.person,
        engagement,
        "advisory_project",
        name="Entity review",
        details={"name": "Entity review"},
    )
    assert (
        await firm.count("SELECT count(*) FROM notices WHERE engagement_id = $1", engagement) == 1
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM advisory_projects WHERE engagement_id = $1", engagement
        )
        == 1
    )
