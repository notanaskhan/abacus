"""C-02-T39 on the migrated database (TASK-8920; C-02 F8; CLS-12 a to d; C12; DEC-5922): the
August close is not available; the locked December 2026 close hands off TB v1 to the 2026 Form
1120-S with its three tax-relevant notes as tax items, and the return's preparer and reviewer are
told; after the close is reopened and locked again, TB v2 supersedes v1."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest

from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.modules.closes import service
from abacus.modules.closes import tax_handoff as th
from abacus.modules.closes.issues import add_note

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the close suite's firm builder
)

pytestmark = pytest.mark.asyncio

NOTES = (
    "Accrued payroll at Dec 31 includes wages of a shareholder-employee",
    "Sound Electric repair: keep the repair analysis in the tax file",
    "Square and Shopify 2026 Forms 1099-K: reconcile gross amounts to gross receipts",
)


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _return(
    firm: _Firm, client: uuid.UUID, entity: uuid.UUID
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    seed = firm.seed
    olivia, samuel = await firm.user("Olivia Brandt"), await firm.user("Samuel Ito")
    engagement = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by, type, status) VALUES ($1, $2, "
            "$3, '2026 Form 1120-S', '2026-01-01', '2026-12-31', $4, 'tax_compliance', 'active') "
            "RETURNING id",
            firm.tenant, client, entity, firm.partner,
        ),
    )  # fmt: skip
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'tax_return', "
            "'2026 Form 1120-S', '2026-01-01', '2026-12-31', $5) RETURNING id",
            firm.tenant, engagement, client, entity, firm.partner,
        ),
    )  # fmt: skip
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year, engine) VALUES ($1, $2, $3, $4, '1120s', 2026, 'cch_axcess')",
        firm.tenant, item, engagement, entity,
    )  # fmt: skip
    for user, function in ((olivia, "preparer"), (samuel, "detail_reviewer")):
        await seed.run(
            "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
            "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $6)",
            firm.tenant, item, engagement, user, function, firm.partner,
        )  # fmt: skip
    return item, [olivia, samuel]


async def _ledger(firm: _Firm, entity: uuid.UUID) -> None:
    # Lines join a snapshot only in the transaction that wrote it (ADR-004's trigger): one
    # statement writes the header and its three lines.
    await firm.seed.run(
        "WITH s AS (INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, "
        "period_end, pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
        "VALUES ($1, $2, '2026-01-01', '2026-12-31', now(), 'import', md5(random()::text) || "
        "md5(random()::text), 3, 300000, 300000) RETURNING id) "
        "INSERT INTO trial_balance_lines (tenant_id, snapshot_id, account_code, account_name, "
        "debit, credit, source_ref) SELECT $1, s.id, l.code, l.name, l.debit, l.credit, "
        "'{}'::jsonb FROM s, (VALUES ('1000', 'Cash', 156000, 0), "
        "('3100', 'Shareholder distributions', 144000, 0), ('4000', 'Sales', 0, 300000)) "
        "AS l (code, name, debit, credit)",
        firm.tenant, entity,
    )  # fmt: skip


async def _lock(firm: _Firm, close_id: uuid.UUID) -> None:
    await firm.seed.run(
        "UPDATE closes SET status = 'locked', locked_at = now(), row_version = row_version + 1 "
        "WHERE work_item_id = $1",
        close_id,
    )


async def test_cls12_hands_off_tb_v1_and_supersedes_after_a_reopen(firm: _Firm) -> None:
    engagement, client, entity = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    closes = await service.generate_closes(firm.ctx(), engagement, 2026)
    august, december = closes[7], closes[11]
    ctx = firm.ctx()

    not_yet = await th.availability(ctx, august)
    assert (not_yet.status, not_yet.reason) == (
        "not_available", "Available after the December 2026 close locks",
    )  # fmt: skip

    target, team = await _return(firm, client, entity)
    await _ledger(firm, entity)
    notes = [await add_note(ctx, december, issue_class="schedule", title=t) for t in NOTES]
    await _lock(firm, december)

    ready = await th.availability(ctx, december)
    assert (ready.status, ready.tb_version, ready.target_return_id) == ("ready", "TB v1", target)
    assert {i.issue_id for i in ready.items} == set(notes)
    assert [s.key for s in ready.schedules] == ["shareholder_distributions"]

    first = await th.publish(
        ctx, december, schedules_on=["shareholder_distributions"], items_on=notes,
        seen_version=ready.version,
    )  # fmt: skip
    assert (first.tb_version, first.tax_issues) == ("TB v1", 3)
    rows = await firm.seed.rows(
        "SELECT event_type, payload FROM outbox WHERE tenant_id = $1 AND event_type IN "
        "('tax_handoff.published', 'tb_handoff.created') ORDER BY id",
        firm.tenant,
    )
    assert {r["event_type"] for r in rows} == {"tax_handoff.published", "tb_handoff.created"}
    assert (await th.availability(ctx, december)).status == "handed_off"

    async with firm.seed.held() as conn:
        await conn.execute("SELECT set_config('app.actor_kind', 'human', false)")
        await conn.execute(
            "INSERT INTO close_reopenings (tenant_id, close_id, reopened_by, reason) VALUES "
            "($1, $2, $3, 'A late vendor credit')",
            firm.tenant, december, firm.partner,
        )  # fmt: skip
    await _lock(firm, december)
    again = await th.availability(ctx, december)
    assert (again.status, again.tb_version, again.superseded_on_next) == ("ready", "TB v2", True)
    second = await th.publish(
        ctx, december, schedules_on=[], items_on=[], seen_version=again.version
    )
    assert second.tb_version == "TB v2"
    superseded = await firm.seed.value(
        "SELECT superseded_by_id FROM tax_handoffs WHERE id = $1", first.handoff_id
    )
    assert superseded == second.handoff_id
    told = await firm.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'tax_handoff.superseded'",
        firm.tenant,
    )
    assert len(told) == 1 and set(str(u) for u in team) <= set(
        str(u) for u in json.loads(told[0]["payload"]).get("recipient_user_ids", [])
    )
