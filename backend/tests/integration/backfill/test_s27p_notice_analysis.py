"""N-04-T11 (TASK-3360; DEC-2359): Run writes a running version, the workflow's step the ready one.

Real units of work and the real system context: a stubbed test would miss a missing audit record,
a refused `Ref` or a verifier that refuses the platform. The step is called directly, as the
activity calls it; Temporal itself is not started here.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.notices import analysis

from .tb_support import Books, Json
from .test_n04t06_notices_core import _notice, world

pytestmark = pytest.mark.asyncio

_ = world
_N: Final = "/v1/notices"


async def _items(books: Books, notice: uuid.UUID, amount: str) -> None:
    """Seeded as code's form map would: the HTTP route needs a real citation first."""
    await books.seed.run(
        "INSERT INTO notice_proposed_items (tenant_id, work_item_id, kind, line_key, label, "
        "amount_irs, origin, recorded_actor_kind) "
        "VALUES ($1, $2, 'line_change', 'interest', 'Interest', $3, 'code_map', 'system')",
        books.tenant_id,
        notice,
        Decimal(amount),
    )


async def _run(books: Books, notice: uuid.UUID) -> Json:
    response = await books.call(
        "POST",
        f"{_N}/{notice}/analysis/run",
        books.senior,
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 202, response.text
    return cast(Json, response.json())


async def test_ac_run_is_running_until_the_step_writes_ready_and_a_repeat_reuses(
    world: Books,
) -> None:
    forget_flags()
    notice = await _notice(world, "CP2000-S27P-A", "2026-10-01")
    await _items(world, notice, "3532.00")
    first = await _run(world, notice)
    assert first["status"] == "running"
    again = await _run(world, notice)
    assert (again["version"], again["reused"]) == (first["version"], True)
    shown = await world.call("GET", f"{_N}/{notice}/analysis", world.senior)
    assert shown.status_code == 200, shown.text
    assert cast(Json, shown.json())["status"] == "running"
    assert "initiator" not in str(shown.json())

    done = await analysis.complete_run(world.tenant_id, notice, int(cast(int, first["version"])))
    assert done == "ready"
    ready = await world.call("GET", f"{_N}/{notice}/analysis", world.senior)
    assert cast(Json, ready.json())["status"] == "ready"
    third = await _run(world, notice)
    assert (third["status"], third["reused"]) == ("ready", True)


async def test_ac_a_failed_run_stops_spinning_and_a_person_can_run_again(
    world: Books,
) -> None:
    forget_flags()
    notice = await _notice(world, "CP2000-S27P-B", "2026-10-01")
    await _items(world, notice, "100.00")
    first = await _run(world, notice)
    version = int(cast(int, first["version"]))
    assert await analysis.mark_failed(world.tenant_id, notice, version) == "failed"
    assert await analysis.mark_failed(world.tenant_id, notice, version) == "gone"
    shown = await world.call("GET", f"{_N}/{notice}/analysis", world.senior)
    assert cast(Json, shown.json())["status"] == "failed"
    second = await _run(world, notice)
    assert second["status"] == "running"
    assert int(cast(int, second["version"])) > version
