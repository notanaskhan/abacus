"""F-03-T25 against Postgres (chapter 03 §3.5 story 5.1; CLI-04g): "Copperleaf reads non-attest
with Tess Moreno (owner) and Ben Ashby (approver of record) as contacts, and no plaintext TIN
column exists." Also: `is_attest_client` follows the engagements (DEC-128), contacts are unique
by email per client, and a designation names only the engagement's client's contacts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

import abacus.modules.engagements.api  # registers the lookups `authorise` reads
from abacus.kernel.db import TenantContext, configure_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import designate_contact, engagement_contacts
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.api import (
    ClientRecordChange,
    ContactExists,
    NewContact,
    add_contact,
    client_record,
    set_client_record,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
_MOVE = text("UPDATE engagements SET status = :status WHERE id = :id")
assert abacus.modules.engagements.api


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale')", self.tenant
        )
        self.partner = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Probe Partner') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status, level) "
            "VALUES ($1, $2, 'active', 'partner')",
            self.tenant,
            self.partner,
        )
        return self

    async def client(self, name: str) -> tuple[uuid.UUID, uuid.UUID]:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", self.tenant, name
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant,
            client,
            name,
        )
        return uuid.UUID(str(client)), uuid.UUID(str(entity))

    async def engagement(
        self, client: uuid.UUID, entity: uuid.UUID, type_: str, status: str
    ) -> uuid.UUID:
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, 'Probe', '2025-01-01', '2025-12-31', $4, $5, $6) "
                    "RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    self.partner,
                    type_,
                    status,
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
        return engagement

    @property
    def tenant_ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "human", str(self.partner))

    @property
    def person(self) -> AuthContext:
        return AuthContext(self.tenant_ctx, self.partner, uuid.uuid4(), None, datetime.now(UTC))

    async def move(self, engagement: uuid.UUID, status: str) -> None:
        """As the app does: the trigger reads under the request's tenant."""
        async with uow(self.tenant_ctx) as tx:
            await tx.session.execute(_MOVE, {"id": engagement, "status": status})
            tx.record("engagement.probed", target=Target("engagement", engagement))

    async def attest(self, client: uuid.UUID) -> bool:
        async with tenant_session(self.tenant_ctx) as session:
            record = await client_record(session, client)
        assert record is not None
        return record.is_attest_client


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


async def test_story_5_1_copperleaf_reads_non_attest_with_its_contacts(firm: _Firm) -> None:
    client, entity = await firm.client("Copperleaf")
    engagement = await firm.engagement(client, entity, "tax_compliance", "active")
    async with uow(firm.tenant_ctx) as tx:
        await set_client_record(tx, client, ClientRecordChange(kind="business", risk_tier="low"))
        tess = await add_contact(
            tx,
            firm.tenant,
            client,
            NewContact("Tess Moreno", "client_person", email="tess@example.test", title="Owner"),
        )
        ben = await add_contact(
            tx,
            firm.tenant,
            client,
            NewContact("Ben Ashby", "client_person", email="ben@example.test", title="Controller"),
        )
    assert await designate_contact(firm.person, engagement, ben, "approver_of_record") is True
    assert await designate_contact(firm.person, engagement, ben, "approver_of_record") is False

    async with tenant_session(firm.tenant_ctx) as session:
        record = await client_record(session, client)
    assert record is not None
    assert (record.kind, record.risk_tier, record.status) == ("business", "low", "active")
    assert record.is_attest_client is False
    assert [(c.display_name, c.contact_kind, c.title) for c in record.contacts] == [
        ("Ben Ashby", "client_person", "Controller"),
        ("Tess Moreno", "client_person", "Owner"),
    ]
    designations = await engagement_contacts(firm.person, engagement)
    assert [(d.contact_id, d.designation) for d in designations] == [(ben, "approver_of_record")]
    assert tess not in {d.contact_id for d in designations}


async def test_no_plaintext_taxpayer_id_column_exists(firm: _Firm) -> None:
    columns = await firm.seed.value(
        "SELECT coalesce(string_agg(table_name || '.' || column_name, ', '), '') "
        "FROM information_schema.columns WHERE table_schema = 'public' "
        "AND column_name ~ '(^|_)(tin|ssn|ein|itin|taxpayer_id)(_|$)' "
        "AND column_name !~ '_last4$'"
    )
    assert columns == ""


async def test_is_attest_client_follows_the_engagements(firm: _Firm) -> None:
    client, entity = await firm.client("Probe Audit Client")
    audit = await firm.engagement(client, entity, "fs_audit", "prospect")
    assert await firm.attest(client) is False  # a prospect isn't accepted yet
    await firm.move(audit, "accepted")
    assert await firm.attest(client) is True
    await firm.move(audit, "archived")
    assert await firm.attest(client) is False
    review = await firm.engagement(client, entity, "review", "prospect")
    await firm.move(review, "active")
    assert await firm.attest(client) is True


async def test_the_app_cannot_set_the_attest_flag(firm: _Firm) -> None:
    client, _ = await firm.client("Probe")
    granted = await firm.seed.value(
        "SELECT has_column_privilege('abacus_app', 'clients', 'is_attest_client', 'UPDATE')"
    )
    assert granted is False
    assert await firm.attest(client) is False


async def test_a_client_has_one_contact_per_email(firm: _Firm) -> None:
    client, _ = await firm.client("Probe")
    async with uow(firm.tenant_ctx) as tx:
        await add_contact(tx, firm.tenant, client, NewContact("A", "client_person", "a@x.test"))
    with pytest.raises(ContactExists):
        async with uow(firm.tenant_ctx) as tx:
            await add_contact(tx, firm.tenant, client, NewContact("B", "tcwg", "A@X.test"))


async def test_a_designation_names_only_the_engagements_clients_contact(firm: _Firm) -> None:
    client, entity = await firm.client("Probe")
    other, _ = await firm.client("Other")
    engagement = await firm.engagement(client, entity, "tax_compliance", "active")
    async with uow(firm.tenant_ctx) as tx:
        stranger = await add_contact(tx, firm.tenant, other, NewContact("C", "client_person"))
    with pytest.raises(NotFound):
        await designate_contact(firm.person, engagement, stranger, "primary_contact")
