"""C-02-T20 (TASK-8709; DEC-5706): CLS-11's words for the connection's health (a forced 401 reads
Needs reauth), the tiles from the posting log (7 posted, 1 proposed, closing date Jul 31), and a
deterministic CSV."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.integrations import ledger_console as lc

CT = datetime(2026, 8, 11, 10, 0).astimezone()


def _row(code: str, status: str, n: int, failures: int = 0, resolved: int = 0) -> lc.LogRow:
    return lc.LogRow(
        uuid4(), code, code[:7], status, n, n, "47901", "47906", resolved, failures, CT, None
    )


def test_ac_a_forced_401_reads_needs_reauth() -> None:
    assert lc.health_of("active", None) == "connected"
    assert lc.health_of("needs_attention", "token_expired") == "needs_reauth"
    assert lc.health_of("needs_attention", "rate_limited") == "needs_attention"
    assert lc.health_of("revoked", None) == "disconnected"


def test_ac_tiles_read_7_posted_1_proposed_and_jul_31() -> None:
    facts = lc.PostingFacts(
        (_row("2026-07-A", "posted", 7, failures=1, resolved=1),),
        1,
        lc.ClosingDate(date(2026, 7, 31), None, CT),
    )
    tiles = lc._tiles(facts)  # pyright: ignore[reportPrivateUsage] -- the rule under test
    assert tiles == {
        "posted": 7,
        "proposed": 1,
        "failed_post": 0,
        "resolved_failures": 1,
        "closing_date": date(2026, 7, 31),
    }


def test_ac_the_csv_is_deterministic_and_carries_no_ids() -> None:
    rows = [_row("2026-07-A", "posted", 6, 1, 1), _row("2026-06-A", "posted", 5)]
    once, again = lc.posting_log_csv(rows), lc.posting_log_csv(rows)
    assert once == again
    lines = once.decode().splitlines()
    assert lines[0] == ",".join(lc.CSV_COLUMNS)
    assert lines[1].startswith("2026-07-A,2026-07,posted,6,6,47901,47906,1")
    assert all(str(r.batch_id) not in once.decode() for r in rows)


def test_ac_a_provider_reference_never_reaches_the_csv_as_a_formula() -> None:
    hostile = lc.LogRow(
        uuid4(), "2026-07-B", "2026-07", "posted", 1, 1, "=HYPERLINK(1)", "@SUM(1)", 0, 0, CT, None
    )
    line = lc.posting_log_csv([hostile]).decode().splitlines()[1]
    assert ",'=HYPERLINK(1),'@SUM(1)," in line


async def test_ac_the_drawer_reads_one_batch_and_hides_an_unknown_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity, batch = uuid4(), uuid4()
    row = lc.LogRow(
        batch, "2026-07-A", "2026-07", "posted", 6, 6, "47901", "47906", 1, 1, CT, None
    )

    async def entity_of(_t: object, b: object) -> object:
        return entity if b == batch else None

    async def log(_ctx: object, e: object, **_k: object) -> list[lc.LogRow]:
        assert e == entity  # authorised through the console's own read (walls: 404)
        return [row]

    monkeypatch.setattr(lc, "_batch_entities", [entity_of])
    monkeypatch.setattr(lc, "posting_log", log)
    ctx = SimpleNamespace(tenant=None)
    assert await lc.posting_batch(ctx, batch) == row  # type: ignore[arg-type]  # a stand-in
    with pytest.raises(NotFound):
        await lc.posting_batch(ctx, uuid4())  # type: ignore[arg-type]  # a stand-in
