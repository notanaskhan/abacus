"""T-02-T13 (TASK-2322; T-02 §3.3; DEC-1368) over HTTP against Postgres: "The Feld overview foots
to refund 253 from the approved import and no figure appears for a user without content rights."

The Feld return is seeded as the practice-board test seeds returns (T-02-T09's `Board`), with an
approved CCH import's summary (`final`) and an older pro forma that must never be the estimate.
A security admin reads metadata only: the same overview, with no engine figure in it.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import cast

import pytest

from abacus.kernel.clock import frozen

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
# T-02-T09's fixtures, served here too: the app engine per test, the seeder and the board.
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

LINES = [
    {"line_key": "total_income", "label": "Total income", "amount": "598030"},
    {"line_key": "total_tax", "label": "Total tax", "amount": "123223", "total": "total"},
    {"line_key": "payments", "label": "Total payments", "amount": "123476", "total": "total"},
    {"line_key": "refund", "label": "Refund", "amount": "253", "total": "grand"},
]


async def _summaries(b: Board, item: object) -> None:
    for kind, version, lines, at in (
        (
            "pro_forma",
            "2025I:FeldJ:V1",
            [{"line_key": "agi", "label": "2024 AGI", "amount": "1"}],
            datetime(2026, 2, 3, tzinfo=UTC),
        ),
        ("final", "2025I:FeldJ:V3", LINES, datetime(2026, 9, 10, 15, 0, tzinfo=UTC)),
    ):
        await b.seed.run(
            "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
            "lines, approved_at) VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
            b.tenant,
            item,
            version,
            kind,
            json.dumps(lines),
            at,
        )


async def test_ac_feld_foots_to_253_and_metadata_readers_get_no_figure(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    await _summaries(board, feld)
    samuel = await board.person("Samuel Ito", "firm_manager")
    felix = await board.person("Felix Andersen", "security_admin")
    with frozen(DEMO):
        found = await _as(samuel)("GET", f"/v1/tax-returns/{feld}/overview")
        metadata = await _as(felix)("GET", f"/v1/tax-returns/{feld}/overview")
        record = await _as(samuel)("GET", f"/v1/tax-returns/{feld}")
    assert found.status_code == 200, found.text
    body = cast(Json, found.json())
    assert body["engine_version"] == "2025I:FeldJ:V3"
    lines = {line["line_key"]: line["amount"] for line in cast(list[Json], body["engine_summary"])}
    assert lines["refund"] == "253"
    assert float(cast(str, lines["total_tax"])) + 253 == float(cast(str, lines["payments"]))
    assert body["engine_synced_on"] == date(2026, 9, 10).isoformat()
    assert [p["step"] for p in cast(list[Json], body["pipeline"])] == [
        "gather",
        "prepare",
        "review",
        "deliver",
    ]

    assert metadata.status_code == 200, metadata.text
    blank = cast(Json, metadata.json())
    assert blank["engine_summary"] == [] and blank["engine_version"] is None
    assert blank["ladder"] and blank["pipeline"]

    assert record.status_code == 200, record.text
    assert cast(Json, cast(Json, record.json())["row"])["status"] == "in_review"


@pytest.mark.parametrize("event", ["start_preparation", "start_review"])
async def test_a_person_may_request_only_the_table_s_moves(board: Board, event: str) -> None:
    feld = board.returns["Feld Household 1040"]  # in review: neither move is in the table
    samuel = await board.person("Samuel Ito", "firm_manager")
    version = await board.seed.value(
        "SELECT row_version FROM tax_returns WHERE work_item_id = $1", feld
    )
    with frozen(DEMO):
        refused = await _as(samuel)(
            "POST",
            f"/v1/tax-returns/{feld}/transitions",
            json={"event": event, "seen_version": version},
        )
    assert refused.status_code in (403, 409), refused.text
