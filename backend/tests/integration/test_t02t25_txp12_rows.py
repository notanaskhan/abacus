"""T-02-T25 (TASK-2530; T-02 §3.6, DV-10; ADR-031; DEC-88) against Postgres: the additive
TXP-12 row fields behind the screen's fixture-to-live swap.

- A row carries its period, its recipient's ownership note and locality, its delivery contact,
  its hand-offs (the target named only to a reader of it) and a pending details change.
- A row offers the recipient's own returns for the year as share targets (DEC-88).
- No list row carries a TIN; the package detail carries it masked, last four only (ADR-031).
- The release check names the "Deliverable ready" version a release must cite.

The Ridgeline drafts and the Feld share are T-02-T20's (`test_t02t20_k1_packages`).
"""

from __future__ import annotations

import json
import uuid
from typing import cast

from abacus.kernel.clock import frozen
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import k1_packages

from . import test_t02t09_practice_board as t02t09
from . import test_t02t20_k1_packages as t02t20
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
_drafts = t02t20._ridgeline_with_drafts  # pyright: ignore[reportPrivateUsage] -- T-02-T20's set
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board


async def _flag(b: Board) -> None:
    await b.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.k1_release', 'true', 'test-seed', 'T-02-T25')",
        b.tenant,
    )


async def _rows(b: Board, who: AuthContext, ridgeline: uuid.UUID) -> list[Json]:
    with frozen(DEMO):
        listed = await _as(who)("GET", f"/v1/tax-returns/{ridgeline}/k1-packages")
    assert listed.status_code == 200, listed.text
    return cast(list[Json], cast(Json, listed.json())["items"])


async def test_rows_carry_period_note_locality_and_handoffs_but_no_tin(board: Board) -> None:
    ridgeline, feld, samuel = await _drafts(board)
    await _flag(board)
    await board.seed.run(
        "UPDATE k1_recipients SET ownership_note = '35% → 30% at 6/30', "
        'address = \'{"city": "Brooklyn", "state": "NY"}\'::jsonb '
        "WHERE work_item_id = $1 AND engine_ref = 'P01'",
        ridgeline,
    )
    await board.seed.run(
        "UPDATE k1_packages SET period_start = '2025-07-01', period_end = '2025-12-31' "
        "WHERE work_item_id = $1 AND recipient_id = (SELECT id FROM k1_recipients "
        "WHERE work_item_id = $1 AND engine_ref = 'P02')",
        ridgeline,
    )
    rows = await _rows(board, samuel, ridgeline)
    await k1_packages.share_internal(
        samuel, ridgeline, [uuid.UUID(cast(str, rows[0]["id"]))], [feld]
    )
    jonah, meera = await _rows(board, samuel, ridgeline)
    assert jonah["recipient_name"] == "Jonah Feld"
    assert jonah["ownership_note"] == "35% → 30% at 6/30"
    assert jonah["locality"] == "Brooklyn, NY"
    assert (jonah["period_start"], meera["period_start"], meera["period_end"]) == (
        None,
        "2025-07-01",
        "2025-12-31",
    )
    handoffs = cast(list[Json], jonah["handoffs"])
    assert [(h["target_return_id"], h["target_form"], h["status"]) for h in handoffs] == [
        (str(feld), "1040", "draft_shared")
    ]
    assert meera["handoffs"] == []
    assert meera["details_change"] is None
    # ADR-031: no TIN on a list row, masked or not.
    for row in (jonah, meera):
        assert not any("tin" in key for key in row), row.keys()
        assert "1111" not in json.dumps(row) and "2222" not in json.dumps(row)


async def test_a_handoff_target_is_named_only_to_a_reader_of_it(board: Board) -> None:
    ridgeline, feld, samuel = await _drafts(board)
    await _flag(board)
    rows = await _rows(board, samuel, ridgeline)
    await k1_packages.share_internal(
        samuel, ridgeline, [uuid.UUID(cast(str, rows[0]["id"]))], [feld]
    )
    other = await board.person("Olivia Brandt", None)
    await board.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) SELECT $1, "
        "engagement_id, $3, 'manager' FROM tax_returns WHERE work_item_id = $2",
        board.tenant,
        ridgeline,
        other.user_id,
    )
    seen = await _rows(board, other, ridgeline)
    handoff = cast(list[Json], seen[0]["handoffs"])[0]
    assert handoff["target_return_id"] is None
    assert handoff["target_name"] == "Another return"
    assert handoff["target_form"] is None
    assert "Feld" not in json.dumps(seen)
    assert seen[0]["related_returns"] == []


async def test_a_row_offers_the_recipients_own_return_as_a_share_target(board: Board) -> None:
    ridgeline, feld, samuel = await _drafts(board)
    await _flag(board)
    await board.seed.run(
        "UPDATE k1_recipients SET client_entity_id = (SELECT e.id FROM client_entities e "
        "JOIN work_items w ON w.client_id = e.client_id WHERE w.id = $2 LIMIT 1) "
        "WHERE work_item_id = $1 AND engine_ref = 'P01'",
        ridgeline,
        feld,
    )
    jonah, meera = await _rows(board, samuel, ridgeline)
    related = cast(list[Json], jonah["related_returns"])
    assert [(r["return_id"], r["form"]) for r in related] == [(str(feld), "1040")]
    assert meera["related_returns"] == []


async def test_the_detail_carries_the_tin_masked_and_the_check_names_the_template(
    board: Board,
) -> None:
    ridgeline, _feld, samuel = await _drafts(board)
    await _flag(board)
    rows = await _rows(board, samuel, ridgeline)
    with frozen(DEMO):
        detail = await _as(samuel)("GET", f"/v1/k1-packages/{rows[0]['id']}")
        check = await _as(samuel)("GET", f"/v1/tax-returns/{ridgeline}/k1-packages/release-check")
    assert detail.status_code == 200, detail.text
    assert cast(Json, detail.json())["tin"] == {"kind": "ssn", "last4": "1111"}
    assert check.status_code == 200, check.text
    body = cast(Json, check.json())
    assert "email_template_version_id" in body
    assert body["eligible"] is False and "not_final_approved" in cast(list[str], body["failing"])


async def test_a_delivery_contact_is_named_only_for_a_client_the_reader_sees(board: Board) -> None:
    ridgeline, _feld, samuel = await _drafts(board)
    await _flag(board)
    issuing = await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", ridgeline)
    other = await board.seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Walled Partner LLC') RETURNING id",
        board.tenant,
    )
    for ref, client, name in (("P01", issuing, "Owen Calder"), ("P02", other, "Hidden Person")):
        contact = await board.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, "
            "portal_state) VALUES ($1, $2, $3, 'k1_recipient', 'not_invited') RETURNING id",
            board.tenant,
            client,
            name,
        )
        await board.seed.run(
            "UPDATE k1_packages SET delivery_contact_id = $3 WHERE work_item_id = $1 AND "
            "recipient_id = (SELECT id FROM k1_recipients WHERE work_item_id = $1 "
            "AND engine_ref = $2)",
            ridgeline,
            ref,
            contact,
        )
    jonah, meera = await _rows(board, samuel, ridgeline)
    assert jonah["delivery_contact_name"] == "Owen Calder"
    assert meera["delivery_contact_name"] is None
    assert "Hidden Person" not in json.dumps([jonah, meera])
