"""A-08-T21 (TASK-8400; SPEC-657 AC-5.2, AC-5.3) against Postgres: an explanation without a
verified citation is refused with 422 `explanation_uncited`, and a decided materiality creates a
new analytics-set version without editing the old one (an unchanged line keeps its explanation)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import analytics as svc
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
D = Decimal


@pytest.fixture
async def audit(
    migrated_db: MigratedDatabase,
) -> AsyncIterator[tuple[AuthContext, uuid.UUID, uuid.UUID, Seeder]]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
                "('https://probe.test', $1, $2, 'Hannah Leclerc') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@x.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        user,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Granite Peak') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Granite "
        "Peak') RETURNING id",
        tenant,
        client,
    )
    engagement = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, status) VALUES ($1, $2, $3, "
                "'FY2026 Audit', '2026-01-01', '2026-12-31', $4, 'active') RETURNING id",
                tenant,
                client,
                entity,
                user,
            )
        )
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, "
        "$2, $3, 'manager')",
        tenant,
        engagement,
        user,
    )
    work_item = uuid.UUID(
        str(
            await seed.value(
                "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement,
            )
        )
    )
    ctx = AuthContext(
        TenantContext(tenant, "human", str(user)), user, uuid.uuid4(), None, datetime.now(UTC)
    )
    yield ctx, engagement, work_item, seed
    await dispose_engine()


def _source() -> list[svc.SourceLine]:
    return [
        svc.SourceLine("revenue", "Revenue", "income", "Income", D("9840000"), D("8610000"), ()),
        svc.SourceLine("interest", "Interest", "income", "Income", D("520000"), D("410000"), ()),
        svc.SourceLine("cogs", "Cost", "expense", "Expenses", D("5200000"), D("5050000"), ()),
    ]  # fmt: skip


async def _seed_set(
    ctx: AuthContext,
    engagement: uuid.UUID,
    work_item: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
    stage: svc.Stage = "preliminary",
) -> uuid.UUID:
    """A provisional set (preliminary unless named) at PM 116,250 computed over `_source()`."""

    async def no_dispatch(*_: object) -> None:
        return None

    async def source(*_: object) -> tuple[list[svc.SourceLine], bool]:
        return _source(), True

    class _Tb:
        class summary:
            period_end = datetime(2026, 12, 31).date()

    async def tb_view(*_: object, **__: object) -> _Tb:
        return _Tb()

    from abacus.modules.ledger import api as ledger

    monkeypatch.setattr(svc, "_dispatch", no_dispatch)
    monkeypatch.setattr(svc, "_source_lines", source)
    monkeypatch.setattr(ledger, "trial_balance_view", tb_view)
    set_id, version_no = await svc._start(  # pyright: ignore[reportPrivateUsage] -- the seam
        ctx.tenant,
        engagement_id=engagement,
        work_item_id=work_item,
        kind="audit_flux",
        stage=stage,
        trial_balance_id=uuid.uuid4(),
        layer="adjusted" if stage == "final" else "unadjusted",
        py_source="prior_engagement",
        threshold=svc.ThresholdFacts(D("10"), D("116250"), None, D("155000"), True),
        created_by=ctx.user_id,
        params={},
    )
    assert version_no == 1
    assert await svc.compute_set(ctx.tenant, set_id) == "current"
    return set_id


async def test_ac53_an_uncited_explanation_is_refused(
    audit: tuple[AuthContext, uuid.UUID, uuid.UUID, Seeder], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, engagement, work_item, _ = audit
    set_id = await _seed_set(ctx, engagement, work_item, monkeypatch)
    view = await svc.set_view(ctx, set_id, authorised=True)
    revenue = next(x for x in view.lines if x.fs_line_key == "revenue")
    assert revenue.status == "unexplained"
    with pytest.raises(svc.ExplanationUncited) as refused:
        await svc.explain(ctx, set_id, revenue.position, text_="Price rise", citation_ids=[])
    assert refused.value.code == "explanation_uncited"
    with pytest.raises(svc.ExplanationUncited):  # a citation nobody verified
        await svc.explain(
            ctx, set_id, revenue.position, text_="Price rise", citation_ids=[uuid.uuid4()]
        )


async def test_ac52_decided_materiality_is_a_new_version(
    audit: tuple[AuthContext, uuid.UUID, uuid.UUID, Seeder], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, engagement, work_item, seed = audit
    old = await _seed_set(ctx, engagement, work_item, monkeypatch)
    view = await svc.set_view(ctx, old, authorised=True)
    revenue = next(x for x in view.lines if x.fs_line_key == "revenue")
    # A staff explanation, recorded as if cited (the seeder writes past the citation check).
    await seed.run(
        "INSERT INTO analytics_explanations (tenant_id, set_id, line_position, text, "
        "citation_ids, source, authored_by) VALUES ($1, $2, $3, 'Price rise', "
        "ARRAY[$4::uuid], 'staff', $5)",
        ctx.tenant_id,
        old,
        revenue.position,
        uuid.uuid4(),
        ctx.user_id,
    )
    before = await seed.value("SELECT count(*) FROM analytics_lines WHERE set_id = $1", old)

    async def decided(*_: object) -> svc.ThresholdFacts:
        return svc.ThresholdFacts(D("10"), D("120000"), None, D("160000"), False)

    monkeypatch.setattr(svc, "threshold_for", decided)
    event = OutboxEvent(
        uuid.uuid4(), ctx.tenant_id, "materiality.decided", {"work_item_id": str(work_item)}
    )
    await svc.on_materiality_decided(event)
    await svc.on_materiality_decided(event)  # idempotent on the event
    new = uuid.UUID(
        str(
            await seed.value(
                "SELECT id FROM analytics_sets WHERE work_item_id = $1 AND version_no = 2",
                work_item,
            )
        )
    )
    assert (
        await seed.value("SELECT count(*) FROM analytics_sets WHERE work_item_id = $1", work_item)
        == 2
    )
    assert await svc.compute_set(ctx.tenant, new) == "current"
    assert await seed.value("SELECT status FROM analytics_sets WHERE id = $1", old) == "superseded"
    assert (
        await seed.value("SELECT count(*) FROM analytics_lines WHERE set_id = $1", old) == before
    )
    assert await seed.value("SELECT threshold_amount FROM analytics_sets WHERE id = $1", old) == D(
        "116250.00"
    )
    fresh = await svc.set_view(ctx, new, authorised=True)
    assert not fresh.threshold.provisional
    carried = next(x for x in fresh.lines if x.fs_line_key == "revenue")
    assert carried.status == "explained"  # still over at 120,000: the explanation carried


async def test_an_accepted_entry_puts_the_final_set_out_of_date(
    audit: tuple[AuthContext, uuid.UUID, uuid.UUID, Seeder], monkeypatch: pytest.MonkeyPatch
) -> None:
    """S48 rest (A-08-T21): an entry the client accepted lands on the adjusted layer, so the
    Current final-stage set reads Out of date; a decline changes nothing, a preliminary set is
    untouched and a replay writes nothing more."""
    ctx, engagement, work_item, seed = audit
    final = await _seed_set(ctx, engagement, work_item, monkeypatch, stage="final")

    def event(decision: str) -> OutboxEvent:
        return OutboxEvent(
            uuid.uuid4(),
            ctx.tenant_id,
            "proposed_entry.client_decided",
            {"work_item_id": str(work_item), "entry_id": str(uuid.uuid4()), "decision": decision},
        )

    status = "SELECT status || ':' || coalesce(failure_code, '') FROM analytics_sets WHERE id = $1"
    await svc.on_entry_client_decided(event("client_declined"))
    assert await seed.value(status, final) == "current:"
    accepted = event("client_accepted")
    await svc.on_entry_client_decided(accepted)
    await svc.on_entry_client_decided(accepted)
    assert await seed.value(status, final) == "out_of_date:adjustment_recorded"
    assert (
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE action = 'analytics.went_out_of_date' "
            "AND target_id = $1",
            str(final),
        )
        == 1
    )
