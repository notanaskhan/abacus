"""P-07-T15 against Postgres (SPEC-321 AC-16, AC-17; engagements-v2 contract §3): ENG-01's index
tiles foot to the total over one `visible()` base, a walled engagement is absent from rows,
tiles and totals, "Letter │ Not signed" lists Accepted engagements and no Prospect, rows sort
past due first; ENG-02's record carries its bands, letter, gates and version; the interim
recorded letter refuses a date before the G1 decision (409 `letter_before_acceptance`), an
unmet G1 (409 `gate_unmet`) and an archived engagement, and otherwise moves the engagement to
Contracted with one `letter.recorded` audit event and `gate.met`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest

import abacus.modules.engagements.api  # registers the gates, facts and authz lookups
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.index import IndexFilters, engagement_index
from abacus.modules.engagements.record import (
    EngagementArchived,
    GateUnmet,
    LetterBeforeAcceptance,
    LetterExceptionsOff,
    RecordedLetterIn,
    engagement_gates_v2,
    engagement_record,
    record_letter_v2,
)
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api
pytestmark = pytest.mark.asyncio


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


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Brightwater Hale', true)",
            self.tenant,
        )
        return self

    async def person(
        self, *, firm_role: str | None = None, level: str | None = None
    ) -> AuthContext:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Margaret Okonkwo') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
            "VALUES ($1, $2, $3, 'active', $4)",
            self.tenant,
            user,
            firm_role,
            level,
        )
        return AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )

    async def client(self, name: str) -> tuple[uuid.UUID, uuid.UUID]:
        client = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name, kind) VALUES ($1, $2, 'business') "
                    "RETURNING id",
                    self.tenant,
                    name,
                )
            )
        )
        entity = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                    "RETURNING id",
                    self.tenant,
                    client,
                    f"{name} LLC",
                )
            )
        )
        return client, entity

    async def engagement(
        self,
        name: str,
        status: str,
        partner: AuthContext,
        *,
        type_: str = "fs_audit",
        client: tuple[uuid.UUID, uuid.UUID] | None = None,
        due: date | None = None,
    ) -> uuid.UUID:
        client_id, entity = client or await self.client(name)
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5, $6, $7) "
                    "RETURNING id",
                    self.tenant,
                    client_id,
                    entity,
                    name,
                    partner.user_id,
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
            partner.user_id,
        )
        if due is not None:  # an audit's assurance work item is created with it
            await self.seed.run(
                "UPDATE work_items SET due_on = $1 WHERE engagement_id = $2", due, engagement
            )
        return engagement

    async def accept(self, engagement: uuid.UUID, at: datetime) -> None:
        await self.seed.open_engagement(self.tenant, engagement, concluded=False, decided_at=at)


async def _firm(migrated_db: MigratedDatabase) -> _Firm:
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


async def test_ac16_tiles_foot_to_the_total_and_a_walled_engagement_is_absent(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    margaret = await firm.person(level="partner")
    admin = await firm.person(firm_role="firm_admin")
    soon = date.today() + timedelta(days=3)
    late = date.today() - timedelta(days=5)
    await firm.engagement("Northwind PY2025", "active", margaret, due=soon)
    await firm.engagement("Granite Peak FY2025", "accepted", margaret, due=late)
    await firm.engagement("Bluestem FY2025", "accepted", margaret)
    await firm.engagement("Thornbury estate", "prospect", margaret, type_="tax_compliance")
    await firm.engagement("Old declined", "declined", margaret)
    walled = await firm.engagement("Ashford FY2025", "active", margaret)
    ashford = (await firm.seed.rows("SELECT client_id FROM engagements WHERE id = $1", walled))[0][
        "client_id"
    ]
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        margaret.user_id,
        ashford,
        admin.user_id,
    )

    page, summary = await engagement_index(margaret, IndexFilters(), cursor=None, limit=50)
    names = [r.engagement.name for r in page.items]
    assert names[:2] == ["Granite Peak FY2025", "Northwind PY2025"]  # past due first, then soon
    assert "Ashford FY2025" not in names and "Old declined" not in names
    assert page.total == 4
    assert page.counts is not None and sum(page.counts.values()) == page.total
    assert "declined" not in page.counts
    assert page.facets is not None
    assert sum(f.n for f in page.facets["service_line"]) == page.total
    assert (summary.prospect, summary.awaiting_letter, summary.past_due) == (1, 2, 1)
    granite = next(r for r in page.items if r.engagement.name == "Granite Peak FY2025")
    assert granite.next_due is not None and granite.next_due.tone == "past_due"
    assert granite.partner_initials == "MO"
    assert granite.letter.status == "not_signed"

    tiled, _ = await engagement_index(
        margaret, IndexFilters(tile="accepted"), cursor=None, limit=50
    )
    assert tiled.total == 2
    assert tiled.counts == page.counts  # the selected tile never shrinks its own count

    unsigned, _ = await engagement_index(
        margaret, IndexFilters(letter="not_signed"), cursor=None, limit=50
    )
    assert sorted(r.engagement.name for r in unsigned.items) == [
        "Bluestem FY2025",
        "Granite Peak FY2025",
        "Northwind PY2025",
    ]  # no Prospect; Northwind is active without a recorded letter

    first, _ = await engagement_index(margaret, IndexFilters(), cursor=None, limit=2)
    assert first.next_cursor is not None
    rest, _ = await engagement_index(margaret, IndexFilters(), cursor=first.next_cursor, limit=2)
    assert len({r.engagement.id for r in first.items + rest.items}) == 4


async def test_ac16_the_record_carries_bands_gates_and_version(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    priya = await firm.person()
    bluestem = await firm.engagement("Bluestem FY2025", "accepted", priya)
    await firm.accept(bluestem, datetime.now(UTC) - timedelta(days=10))

    record = await engagement_record(priya, bluestem)
    assert record.engagement.version == 1
    assert [b.band for b in record.bands][:2] == ["details", "review_delivery"]
    assert record.bands[1].rows[0].user_id == priya.user_id
    gates = {g.gate: g for g in record.gates}
    assert gates["G1"].met and gates["G1"].met_at is not None
    assert record.letter.status == "not_signed"
    assert record.read_only_reason is None
    assert "letter.record" in record.allowed_actions
    assert [g.gate for g in await engagement_gates_v2(priya, bluestem)] == [
        g.gate for g in record.gates
    ]
    stranger = await firm.person()
    with pytest.raises(Forbidden):
        await engagement_record(stranger, bluestem)
    with pytest.raises(NotFound):
        await engagement_record(priya, uuid.uuid4())


async def test_ac17_a_letter_before_acceptance_is_409_and_a_good_one_contracts(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    priya = await firm.person()
    bluestem = await firm.engagement("Bluestem FY2025", "accepted", priya)
    signed = RecordedLetterIn(
        mode="signed",
        client_signed_on=date.today(),
        firm_signed_on=date.today(),
    )
    with pytest.raises(GateUnmet):  # no acceptance decision yet
        await record_letter_v2(priya, bluestem, signed)
    await firm.accept(bluestem, datetime.now(UTC) - timedelta(days=2))
    early = RecordedLetterIn(
        mode="signed",
        client_signed_on=date.today() - timedelta(days=5),
        firm_signed_on=date.today(),
    )
    with pytest.raises(LetterBeforeAcceptance):
        await record_letter_v2(priya, bluestem, early)
    with pytest.raises(LetterExceptionsOff):
        await record_letter_v2(priya, bluestem, RecordedLetterIn(mode="not_required_this_year"))

    done = await record_letter_v2(priya, bluestem, signed)
    assert done.engagement_status == "contracted"
    assert done.letter.client_signed_on == date.today()
    audit = await firm.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "ORDER BY occurred_at",
        firm.tenant,
        str(bluestem),
    )
    actions = [a["action"] for a in audit]
    assert actions.count("letter.recorded") == 1 and "engagement.contracted" in actions
    outbox = await firm.seed.rows(
        "SELECT event_type FROM outbox WHERE tenant_id = $1 AND event_type = 'gate.met'",
        firm.tenant,
    )
    assert len(outbox) == 1
    record = await engagement_record(priya, bluestem)
    assert record.letter.status == "signed" and record.engagement.version >= 2
    gates = {g.gate: g for g in record.gates}
    if "G3" in gates:
        assert gates["G3"].met and gates["G3"].met_by_user_id == priya.user_id


async def test_ac17_an_archived_engagement_refuses_the_letter(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    priya = await firm.person()
    old = await firm.engagement("Meridian FY2023", "archived", priya)
    with pytest.raises(EngagementArchived):
        await record_letter_v2(
            priya,
            old,
            RecordedLetterIn(
                mode="signed", client_signed_on=date.today(), firm_signed_on=date.today()
            ),
        )
    record = await engagement_record(priya, old)
    assert record.read_only_reason == "archived"
