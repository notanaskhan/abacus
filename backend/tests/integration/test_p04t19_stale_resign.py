"""P-04-T19 acceptance (TASK-1301; ADR-160 clause 3; DEC-84; SHL-12 e).

"Changing a cell on a signed workpaper shows later levels as Changed after sign-off without
updating any sign-off row, and an unconfirmed member is refused with independence_pending."
"""

from __future__ import annotations

import json
import uuid
from typing import cast

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import detect_stale
from abacus.modules.workpapers.service import CellEdit, create_workpaper, set_cells

from .test_p04t18_sign_off_service import World, engines, person_ctx, world

__all__ = ["engines", "world"]

ROWS = (
    "SELECT id, level, content_hash, signed_by, created_at FROM sign_offs "
    "WHERE target_id = $1 ORDER BY created_at, id"
)


async def _paper(world: World) -> tuple[uuid.UUID, str]:
    ctx = person_ctx(world["marcus"])
    paper = await create_workpaper(ctx, world.team.engagement, "C-1", "Cash lead", "Cash")
    await set_cells(ctx, world.team.engagement, paper, [CellEdit("C14", "2190", ())])
    found = await world.ladder("hannah", "workpaper", paper)
    assert found.status_code == 200, found.text
    return paper, cast(str, found.json()["target"]["content_hash"])


async def _changes(world: World) -> list[OutboxEvent]:
    rows = await world.seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'workpaper.content_changed' ORDER BY seq",
        world.team.tenant,
    )
    return [
        OutboxEvent(r["id"], r["tenant_id"], r["event_type"], json.loads(r["payload"]))
        for r in rows
    ]


async def test_ac_a_changed_cell_shows_later_levels_changed_without_updating_a_row(
    world: World,
) -> None:
    paper, seen = await _paper(world)
    assert (await world.sign("marcus", "workpaper", paper, "L1_preparer", seen)).status_code == 201
    assert (await world.sign("hannah", "workpaper", paper, "L2_reviewer", seen)).status_code == 201
    before = await world.seed.rows(ROWS, paper)

    await set_cells(
        person_ctx(world["marcus"]), world.team.engagement, paper, [CellEdit("C14", "2310", ())]
    )
    ladder = (await world.ladder("hannah", "workpaper", paper)).json()
    now_hash = ladder["target"]["content_hash"]
    assert now_hash != seen
    stale = {lv["level"]: lv["latest"]["stale"] for lv in ladder["levels"] if lv["latest"]}
    assert stale == {"L1_preparer": True, "L2_reviewer": True}
    assert "sign_off.resign.L2_reviewer" in ladder["allowed_actions"]
    assert await world.seed.rows(ROWS, paper) == before  # no row updated, none added

    # The detector tells each signer once, however often the change event is delivered.
    changes = await _changes(world)
    assert changes
    assert await detect_stale(changes[-1]) == 2
    assert await detect_stale(changes[-1]) == 0
    told = await world.seed.rows(
        "SELECT payload->>'signed_by' AS who, payload->>'level' AS level FROM outbox "
        "WHERE tenant_id = $1 AND event_type = 'sign_off.went_stale' ORDER BY 2",
        world.team.tenant,
    )
    assert [(r["who"], r["level"]) for r in told] == [
        (str(world["marcus"].user_id), "1"),
        (str(world["hannah"].user_id), "2"),
    ]
    assert await world.seed.rows(ROWS, paper) == before

    # Re-signing writes new rows; the old ones stay as they were.
    assert (await world.sign("hannah", "workpaper", paper, "L2_reviewer", now_hash)).json()[
        "detail"
    ] == "not_prepared"
    assert (
        await world.sign("marcus", "workpaper", paper, "L1_preparer", now_hash)
    ).status_code == 201
    resigned = await world.sign("hannah", "workpaper", paper, "L2_reviewer", now_hash)
    assert resigned.status_code == 201, resigned.text
    after = await world.seed.rows(ROWS, paper)
    assert after[: len(before)] == before and len(after) == len(before) + 2
    ladder = (await world.ladder("hannah", "workpaper", paper)).json()
    assert not any(lv["latest"]["stale"] for lv in ladder["levels"] if lv["latest"])


async def test_ac_an_unconfirmed_member_is_refused_with_independence_pending(
    world: World,
) -> None:
    paper, seen = await _paper(world)
    assert (await world.sign("marcus", "workpaper", paper, "L1_preparer", seen)).status_code == 201
    await world.seed.run(
        "UPDATE independence_confirmations SET status = 'declined' "
        "WHERE engagement_id = $1 AND user_id = $2",
        world.team.engagement,
        world["hannah"].user_id,
    )
    found = await world.sign("hannah", "workpaper", paper, "L2_reviewer", seen)
    assert (found.status_code, found.json()["detail"]) == (409, "independence_pending")
    sheet = await world.ladder("kevin", "workpaper", paper)
    assert sheet.status_code == 200


async def test_a_partner_who_has_not_concluded_g2_blocks_signing_on_an_attest_client(
    world: World,
) -> None:
    """Stricter on attest clients (R-SO-5): the G2 gate (the partner's conclusion) too."""
    paper, seen = await _paper(world)
    client = await world.seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.team.engagement
    )
    tenant = await world.seed.value(
        "SELECT tenant_id FROM engagements WHERE id = $1", world.team.engagement
    )
    await world.seed.withdraw_conclusion(cast(uuid.UUID, tenant), world.team.engagement)
    await world.seed.run("UPDATE clients SET is_attest_client = true WHERE id = $1", client)
    found = await world.sign("marcus", "workpaper", paper, "L1_preparer", seen)
    assert (found.status_code, found.json()["detail"]) == (409, "independence_pending")
    await world.seed.run("UPDATE clients SET is_attest_client = false WHERE id = $1", client)
    found = await world.sign("marcus", "workpaper", paper, "L1_preparer", seen)
    assert found.status_code == 201, found.text
