"""T-05-T11 (TASK-6813; ADR-078 as amended; SPEC-651 AC-14.2; DEC-3410): Ridgeline's and
Harborview's TY2025 goldens. Row acceptance: "Every figure in section 1 of the spec is an
exact-Decimal golden case, and the Schedule L conflict is encoded as DF-34 decided it."

The figures are the blueprint's and the screen specs' (`ridgeline_ty2025.yaml`), transcribed
before the engines were read; the engines that exist (TB pipeline, allocation) are run against
them, and every other case foots in exact Decimal until its engine lands.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from abacus.modules.tax.compute.entity.allocation import allocate_item, segments
from abacus.modules.tax.compute.entity.tb_pipeline import TbAccount, run

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "ridgeline_ty2025.yaml").read_text(encoding="utf-8")
)
D = Decimal


def _accounts() -> list[TbAccount]:
    return [
        TbAccount(n, n, sec, line, D(utb), aje=D(aje), tje=D(tje), py=D(py), capital_role=role)
        for n, sec, line, py, utb, aje, tje, role in GOLDEN["tb_pipeline"]["accounts"]
    ]


def test_every_case_names_its_source_parameters_and_reviewer() -> None:
    assert GOLDEN["parameter_set"] == "ty2025"
    assert GOLDEN["reviewed_by"].startswith("pending: tax CPA")
    for key in (
        "tb_pipeline",
        "schedule_l",
        "allocation",
        "schedule_k",
        "capital_m2",
        "harborview_waterfall",
    ):
        assert GOLDEN[key]["source"], key


def test_the_tb_pipeline_meets_its_golden() -> None:
    case = GOLDEN["tb_pipeline"]
    result = run(_accounts())
    want = {k: D(v) for k, v in case["expect"].items()}
    assert result.total_assets("atb") == want["atb_total_assets"]
    assert -result.totals["atb"]["liabilities"] == want["atb_total_liabilities"]
    assert -result.totals["atb"]["equity"] + result.book_income == want["capital_and_income"]
    assert result.book_income == want["book_income"]
    assert result.totals["atb"]["income"] == want["atb_income"]
    assert result.totals["atb"]["deductions"] == want["atb_deductions"]
    assert result.by_form_line["8825 Rents"] == want["rents_8825_ttb"]
    assert all(t.difference == D(case["columns_foot_to"]) for t in result.column_foots.values())


def test_schedule_l_follows_df_34() -> None:
    lines = {n: line for n, _, line, *_ in GOLDEN["tb_pipeline"]["accounts"]}
    for account, line in GOLDEN["schedule_l"]["decided"].items():
        assert lines[account] == line, account
    assert lines["2000"] != lines["2050"]  # 2000 split from 2050


def test_the_allocation_meets_its_golden() -> None:
    case = GOLDEN["allocation"]
    start, end = (date.fromisoformat(d) for d in case["year"])
    segs = segments(
        start,
        end,
        [
            (None, {k: D(v) for k, v in case["opening"].items()}),
            (date.fromisoformat(case["transfer"]), {k: D(v) for k, v in case["after"].items()}),
        ],
        case["convention"],
    )
    result = allocate_item(
        D(case["total"]),
        segs,
        method=case["method"],
        convention=case["convention"],
        segment_amounts=[D(a) for a in case["segment_amounts"]],
    )
    first, second = result.shares
    assert first == {k: D(v) for k, v in case["expect"]["period_1"].items()}
    assert second == {k: D(v) for k, v in case["expect"]["period_2"].items()}
    assert result.totals == {k: D(v) for k, v in case["expect"]["totals"].items()}


def test_schedule_k_crossfoots() -> None:
    case = GOLDEN["schedule_k"]
    for row in case["crossfoot"]:
        total = sum((D(p) / 100 * D(a) for p, a in row["parts"]), D(0))
        assert total == D(row["expect"]), row["name"]
    assert D(case["lines"]["line_2_net_rental"]) / 2 == D("615800")


def test_capital_and_m2() -> None:
    case = GOLDEN["capital_m2"]
    t = case["transfer"]
    assert D(t["capital"]) * D(t["points"][0]) / D(t["points"][1]) == D(t["expect"])
    b = case["section_743b"]
    assert D(b["price"]) - D(b["transferred_tax_capital"]) == D(b["expect"])
    assert sum(D(p) for p in case["tax_exempt_fix"]["parts"]) == D(
        case["tax_exempt_fix"]["expect"]
    )
    assert sum(D(p) for p in case["jonah_row_12"]["parts"]) == D(case["jonah_row_12"]["expect"])
    assert D(case["ending_after_fix"]) == D(GOLDEN["tb_pipeline"]["expect"]["capital_and_income"])


def test_the_harborview_waterfall_foots() -> None:
    case = GOLDEN["harborview_waterfall"]
    for key in ("rungs", "targets", "plugs"):
        assert sum(D(p) for p in case[key]["parts"]) == D(case[key]["expect"]), key
    catch_up = case["gp_catch_up"]
    assert D(catch_up["gp"]) / D(catch_up["base"]) * 100 == D(catch_up["expect_percent"])
