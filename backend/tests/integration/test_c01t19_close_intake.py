"""C-01-T19 (TASK-8071; SPEC-655 F2; CLS-03, POR-11) against Postgres: BD1 publish and the tree.

Row acceptance: "The September close pins the version effective for 2026-09 and publishes its
requests (8 under v3, 7 under v4) at 09:00 CT on Thu Oct 1, 2026 on the demo clock,
incorporating the Square payouts offers 'Re-run affected tasks' for exactly the Square procedure,
and no request is published twice on replay." Here the published version carries 8 templates and
a later version effective 2026-09 carries 7.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from abacus.kernel import clock
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.closes import intake
from abacus.modules.closes import service as closes_service

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import _Firm

pytestmark = pytest.mark.asyncio

BD1_0900_CT = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)  # Thu Oct 1, 2026 09:00 CDT


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _templates(firm: _Firm, version: uuid.UUID, titles: list[str], square_row: uuid.UUID | None) -> dict[str, uuid.UUID]:
    out: dict[str, uuid.UUID] = {}
    for title in titles:
        internal = title.startswith("Bank feed")
        sources = [square_row] if (square_row is not None and "Square" in title) else []
        out[title] = uuid.UUID(str(await firm.seed.value(
            "INSERT INTO close_request_templates (tenant_id, version_id, title, category_path, "
            "due_business_day, client_visible, source_row_ids) VALUES ($1, $2, $3, $4, 3, $5, $6) "
            "RETURNING id",
            firm.tenant, version, title, ["Bank & cards" if "Bank" in title else "Sales"],
            not internal, sources,
        )))  # fmt: skip
    return out


EIGHT = [
    "Bank feed: Operating ••4417", "Bank statement: Operating", "Card statement: Amex",
    "Square payouts report", "Payroll register", "Loan statement", "Sales tax return",
    "Inventory count",
]  # fmt: skip


async def _september(firm: _Firm) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    engagement, _, entity = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    closes = await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    version = await firm.plan(entity, ["4417", "8812"])
    square_row = uuid.UUID(str(await firm.seed.value(
        "SELECT id FROM close_plan_rows WHERE version_id = $1 AND position = 1", version
    )))  # fmt: skip
    await _templates(firm, version, EIGHT, square_row)
    september = closes[8]
    return september, version, square_row


async def test_ac_publishes_eight_at_bd1_and_never_twice(firm: _Firm) -> None:
    september, _, _ = await _september(firm)
    with clock.frozen(datetime(2026, 9, 30, 14, 0, tzinfo=UTC)):
        wait = await intake.seconds_until_publish(firm.tenant, september)
    assert wait == 24 * 3600  # BD1 is Thu Oct 1; 09:00 CT is 14:00 UTC
    with clock.frozen(BD1_0900_CT):
        first = await intake.publish_requests(firm.tenant, september)
        replay = await intake.publish_requests(firm.tenant, september)
    assert first.created == 8
    assert replay.created == 0
    count = await firm.seed.value(
        "SELECT count(*) FROM request_items i JOIN request_lists l ON l.id = i.request_list_id "
        "WHERE l.work_item_id = $1 AND l.kind = 'close_intake'",
        september,
    )
    assert count == 8
    internal = await firm.seed.value(
        "SELECT count(*) FROM request_items i JOIN request_lists l ON l.id = i.request_list_id "
        "WHERE l.work_item_id = $1 AND NOT i.client_visible",
        september,
    )
    assert internal == 1  # the bank feed (QC-1)
    with clock.frozen(BD1_0900_CT):
        assert await intake.seconds_until_publish(firm.tenant, september) == -1


async def test_ac_a_version_effective_for_september_wins(firm: _Firm) -> None:
    september, first_version, _ = await _september(firm)
    plan = await firm.seed.value("SELECT plan_id FROM close_plan_versions WHERE id = $1", first_version)
    later = uuid.UUID(str(await firm.seed.value(
        "INSERT INTO close_plan_versions (tenant_id, plan_id, version, drafted_by) "
        "VALUES ($1, $2, 2, $3) RETURNING id", firm.tenant, plan, firm.partner,
    )))  # fmt: skip
    await _templates(firm, later, EIGHT[:7], None)
    await firm.seed.run(
        "UPDATE close_plan_versions SET status = 'published', effective_from = '2026-09', "
        "published_by = $2, published_actor_kind = 'human', published_at = now() WHERE id = $1",
        later, firm.partner,
    )  # fmt: skip
    with clock.frozen(BD1_0900_CT):
        done = await intake.publish_requests(firm.tenant, september)
    assert (done.created, done.plan_version) == (7, 2)


async def test_ac_incorporating_square_offers_rerun_of_exactly_its_procedure(firm: _Firm) -> None:
    september, _, square_row = await _september(firm)
    with clock.frozen(BD1_0900_CT):
        await intake.publish_requests(firm.tenant, september)
    await firm.seed.run(
        "UPDATE request_items SET incorporation_state = 'incorporated' WHERE title = 'Square payouts report' "
        "AND tenant_id = $1",
        firm.tenant,
    )
    tree = await intake.request_tree(firm.ctx(), september)
    requests = [r for n in tree.nodes for r in (n.children or [n])]
    offers = {r.title: r.rerun_plan_row_ids for r in requests if r.kind == "request"}
    assert offers["Square payouts report"] == [square_row]
    assert all(v == [] for k, v in offers.items() if k != "Square payouts report")
    assert tree.published and tree.plan_version == 1
