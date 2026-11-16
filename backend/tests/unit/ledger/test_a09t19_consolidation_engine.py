"""A-09-T19 (red): the consolidation engine on Harlow & Pike FY2026 (SPEC-658; AUD-33; the seed
figures of `apps/web/src/fixtures/seed/group-audit.ts`). Level 1 totals 50,760,000 with every
column netting to zero, Level 2 totals 39,760,000 with net income 4,760,000, and two xlsx renders
are byte-identical."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.ledger.compute import consolidation as c
from abacus.modules.ledger.consolidation_xlsx import render_levels

ENTITIES = ("holdings", "operating", "manufacturing", "distribution", "real_estate")
TB = [
    ("Cash", "assets", [2_600_000, 0, 1_800_000, 1_400_000, 300_000]),
    ("Accounts receivable", "assets", [0, 0, 7_200_000, 4_100_000, 0]),
    ("Intercompany receivable", "assets", [0, 0, 2_400_000, 0, 0]),
    ("Inventory", "assets", [0, 0, 9_600_000, 6_300_000, 0]),
    ("Property, plant & equipment, net", "assets", [0, 0, 8_400_000, 1_200_000, 8_100_000]),
    ("Investment in Operating Co.", "assets", [20_000_000, 0, 0, 0, 0]),
    ("Investment in Real Estate", "assets", [6_000_000, 0, 0, 0, 0]),
    ("Investment in Manufacturing", "assets", [0, 14_000_000, 0, 0, 0]),
    ("Investment in Distribution", "assets", [0, 6_000_000, 0, 0, 0]),
    ("Accounts payable", "liabilities_equity", [0, 0, -4_600_000, -2_300_000, 0]),
    ("Intercompany payable", "liabilities_equity", [0, 0, 0, -2_400_000, 0]),
    ("Accrued liabilities", "liabilities_equity", [-400_000, 0, -1_500_000, -600_000, 0]),
    ("Mortgage note", "liabilities_equity", [0, 0, 0, 0, -1_200_000]),
    ("Term loan", "liabilities_equity", [-9_000_000, 0, 0, 0, 0]),
    (
        "Common stock / contributed capital",
        "liabilities_equity",
        [-12_000_000, -20_000_000, -14_000_000, -6_000_000, -6_000_000],
    ),
    (
        "Retained earnings 1/1/2026",
        "liabilities_equity",
        [-9_360_000, 0, -5_900_000, -100_000, -300_000],
    ),
    ("Net sales — third party", "income", [0, 0, -42_000_000, -31_000_000, 0]),
    ("Net sales — intercompany", "income", [0, 0, -18_000_000, 0, 0]),
    ("Rental income — intercompany", "income", [0, 0, 0, 0, -1_200_000]),
    ("Cost of goods sold", "income", [0, 0, 45_600_000, 24_800_000, 0]),
    ("Rent expense — intercompany", "income", [0, 0, 1_200_000, 0, 0]),
    ("Operating expenses", "income", [1_800_000, 0, 9_800_000, 4_600_000, 260_000]),
    ("Interest expense", "income", [360_000, 0, 0, 0, 40_000]),
]
ELIMS = [
    (
        "E1a",
        2,
        [
            ("Common stock / contributed capital", 20_000_000, 0),
            ("Investment in Manufacturing", 0, 14_000_000),
            ("Investment in Distribution", 0, 6_000_000),
        ],
    ),
    (
        "E1b",
        1,
        [
            ("Common stock / contributed capital", 26_000_000, 0),
            ("Investment in Operating Co.", 0, 20_000_000),
            ("Investment in Real Estate", 0, 6_000_000),
        ],
    ),
    (
        "E2",
        2,
        [("Net sales — intercompany", 18_000_000, 0), ("Cost of goods sold", 0, 18_000_000)],
    ),
    ("E3", 2, [("Cost of goods sold", 240_000, 0), ("Inventory", 0, 240_000)]),
    ("E4", 2, [("Intercompany payable", 2_400_000, 0), ("Intercompany receivable", 0, 2_400_000)]),
    (
        "E5",
        1,
        [
            ("Rental income — intercompany", 1_200_000, 0),
            ("Rent expense — intercompany", 0, 1_200_000),
        ],
    ),
]
LEVEL2 = ("operating", "manufacturing", "distribution")


def _tbs() -> dict[str, list[c.TbLine]]:
    return {
        e: [c.TbLine(cap, sec, D(amounts[i])) for cap, sec, amounts in TB]  # type: ignore[arg-type] -- the section literals
        for i, e in enumerate(ENTITIES)
    }


def _elims() -> list[c.Elimination]:
    return [
        c.Elimination(
            code, level, tuple(c.EliminationLine(cap, D(d), D(cr)) for cap, d, cr in lines)
        )
        for code, level, lines in ELIMS
    ]


def test_ac_level_1_totals_50_760_000_and_every_column_nets_to_zero() -> None:
    level = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims())
    assert level.total_assets == D("50760000.00")
    assert level.ties and all(v == 0 for v in level.column_totals.values())
    assert level.eliminations_posted == 6


def test_ac_level_2_totals_39_760_000_with_net_income_4_760_000() -> None:
    level = c.consolidate(_tbs(), LEVEL2, level=2, eliminations=_elims())
    assert level.total_assets == D("39760000.00")
    assert level.net_income == D("4760000.00")
    assert level.eliminations_posted == 4
    assert level.ties


def test_consolidated_equals_the_entities_less_the_eliminations() -> None:
    level = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims())
    for row in level.rows:
        entities = sum((row.amount(e) for e in ENTITIES), D(0))
        assert row.amount(c.CONSOLIDATED) == entities + row.amount(c.ELIMINATIONS)
    inventory = next(r for r in level.rows if r.caption == "Inventory")
    assert next(x for x in inventory.cells if x.column == c.ELIMINATIONS).elimination_codes == (
        "E3",
    )


def test_ac_two_xlsx_renders_are_byte_identical() -> None:
    levels = [
        c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims()),
        c.consolidate(_tbs(), LEVEL2, level=2, eliminations=_elims()),
    ]
    names = {"holdings": "Holdings", "operating": "Operating Co."}
    assert render_levels(levels, names) == render_levels(levels, names)


def test_an_unbalanced_elimination_or_missing_tb_is_refused() -> None:
    bad = [c.Elimination("X", 1, (c.EliminationLine("Cash", D(1), D(0)),))]
    with pytest.raises(c.ConsolidationInvalid):
        c.consolidate(_tbs(), ENTITIES, level=1, eliminations=bad)
    with pytest.raises(c.ConsolidationInvalid):
        c.consolidate(_tbs(), ("nowhere",), level=2, eliminations=[])


def test_attribution_and_hash_are_stable() -> None:
    a = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims())
    b = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=list(reversed(_elims())))
    assert a.inputs_hash == b.inputs_hash
    assert sum(a.attribution.values()) == pytest.approx(D(100), abs=D("0.05"))
