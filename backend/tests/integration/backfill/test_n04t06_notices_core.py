"""N-04-T06 (TASK-3210; DEC-2210): NOT-01's index, summary, detail and Start over HTTP.

The A-04 backfill world's engagement holds two notices (inserted as N-04-T07's intake would); the
senior reads them, starts the first, and a second Start answers 409 `illegal_transition`.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import cast

import pytest

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    # `notices.workspace` retired at N-04-T27 (DEC-2602): the routes are on for every firm.
    return await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture


async def _notice(world: Books, code: str, respond_by: str) -> uuid.UUID:
    client = await world.seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.site.engagement_id
    )
    item = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'notice', $4, $5) RETURNING id",
            world.tenant_id,
            world.site.engagement_id,
            client,
            f"{code} · TY2024",
            world.senior.user_id,
        ),
    )
    # notice.start needs a function on the work item (function_in): the senior prepares.
    await world.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'preparer', $4)",
        world.tenant_id,
        item,
        world.site.engagement_id,
        world.senior.user_id,
    )
    await world.seed.run(
        "INSERT INTO notices (tenant_id, work_item_id, engagement_id, notice_code, received_on, "
        "agency, notice_type_key, title, tax_year, respond_by) VALUES ($1, $2, $3, $4, "
        "'2026-08-24', 'irs', 'cp2000', 'Proposed adjustment', 2024, $5::date)",
        world.tenant_id,
        item,
        world.site.engagement_id,
        code,
        date.fromisoformat(respond_by),
    )
    return item


async def test_ac1_index_summary_and_start(world: Books) -> None:
    first = await _notice(world, "CP2000", "2026-09-23")
    await _notice(world, "CP14", "2026-10-30")
    listed = await world.call("GET", "/v1/notices", world.senior)
    assert listed.status_code == 200, listed.text
    body = cast(Json, listed.json())
    assert [r["notice_code"] for r in cast(list[Json], body["items"])][:2] == ["CP2000", "CP14"]
    assert cast(Json, body["counts"])["new"] == 2
    summary = await world.call("GET", "/v1/notices/summary", world.senior)
    assert summary.status_code == 200, summary.text
    assert cast(Json, summary.json())["tiles"] == {
        "new": 2,
        "analyzing": 0,
        "response_drafted": 0,
        "awaiting": 0,
    }
    started = await world.call(
        "POST",
        f"/v1/notices/{first}:start",
        world.senior,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert started.status_code == 200, started.text
    assert cast(Json, cast(Json, started.json())["row"])["status"] == "classified"
    again = await world.call(
        "POST",
        f"/v1/notices/{first}:start",
        world.senior,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert again.status_code == 409, again.text
    assert cast(Json, again.json())["detail"] == "illegal_transition"
    events = await world.seed.value(
        "SELECT count(*) FROM notice_status_events WHERE work_item_id = $1", first
    )
    assert events == 1


async def test_ac1_a_stale_edit_is_409(world: Books) -> None:
    first = await _notice(world, "CP2000", "2026-09-23")
    stale = await world.call(
        "PATCH",
        f"/v1/notices/{first}",
        world.senior,
        {"respond_by": "2026-09-30"},
        headers={"If-Match": "9"},
    )
    assert stale.status_code == 409, stale.text
    fresh = await world.call(
        "PATCH",
        f"/v1/notices/{first}",
        world.senior,
        {"respond_by": "2026-09-30"},
        headers={"If-Match": "1"},
    )
    assert fresh.status_code == 200, fresh.text
    assert cast(Json, fresh.json())["respond_by_source"] == "corrected"
