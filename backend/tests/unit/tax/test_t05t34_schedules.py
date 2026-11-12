"""T-05-T34 (TASK-7624; DEC-4619): schedule read models over the workbook cells.

The Item L pill reads off 6,200 before the fix and tie after it; Schedule K ties per line when
the partners' shares sum to the total; every total is the server's.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.tax import entity_schedules as es

D = Decimal
RETURN = uuid.UUID("00000000-0000-4000-8000-000000000065")
A = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
B = uuid.UUID("00000000-0000-4000-8000-0000000000b2")


def _v(**cells: object) -> dict[str, dict[str, object]]:
    return {k.replace("_", "!", 1): {"t": "n", "v": v} for k, v in cells.items()}


# Two partners, ending capital 6,866,200; the drafted M-2 ends at 6,860,000 (off 6,200).
VALUES = _v(
    **{
        "05_A2": "Pell Street II LLC",
        "05_B2": "4000000",
        "05_C2": "100000",
        "05_D2": "250000",
        "05_E2": "1316200",
        "05_F2": "5166200",
        "05_A3": "Jonah Feld",
        "05_B3": "1500000",
        "05_C3": "0",
        "05_D3": "100000",
        "05_E3": "300000",
        "05_F3": "1700000",
        "07_B1": "5500000",
        "07_B2": "100000",
        "07_B3": "1610000",
        "07_B6": "350000",
        "07_B9": "6860000",
        "06_A2": "1",
        "06_B2": "Ordinary business income (loss)",
        "06_C2": "1000",
        "09_B2": "750",
        "09_C2": "250",
        "06_A3": "2",
        "06_B3": "Net rental real estate income (loss)",
        "06_C3": "1001",
        "09_B3": "750",
        "09_C3": "250",
        "08_A2": "Ridgeline Plaza",
        "08_B2": "2",
        "08_C2": "601",
        "08_A3": "Ridgeline Commons",
        "08_B3": "2",
        "08_C3": "400",
    }
)


def test_ac_item_l_reads_off_6200_before_the_fix_and_tie_after() -> None:
    rows = es.capital_rows(VALUES, RETURN, {})
    before = es.item_l(rows, es.m2_as_drafted(VALUES))
    assert before.tie == "off" and before.difference == D("6200")
    assert before.capital_ending == D("6866200") and before.m2_ending == D("6860000")
    after = es.item_l(rows, es.m2_with_fix(VALUES, rows))
    assert after.tie == "tie" and after.difference == D(0)


def test_ac_m2_with_fix_foots_and_drafted_shows_its_gap() -> None:
    rows = es.capital_rows(VALUES, RETURN, {})
    drafted = es.m2_as_drafted(VALUES)
    assert drafted.lines[4][2] == D("7210000")  # line 5 = 1 + 2 + 3 + 4
    assert drafted.tie == "tie"  # 7,210,000 - 350,000 = 6,860,000
    fixed = es.m2_with_fix(VALUES, rows)
    assert fixed.ending == D("6866200") and fixed.tie == "tie"
    assert [n for n, _l, _a in fixed.lines] == list(range(1, 10))


def test_ac_capital_rows_roll_forward_and_server_totals() -> None:
    rows = es.capital_rows(VALUES, RETURN, {"Jonah Feld": B})
    assert [r.name for r in rows] == ["Pell Street II LLC", "Jonah Feld"]
    assert rows[1].partner_id == B
    assert rows[0].partner_id == es.partner_id_for(RETURN, "Pell Street II LLC", {})
    assert es.capital_tie(rows) == "tie"
    totals = es.capital_totals(rows)
    assert totals.ending == D("6866200") and totals.distributions == D("350000")


def test_ac_capital_tie_is_off_when_a_row_does_not_roll_forward() -> None:
    broken = {**VALUES, "05!F3": {"t": "n", "v": "1700001"}}
    assert es.capital_tie(es.capital_rows(broken, RETURN, {})) == "off"


def test_ac_schedule_k_ties_per_line_on_the_partner_split() -> None:
    lines = es.schedule_k(VALUES, [A, B], "federal")
    assert [k.line for k in lines] == ["1", "2"]
    assert lines[0].tie == "tie" and dict(lines[0].by_partner) == {A: D(750), B: D(250)}
    assert lines[1].tie == "off"  # 1,001 against 1,000 allocated


def test_ac_state_view_is_empty_until_apportionment_writes_column_d() -> None:
    assert es.schedule_k(VALUES, [A, B], "state") == []
    with_state = {**VALUES, "06!D2": {"t": "n", "v": "400"}}
    state = es.schedule_k(with_state, [A, B], "state")
    assert [(k.line, k.total, k.by_partner) for k in state] == [("1", D(400), ())]


def test_ac_form_8825_breakdown_by_property() -> None:
    assert es.breakdown(VALUES, "2") == [
        ("Ridgeline Plaza", D(601)),
        ("Ridgeline Commons", D(400)),
    ]
    assert es.breakdown(VALUES, "1") == []
