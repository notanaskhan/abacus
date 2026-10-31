# ac-test-author: ayushkbhatia
"""T-02-T29 (ADR-078; TASK-2527; SPEC-502 AC-8, AC-10, AC-11, AC-19, AC-20; T-02 §3.1 to §3.4):
the independent suite for T-02's tax-return backend (T-02-T07, T09, T10, T13, T18), written from
the SPEC and the epic rather than the code. "Tests pass on main and fail if a guarded transition
succeeds without its gate."

- The guard table (T07): a person may ask only for the table's requestable moves; the gated
  moves (final approval, the envelope, the transmission, the acks, prepared) are refused over
  HTTP and at the service, the system never takes a person's decision, the agent never moves a
  return, and a refusal changes nothing.
- Wall-safe tiles and totals (T09): a walled return is absent from rows, tiles, office totals and
  the record, with no hidden count; the tiles foot to the total and open plus done.
- Due-date pins (T10): a correction moves an open return's dates, never a filed or accepted one,
  and keeps their pinned versions.
- Overview figures only from approved imports (T13): a pro forma alone shows no figure.
- Consent-gated suggestions (T18): without the household's consents, no suggestion and no model
  call.

T-02-T09's practice-board seed serves the returns (Feld in review, Ridgeline preparing, Copperleaf
filed, Granite Peak accepted, Lakeshore not started).
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import cast

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import due_dates
from abacus.modules.tax.api import TransitionRefused, apply_transition

from . import test_t02t09_practice_board as t02t09
from .agent_tests.support import Seeder
from .test_t02t09_practice_board import DEMO, Board, Json
from .test_t02t10_due_date_pinning import _dates, _publish, _return
from .test_t02t13_return_overview import manager_on
from .test_t02t18_intake import _binder, _waiting

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

GATED = ("final_approved", "envelope_sent", "transmission_recorded", "ack_accepted", "prepared")


async def _state(b: Board, item: uuid.UUID) -> tuple[str, int, int]:
    status = cast(
        str, await b.seed.value("SELECT status FROM tax_returns WHERE work_item_id = $1", item)
    )
    version = cast(
        int,
        await b.seed.value("SELECT row_version FROM tax_returns WHERE work_item_id = $1", item),
    )
    events = cast(
        int,
        await b.seed.value(
            "SELECT count(*) FROM tax_return_status_events WHERE work_item_id = $1", item
        ),
    )
    return status, version, events


# --- the guard table ----------------------------------------------------------------------------


@pytest.mark.parametrize("event", GATED)
async def test_a_gated_move_is_refused_over_http_and_nothing_changes(
    board: Board, event: str
) -> None:
    feld = board.returns["Feld Household 1040"]
    samuel = await manager_on(board, feld)
    before = await _state(board, feld)
    with frozen(DEMO):
        refused = await _as(samuel)(
            "POST",
            f"/v1/tax-returns/{feld}/transitions",
            json={"event": event, "seen_version": before[1]},
        )
    assert refused.status_code in (403, 409, 422), refused.text
    assert await _state(board, feld) == before


async def test_the_service_refuses_a_move_without_its_gate(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    _status, version, _events = await _state(board, feld)
    system = TenantContext(board.tenant, "system", "tax:planted")
    with pytest.raises(Forbidden):  # the system never takes a person's decision
        await apply_transition(system, feld, "final_approved", seen_version=version)
    agent = TenantContext(board.tenant, "agent", f"agent:x:{uuid.uuid4()}")
    for event in ("start_review", "issues_raised", "content_changed"):
        with pytest.raises(Forbidden):  # the agent never moves a return
            await apply_transition(agent, feld, event, seen_version=version)
    person = TenantContext(board.tenant, "human", str(board.partner))
    for event in ("envelope_sent", "transmission_recorded", "ack_accepted"):
        with pytest.raises(TransitionRefused):  # not from In review: the table holds no move
            await apply_transition(person, feld, event, seen_version=version)
    assert (await _state(board, feld))[0] == "in_review"


# --- wall-safe tiles, totals and rows -----------------------------------------------------------


async def test_the_tiles_foot_and_a_walled_return_leaves_no_trace(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    admin = await board.person("Margaret Okonkwo", "firm_admin")
    walled = await board.person("Lena Park", "firm_admin")
    await board.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        board.tenant,
        walled.user_id,
        board.clients["Feld Household"],
        board.partner,
    )
    with frozen(DEMO):
        full = cast(Json, (await _as(admin)("GET", "/v1/tax-returns/summary")).json())
        seen = cast(Json, (await _as(walled)("GET", "/v1/tax-returns/summary")).json())
        rows = cast(Json, (await _as(walled)("GET", "/v1/tax-returns")).json())
        record = await _as(walled)("GET", f"/v1/tax-returns/{feld}")
    for s in (full, seen):
        tiles = [cast(int, t["count"]) for t in cast(list[Json], s["tiles"])]
        assert sum(tiles) == s["total"] == cast(int, s["open"]) + cast(int, s["done"])
        offices = cast(list[Json], s["offices"])
        assert sum(cast(int, o["open"]) + cast(int, o["done"]) for o in offices) == s["total"]
    assert cast(int, full["total"]) - cast(int, seen["total"]) == 1
    assert cast(int, full["open"]) - cast(int, seen["open"]) == 1  # Feld is in review: open
    assert "Feld Household" not in {r["client_name"] for r in cast(list[Json], rows["items"])}
    assert rows["total"] == seen["total"]
    assert record.status_code == 404
    assert "hidden" not in json.dumps(seen) and "hidden" not in json.dumps(rows)


# --- due-date pins ------------------------------------------------------------------------------


async def test_a_correction_moves_open_returns_never_filed_or_accepted_ones(seed: Seeder) -> None:
    s = seed
    await _publish(s, 15, effective=date(2033, 1, 1), tax_year=2033)
    tenant = await s.firm()
    ctx = TenantContext(tenant, "system", "test:t02t29")
    items = {
        status: await _return(s, tenant, "preparing", extended=True, tax_year=2033)
        for status in ("open", "filed", "accepted")
    }
    for item in items.values():
        async with uow(ctx) as tx:
            pinned = await due_dates.pin(tx.session, ctx, item)
            assert pinned is not None
            due_dates.record_pinned(tx, item, pinned)
    for status in ("filed", "accepted"):
        await s.run(
            "UPDATE tax_returns SET status = $2 WHERE work_item_id = $1", items[status], status
        )
    before = {k: await _dates(s, v) for k, v in items.items()}
    await _publish(s, 18, effective=date(2033, 6, 1), tax_year=2033)
    await due_dates.recompute_unfiled(ctx)
    after = {k: await _dates(s, v) for k, v in items.items()}
    for kept in ("filed", "accepted"):
        assert after[kept]["original_due_on"] == before[kept]["original_due_on"]
        assert after[kept]["due_rule_version_ids"] == before[kept]["due_rule_version_ids"]
    assert after["open"]["original_due_on"] != before["open"]["original_due_on"]
    assert after["open"]["due_rule_version_ids"] != before["open"]["due_rule_version_ids"]


# --- overview figures only from approved imports -----------------------------------------------


async def test_a_pro_forma_alone_shows_no_figure(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    await board.seed.run(
        "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
        "lines, approved_at) VALUES ($1, $2, '2025I:FeldJ:V1', 'pro_forma', $3::jsonb, "
        "'2026-02-03T00:00:00Z')",
        board.tenant,
        feld,
        json.dumps([{"line_key": "refund", "label": "Refund", "amount": "999"}]),
    )
    samuel = await manager_on(board, feld)
    with frozen(DEMO):
        found = await _as(samuel)("GET", f"/v1/tax-returns/{feld}/overview")
    assert found.status_code == 200, found.text
    body = cast(Json, found.json())
    assert body["engine_summary"] == []
    assert "999" not in json.dumps(body["engine_summary"])


# --- consent-gated suggestions ------------------------------------------------------------------


async def test_without_both_consents_no_suggestion_and_no_model_call(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    await _binder(board, feld)
    kevin = await manager_on(board, feld)
    client = cast(
        uuid.UUID, await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld)
    )
    await _waiting(board, client, "Feld_W2_2025.pdf", 2025)
    before = await board.seed.value(
        "SELECT count(*) FROM usage_records WHERE tenant_id = $1", board.tenant
    )
    with frozen(DEMO):
        found = await _as(kevin)("GET", f"/v1/tax-returns/{feld}/intake")
    assert found.status_code == 200, found.text
    body = cast(Json, found.json())
    assert body["suggestions"] != "available"
    assert all(w["suggestion"] is None for w in cast(list[Json], body["waiting"]))
    after = await board.seed.value(
        "SELECT count(*) FROM usage_records WHERE tenant_id = $1", board.tenant
    )
    assert after == before
