"""T-02-T11 (TASK-2215; SPEC-502 AC-15 to AC-17): the TY2025 tax slice's golden footings, without
a database, and its parity with the fixture seed.

224 returns on 214 engagements (10 with two returns); open 79 by status 2 / 8 / 9 / 17 / 15 /
11 / 7 / 10 and done 145 (6 filed, 139 accepted); 161 extended; offices 98 / 64 / 62. The named
rows are the fixture seed's, field for field, so `make seed-demo` and fixture mode show the same
board (the seed file is parsed here; the TS foot tests hold the seed to the same numbers).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale import tax_board
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import RETURNS, TAX_ENGAGEMENTS
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

SEED = Path(__file__).resolve().parents[4] / "apps/web/src/fixtures/seed/tax/tax-returns.ts"
OPEN = tax_board.OPEN_STATUSES


def test_ac15_returns_engagements_and_offices_foot() -> None:
    assert len(tax_board.BOARD) == len(RETURNS) == 224
    assert len(TAX_ENGAGEMENTS) == 214
    assert sum(1 for e in TAX_ENGAGEMENTS if len(e.returns) == 2) == 10
    assert Counter(r.office for r in tax_board.BOARD) == {
        "Chicago": 98,
        "Denver": 64,
        "New York": 62,
    }


def test_ac15_statuses_and_extensions_foot() -> None:
    counts = Counter(r.status for r in tax_board.BOARD)
    assert dict(counts) == {k: v for k, v in tax_board.STATUS_COUNTS.items() if v}
    assert sum(1 for r in tax_board.BOARD if r.status in OPEN) == 79
    assert sum(1 for r in tax_board.BOARD if r.status not in OPEN) == 145
    assert sum(1 for r in tax_board.BOARD if r.extended) == 161
    # §9.5: every open return is extended, save a named row the handoff draws otherwise
    # (Lakeshore Literacy Alliance's 990, gathering, due Nov 16).
    unextended = {name for name, row in tax_board.NAMED.items() if not row.extended}
    assert all(
        r.extended for r in tax_board.BOARD if r.status in OPEN and r.client not in unextended
    )


def test_ac15_the_named_rows_hold() -> None:
    ridgeline = tax_board.BOARD_BY_LABEL["ridgeline-property-partners-lp"]
    assert (ridgeline.status, ridgeline.level, ridgeline.sync.code, ridgeline.issues) == (
        "in_review",
        "Partner",
        "not_yet_exported",
        11,
    )
    assert (ridgeline.preparer, ridgeline.reviewer, ridgeline.form) == ("OB", "SI", "1065")
    assert ridgeline.due == date(2026, 9, 15) and ridgeline.extended
    lakeshore = next(r for r in tax_board.BOARD if r.client == "Lakeshore Literacy Alliance")
    assert lakeshore.due == date(2026, 11, 16)


def test_ac16_every_in_review_return_has_a_level_and_sync_follows_status() -> None:
    for row in tax_board.BOARD:
        if row.status == "in_review":
            assert row.level is not None, row.label
        if row.status not in OPEN:
            assert row.sync.code == "synced" and row.sync.day is not None, row.label


def test_ac17_the_named_rows_are_the_fixture_seeds_field_for_field() -> None:
    text = SEED.read_text()
    block = text[text.index("const NAMED: Readonly<Record<string, Named>> = {") :]
    block = block[: block.index("\n};")]
    entries = dict(re.findall(r'\n  "([^"]+)": \{(.*?)\},', block, re.S))
    assert set(entries) == set(tax_board.NAMED)
    for name, body in entries.items():
        named = tax_board.NAMED[name]
        flat = " ".join(body.split())
        assert f'team: "{named.team}"' in flat, name
        assert f'status: "{named.status}"' in flat, name
        for field, value in (("office", named.office), ("level", named.level), ("due", named.due)):
            if value is not None:
                assert f'{field}: "{value}"' in flat, (name, field)


def test_ac17_the_slice_needs_the_binders_and_emits_one_event_per_return() -> None:
    assert tax_board.NEEDS == ("binders",)
    events = slice_events(tax_board.SLICE)
    assert len(events) == 224
    assert {e.kind for e in events} == {"tax.return_board_set"}
