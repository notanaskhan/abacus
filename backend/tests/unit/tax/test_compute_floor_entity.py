"""The compute floor (ADR-079; `compute: 100`) for T-05's entity engines: every refusal of the
allocation engine, a tie or foot with a missing side, and a capital roll-forward that does not
tie. Each refusal names its code and never a partner's figure."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax.compute.entity.allocation import (
    AllocationInvalid,
    allocate_item,
    segments,
)
from abacus.modules.tax.compute.entity.tb_pipeline import TbAccount, run
from abacus.modules.tax.compute.entity.ties import foot, tie

D = Decimal
Y0, Y1 = date(2025, 1, 1), date(2025, 12, 31)
HALF = {"A": D(50), "B": D(50)}


def _code(excinfo: pytest.ExceptionInfo[AllocationInvalid]) -> str:
    return excinfo.value.code


def test_segments_need_the_opening_interests_first() -> None:
    with pytest.raises(AllocationInvalid) as e:
        segments(Y0, Y1, [(date(2025, 6, 30), HALF)], "monthly")
    assert _code(e) == "opening_interests_required"


def test_a_transfer_outside_the_year_is_refused() -> None:
    with pytest.raises(AllocationInvalid) as e:
        segments(Y0, Y1, [(None, HALF), (date(2026, 2, 1), HALF)], "monthly")
    assert _code(e) == "transfer_out_of_year"


@pytest.mark.parametrize(
    ("total", "kwargs", "code"),
    [
        (D(100), {"method": "proration", "convention": "fortnightly"}, "unknown_convention"),
        (D("100.50"), {"method": "proration", "convention": "calendar_day"}, "whole_dollars_only"),
        (
            D(100),
            {"method": "interim_closing", "convention": "monthly"},
            "segment_amounts_required",
        ),
        (
            D(100),
            {"method": "interim_closing", "convention": "monthly", "segment_amounts": [D(40)]},
            "segments_do_not_sum_to_the_year",
        ),
    ],
)
def test_allocate_item_refuses(total: Decimal, kwargs: dict[str, object], code: str) -> None:
    segs = segments(Y0, Y1, [(None, HALF)], "monthly")
    with pytest.raises(AllocationInvalid) as e:
        allocate_item(total, segs, **kwargs)  # type: ignore[arg-type]  # the refusal under test
    assert _code(e) == code


def test_a_tie_or_foot_with_a_missing_side_is_missing() -> None:
    assert tie(None, D(1)).state == "missing"
    assert tie(D(1), None).difference is None
    assert foot([D(1), None], D(1)).state == "missing"
    assert foot([D(1)], None).state == "missing"


def test_capital_that_does_not_roll_forward_blocks_the_return() -> None:
    accounts = [
        TbAccount("1000", "Cash", "assets", "L1", D(100)),
        TbAccount("3000", "Capital (no M-2 role)", "equity", "L21", D(-100)),
    ]
    result = run(accounts)
    assert "capital" in result.blocked_by


# --- Schedule K (T-05-T34 engine): refusals, payments by partner and state cells -------------

from abacus.modules.tax.compute.entity.schedule_k import (  # noqa: E402  # grouped by engine
    KLine,
    KPartner,
    ScheduleKInvalid,
    StateCell,
    schedule_k,
)

_P = (D(50), D(50), D(50))


def _partners(*keys: str, ending: tuple[Decimal, Decimal, Decimal] = _P) -> list[KPartner]:
    return [KPartner(k, "individual", _P, ending) for k in keys]


def _k(lines: list[KLine], **kwargs: object) -> object:
    segs = segments(Y0, Y1, [(None, HALF)], "monthly")
    args: dict[str, object] = {"partners": _partners("A", "B"), "liabilities": {}}
    args.update(kwargs)
    return schedule_k(
        args["partners"],  # type: ignore[arg-type]  # the test's own inputs
        segs,
        lines,
        method="interim_closing",
        convention="monthly",
        liabilities=args["liabilities"],  # type: ignore[arg-type]  # the test's own inputs
        state_cells=args.get("state_cells", ()),  # type: ignore[arg-type]  # the test's own inputs
    )


def _k_code(lines: list[KLine], **kwargs: object) -> str:
    with pytest.raises(ScheduleKInvalid) as e:
        _k(lines, **kwargs)
    return e.value.code


ORDINARY = KLine("1", D(1000), segment_amounts=(D(1000),))


def test_schedule_k_refusals() -> None:
    assert _k_code([KLine("1", D("10.5"), segment_amounts=(D("10.5"),))]) == "whole_dollars_only"
    assert _k_code([ORDINARY], partners=[]) == "partners_required"
    assert _k_code([ORDINARY], partners=_partners("A", "A")) == "partners_required"
    assert _k_code([ORDINARY, ORDINARY]) == "duplicate_line"
    assert _k_code([ORDINARY], liabilities={"guaranteed": D(10)}) == "unknown_liability_kind"
    assert _k_code([ORDINARY], liabilities={"recourse": D("1.5")}) == "whole_dollars_only"
    lopsided = _partners("A", "B", ending=(D(60), D(50), D(50)))
    assert _k_code([ORDINARY], partners=lopsided) == "ending_profit_must_sum_to_100"


def test_payments_by_partner_are_kept_as_paid_and_must_foot() -> None:
    paid = KLine("4a", D(300), by_partner={"A": D(300)})
    result = _k([ORDINARY, paid])
    assert {k.partner: k.lines["4a"] for k in result.k1s} == {"A": D(300), "B": D(0)}  # type: ignore[attr-defined]  # ScheduleK
    stranger = KLine("4a", D(300), by_partner={"Z": D(300)})
    assert _k_code([ORDINARY, stranger]) == "unknown_partner"
    short = KLine("4a", D(300), by_partner={"A": D(200)})
    assert _k_code([ORDINARY, short]) == "line_4a_does_not_foot"


def test_state_cells_roll_up_per_state_and_name_known_partners() -> None:
    cells = (
        StateCell("NY", "A", D(100), "imported"),
        StateCell("NY", "A", D(50), "keyed"),
        StateCell("NJ", "B", D(25), "keyed"),
    )
    result = _k([ORDINARY], state_cells=cells)
    assert result.states == {"NY": {"A": D(150)}, "NJ": {"B": D(25)}}  # type: ignore[attr-defined]  # ScheduleK
    stray = (StateCell("NY", "Z", D(1), "keyed"),)
    assert _k_code([ORDINARY], state_cells=stray) == "unknown_partner"


# --- the targeted waterfall (T-05 allocation structures): refusals and every rung's path ------

from abacus.modules.tax.compute.entity.waterfall import (  # noqa: E402  # grouped by engine
    Rung,
    WaterfallInvalid,
    WaterfallPartner,
    run_waterfall,
)

GP = WaterfallPartner("G", "gp", D(100))
LP = WaterfallPartner("L", "lp", D(900))
ROC = Rung(1, "return_of_capital")


def _w_code(partners: list[WaterfallPartner], rungs: list[Rung], income: Decimal) -> str:
    with pytest.raises(WaterfallInvalid) as e:
        run_waterfall(partners, rungs, income)
    return e.value.code


def test_waterfall_refuses_bad_partners_and_amounts() -> None:
    residual = [Rung(1, "residual")]
    assert _w_code([], residual, D(0)) == "partners_required"
    assert _w_code([GP, GP], residual, D(0)) == "duplicate_partner"
    assert _w_code([LP], residual, D(0)) == "general_partner_required"
    assert _w_code([WaterfallPartner("G", "gp", D("10.5")), LP], residual, D(0)) == (
        "whole_dollars_only"
    )
    assert _w_code([WaterfallPartner("G", "gp", D(-1)), LP], residual, D(0)) == "negative_capital"
    assert _w_code([GP, LP], residual, D("1.5")) == "whole_dollars_only"
    assert _w_code([GP, LP], [], D(0)) == "rung_priorities_must_be_unique"
    assert _w_code([GP, LP], [ROC, Rung(1, "residual")], D(0)) == "rung_priorities_must_be_unique"
    assert _w_code([GP, LP], residual, D(-2000)) == "negative_distributable"


def test_waterfall_refuses_bad_rung_parameters() -> None:
    assert _w_code([GP, LP], [ROC, Rung(2, "preferred_return")], D(500)) == "rate_required"
    assert _w_code([GP, LP], [ROC, Rung(2, "preferred_return", {"rate": 150})], D(500)) == (
        "rate_out_of_range"
    )
    catch_up = Rung(2, "catch_up", {"target": 20, "share": 10})
    assert _w_code([GP, LP], [ROC, catch_up], D(500)) == "catch_up_share_must_exceed_target"


def test_a_catch_up_below_full_share_pays_the_limited_partners_too() -> None:
    rungs = [
        ROC,
        Rung(2, "preferred_return", {"rate": 8}),
        Rung(3, "catch_up", {"target": 20, "share": 80}),
        Rung(4, "promote", {"gp": 20}),
    ]
    result = run_waterfall([GP, LP], rungs, D(1000))
    catch_up = next(r for r in result.rungs if r.rule_type == "catch_up")
    assert catch_up.shares.get("L", D(0)) > 0
    assert sum((r.amount for r in result.rungs), D(0)) == D(2000)


def test_a_residual_split_pays_by_its_weights_or_by_capital() -> None:
    by_split = run_waterfall([GP, LP], [ROC, Rung(2, "residual", {"split": {"G": 20, "L": 80}})],
                             D(1000))  # fmt: skip
    assert by_split.rungs[-1].shares == {"G": D(200), "L": D(800)}
    by_capital = run_waterfall([GP, LP], [ROC, Rung(2, "straight_pct")], D(1000))
    assert by_capital.rungs[-1].shares == {"G": D(100), "L": D(900)}
    stray = [ROC, Rung(2, "residual", {"split": {"Z": 100}})]
    assert _w_code([GP, LP], stray, D(1000)) == "unknown_partner_in_split"


def test_income_left_after_the_last_rung_is_refused() -> None:
    assert _w_code([GP, LP], [ROC], D(100)) == "undistributed_remainder"
