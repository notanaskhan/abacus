"""C-01-T14 (TASK-8032; SPEC-655 AC-2, AC-4, AC-9 to AC-13) against Postgres: the close record.

The task's acceptance: "a move to In review at 20 of 21 answers 409 naming the missing account,
and walled closes are absent from rows and counts". Copperleaf's 43% (9 / 21), 7 open issues and
4 days past due foot in the figure book (C-01-T13) and land through the seed tests (T44).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest

import abacus.modules.closes.api  # registers the `close` kind
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.closes import business_days, service
from abacus.modules.closes.contract import (
    AccountsNotReconciled,
    OnHoldIn,
    StatusMoveIn,
    TransitionNotAvailable,
)
from abacus.modules.engagements.api import WorkItemExists
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def user(self, name: str) -> uuid.UUID:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                    name,
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
        self.partner = await self.user("Priya Raman")
        return self

    async def engagement(self, client_name: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            self.tenant,
            client_name,
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant,
            client,
            client_name,
        )
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, '2026 Close', '2026-01-01', '2026-12-31', $4, "
                    "'cas_monthly_close', 'active') RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    self.partner,
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
        return engagement, uuid.UUID(str(client)), uuid.UUID(str(entity))

    def ctx(self, user: uuid.UUID | None = None, actor_kind: str = "human") -> AuthContext:
        who = user or self.partner
        # An agent acts for a person (Q-02-T16): its audit rows carry the person it acts for.
        on_behalf = who if actor_kind == "agent" else None
        tenant = TenantContext(self.tenant, actor_kind, str(who), on_behalf)  # type: ignore[arg-type] -- the test's actor kind literal
        return AuthContext(tenant, who, uuid.uuid4(), None, datetime.now(UTC))

    async def plan(
        self, entity: uuid.UUID, accounts: list[str], *, publish: bool = True
    ) -> uuid.UUID:
        """A published plan whose rows are bank reconciliations, one per account (a draft when
        `publish` is False: a published version never changes, so its templates go in first)."""
        plan = await self.seed.value(
            "INSERT INTO close_plans (tenant_id, client_entity_id, created_by) "
            "VALUES ($1, $2, $3) RETURNING id",
            self.tenant,
            entity,
            self.partner,
        )
        version = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO close_plan_versions (tenant_id, plan_id, version, drafted_by) "
                    "VALUES ($1, $2, 1, $3) RETURNING id",
                    self.tenant,
                    plan,
                    self.partner,
                )
            )
        )
        for position, account in enumerate(accounts):
            await self.seed.run(
                "INSERT INTO close_plan_rows (tenant_id, version_id, position, "
                "account_external_id, account_name, account_class, procedure, method, source, "
                "review_level) VALUES ($1, $2, $3, $4, $5, 'Bank', 'reconciliation', "
                "'Bank statement → GL', 'bank_feed', 'senior_signoff')",
                self.tenant,
                version,
                position,
                account,
                f"Account {account}",
            )
        if publish:
            await self.publish(version)
        return version

    async def publish(self, version: uuid.UUID) -> None:
        await self.seed.run(
            "UPDATE close_plan_versions SET status = 'published', effective_from = '2026-01', "
            "published_by = $2, published_actor_kind = 'human', published_at = now() "
            "WHERE id = $1",
            version,
            self.partner,
        )

    async def reconcile(self, close_id: uuid.UUID, account: str, tally: str = "tie") -> None:
        """A tied reconciliation with a current L1 sign-off on its content hash."""
        content = hashlib.sha256(f"{close_id}:{account}".encode()).hexdigest()
        rec = await self.seed.value(
            "INSERT INTO reconciliations (tenant_id, close_id, account_external_id, period, "
            "version, balance_per_bank, adjusted_bank, book_balance, adjusted_book, difference, "
            "tally, engine_version, inputs_hash, content_hash) VALUES ($1, $2, $3, '2026-08', 1, "
            "100, 100, 100, 100, $5, $4, 'reconciliation-1.0.0', $6, $6) RETURNING id",
            self.tenant,
            close_id,
            account,
            tally,
            0 if tally == "tie" else 1,
            content,
        )
        await self.seed.run(
            "INSERT INTO sign_offs (tenant_id, engagement_id, target_type, target_id, level, "
            "signed_by, actor_kind, actor_id, content_hash) SELECT $1, engagement_id, "
            "'reconciliation', $2, 1, $3::uuid, 'human', $3::uuid::text, $4 FROM closes "
            "WHERE work_item_id = $5",
            self.tenant,
            rec,
            self.partner,
            content,
            close_id,
        )


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    # Fresh pools on this test's loop (the identity engine, for names_of, rebuilds from the
    # settings), disposed after it: no connection outlives its loop.
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _august(firm: _Firm, client: str = "Copperleaf Coffee Roasters, Inc.") -> uuid.UUID:
    engagement, _, _ = await firm.engagement(client)
    closes = await service.generate_closes(firm.ctx(), engagement, 2026)
    return closes[7]


async def test_ac13_twelve_closes_with_bd1_and_due_dates(
    firm: _Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The platform's `legal_holidays` set is K-02's (its suite publishes and reads it); here the
    # calendar holds Labor Day 2026 so BD7 is counted past it.
    async def labor_day(_latest: date) -> frozenset[date]:
        return frozenset({date(2026, 9, 7)})

    monkeypatch.setattr(business_days, "_holidays", labor_day)
    engagement, _, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    created = await service.generate_closes(firm.ctx(), engagement, 2026)
    assert len(created) == 12
    periods = await firm.seed.rows(
        "SELECT period, requests_publish_on, due_on, status FROM closes "
        "WHERE engagement_id = $1 ORDER BY period",
        engagement,
    )
    assert [p["period"] for p in periods] == [f"2026-{m:02d}" for m in range(1, 13)]
    august = periods[7]
    # BD1 after Mon Aug 31 is Tue Sep 1; BD7 is Thu Sep 10 (Labor Day, Sep 7, is skipped).
    assert (august["requests_publish_on"], august["due_on"]) == (
        date(2026, 9, 1),
        date(2026, 9, 10),
    )
    assert {p["status"] for p in periods} == {"not_started"}
    with pytest.raises(WorkItemExists):
        await service.generate_closes(firm.ctx(), engagement, 2026)


async def test_ac9_in_review_at_20_of_21_names_the_missing_account(firm: _Firm) -> None:
    engagement, _, entity = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    close = (await service.generate_closes(firm.ctx(), engagement, 2026))[7]
    accounts = [f"{n:02d}" for n in range(1, 22)]
    await firm.plan(entity, accounts)
    for account in accounts[:20]:
        await firm.reconcile(close, account)
    async with uow(firm.ctx().tenant) as tx:  # the system's first run (AC-11)
        assert await service.start_close(tx, close)
    summary = await service.close_summary(firm.ctx(), close)
    assert (summary.accounts_reconciled, summary.accounts_total) == (20, 21)
    assert summary.in_review_blocked_by == "accounts_not_reconciled"
    with pytest.raises(AccountsNotReconciled) as refused:
        await service.move_status(
            firm.ctx(), close, StatusMoveIn(to="in_review"), str(summary.row_version)
        )
    row_21 = await firm.seed.value(
        "SELECT id FROM close_plan_rows WHERE tenant_id = $1 AND account_name = 'Account 21'",
        firm.tenant,
    )
    assert refused.value.facts["plan_row_id"] == str(row_21)
    await firm.reconcile(close, accounts[20])
    moved = await service.move_status(
        firm.ctx(), close, StatusMoveIn(to="in_review"), str(summary.row_version)
    )
    assert moved.status == "in_review" and moved.accounts_reconciled == 21
    events = await firm.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND action = 'close.status_changed'",
        firm.tenant,
    )
    assert len(events) == 2  # Not started → In progress, In progress → In review


async def test_ac2_an_untied_or_unsigned_account_does_not_count(firm: _Firm) -> None:
    engagement, _, entity = await firm.engagement("Two Rivers Brewing Co.")
    close = (await service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await firm.plan(entity, ["35", "36"])
    await firm.reconcile(close, "35")
    await firm.reconcile(close, "36", tally="off")
    facts = await service.close_for(firm.ctx().tenant, close)
    assert (facts.accounts_reconciled, facts.accounts_total) == (1, 2)


async def test_ac11_approved_delivered_locked_fail_closed(firm: _Firm) -> None:
    close = await _august(firm)
    for to in ("approved", "delivered", "locked"):
        with pytest.raises(TransitionNotAvailable):
            await service.move_status(firm.ctx(), close, StatusMoveIn(to=to), "1")


async def test_ac12_an_agent_is_refused_and_the_refusal_kept(firm: _Firm) -> None:
    close = await _august(firm)
    with pytest.raises(Forbidden):
        await service.move_status(
            firm.ctx(actor_kind="agent"), close, StatusMoveIn(to="in_review"), "1"
        )
    refused = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'decision.refused_non_human'",
        firm.tenant,
    )
    assert int(str(refused)) == 1


async def test_ac10_on_hold_keeps_the_status_and_needs_a_reason(firm: _Firm) -> None:
    close = await _august(firm)
    held = await service.move_status(
        firm.ctx(), close, StatusMoveIn(on_hold=OnHoldIn(reason="Statements not received")), "1"
    )
    assert (held.status, held.on_hold, held.on_hold_reason) == (
        "not_started", True, "Statements not received",
    )  # fmt: skip


async def test_ac4_walled_closes_are_absent_from_rows_tiles_and_summary(firm: _Firm) -> None:
    await _august(firm, "Copperleaf Coffee Roasters, Inc.")
    walled_engagement, walled_client, _ = await firm.engagement("Bluebird Bakery Co.")
    walled = (await service.generate_closes(firm.ctx(), walled_engagement, 2026))[7]
    raj = await firm.user("Raj Malhotra")
    for engagement in (
        await firm.seed.value("SELECT engagement_id FROM closes WHERE tenant_id = $1 "
                              "AND engagement_id <> $2 LIMIT 1", firm.tenant, walled_engagement),
        walled_engagement,
    ):  # fmt: skip
        await firm.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'manager')",
            firm.tenant,
            engagement,
            raj,
        )
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        raj,
        walled_client,
        firm.partner,
    )
    listed = await service.list_closes(firm.ctx(raj), period="2026-08")
    assert [r.client_name for r in listed.items] == ["Copperleaf Coffee Roasters, Inc."]
    assert sum(listed.tiles.model_dump().values()) == 1
    with pytest.raises(NotFound):
        await service.close_summary(firm.ctx(raj), walled)
    everyone = await service.list_closes(firm.ctx(), period="2026-08")
    assert len(everyone.items) == 2 and everyone.tiles.not_started == 2


async def test_ac1_tiles_count_before_the_status_filter(firm: _Firm) -> None:
    await _august(firm, "Copperleaf Coffee Roasters, Inc.")
    await _august(firm, "Juniper & Oak Interiors, LLC")
    filtered = await service.list_closes(firm.ctx(), period="2026-08", status="in_review")
    assert filtered.items == [] and filtered.tiles.not_started == 2
