"""T-05-T40 (TASK-7702; T-05 §2.3, F2; DEC-4703, DEC-4704): the workbook run's part-2 handlers.

Row acceptance: "A run without a depreciation import stops that step at Needs attention with an
issue, and an imported report fills 02 Fixed Assets with cited cells." Plus: the report is parsed
as hostile input; the §706(d) convention is a run question with options from code when no person
settled it; state amounts are code's (federal times apportionment).
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.agents.api import RunStepFacts
from abacus.modules.tax import run_steps
from abacus.modules.tax.entity_run_plan import (
    QUESTION_706D,
    convention_question,
    plan_steps,
    selected,
)
from abacus.modules.tax.workbook_imports import ImportInvalid, parse, writes_for
from abacus.modules.tax.workbook_service import CellWrite

RETURN = uuid.uuid4()
D = Decimal
REPORT = (
    "Asset Description,Placed in service,Cost basis,Method,Life,Current depreciation,"
    "Bonus,Section 179\n"
    "Elm Street building,2019-04-01,1200000,SL,39,30769,0,0\n"
    "HVAC,06/15/2025,84000,MACRS,15,2800,42000,0\n"
)


def _facts(step: str) -> RunStepFacts:
    return RunStepFacts(uuid.uuid4(), uuid.uuid4(), step, 3, {"return_id": str(RETURN)})


class _Agent:
    tenant: Any = object()  # Any: a stand-in tenant


# --- the hostile parse ---------------------------------------------------------------------------


def test_an_imported_report_fills_02_with_cited_cells() -> None:
    parsed = parse("depreciation_register", REPORT.encode())
    cells = {w.address: w for w in writes_for(parsed)}
    assert cells["02!A2"].value == "Elm Street building"
    assert cells["02!C2"].value == D(1200000)
    assert cells["02!B3"].value == "2025-06-15"
    assert cells["02!G3"].value == D(42000)
    assert cells["02!A2"].source == "engine_import"
    note = cells["02!F3"].citation_note or ""
    assert note.startswith("Depreciation report import ") and note.endswith(" row 3")
    assert parsed.sha256[:12] in note
    assert cells["02!F4"].formula == "=SUM(F2:F3)" and cells["02!F4"].value == D(33569)


def test_a_formula_in_the_report_stays_text_and_is_never_evaluated() -> None:
    hostile = REPORT + '"=HYPERLINK(""http://x"")",2025-01-01,1,SL,5,1,0,0\n'
    cells = {w.address: w for w in writes_for(parse("depreciation_register", hostile.encode()))}
    assert cells["02!A4"].value == '=HYPERLINK("http://x")'
    assert cells["02!A4"].formula is None  # a client string is text in the cell store


def test_problems_name_sheet_row_column_and_code_never_the_cell() -> None:
    bad = "Asset,Cost,Depreciation\nTruck,ten thousand,1000\n,,\nVan,5000,\n"
    with pytest.raises(ImportInvalid) as caught:
        parse("depreciation_register", bad.encode())
    problems = caught.value.facts["problems"]
    assert {"sheet": "csv", "row": 2, "column": "B", "code": "not_a_number"} in problems
    assert {"sheet": "csv", "row": 4, "column": "C", "code": "required"} in problems
    assert all("ten thousand" not in str(p) for p in problems)


def test_a_missing_required_column_and_size_limits_are_refused() -> None:
    with pytest.raises(ImportInvalid) as missing:
        parse("depreciation_register", b"Asset,Cost\nTruck,1\n")
    assert missing.value.facts["problems"][0]["code"] == "missing_column:current"
    with pytest.raises(ImportInvalid) as large:
        parse("depreciation_register", b"x" * (5 * 1024 * 1024 + 1))
    assert large.value.facts["problems"][0]["code"] == "too_large"


def test_an_xlsx_report_reads_cached_values_only() -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["State", "Apportionment %", "PTET paid"])
    sheet.append(["NY", 62.5, 48000])
    sheet.append(["NJ", "=1+1", 0])  # a formula with no cached value is not a number
    data = io.BytesIO()
    book.save(data)
    with pytest.raises(ImportInvalid) as caught:
        parse("state_apportionment", data.getvalue())
    assert caught.value.facts["problems"] == [
        {"sheet": "Sheet", "row": 3, "column": "B", "code": "required"}
    ]


def test_state_rows_land_in_08_f_to_h() -> None:
    parsed = parse("state_apportionment", b"State,Apportionment,PTET\nNY,62.5,48000\n")
    cells = {w.address: w.value for w in writes_for(parsed)}
    assert cells == {"08!F2": "NY", "08!G2": D("62.5"), "08!H2": D(48000)}


# --- the handlers ---------------------------------------------------------------------------


@pytest.fixture
def io_stub(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:  # Any: recorded calls
    seen: dict[str, Any] = {"writes": [], "issues": [], "values": {}}  # Any: a test double

    async def write(
        agent: object, facts: object, return_id: object, writes: list[CellWrite]
    ) -> int:
        seen["writes"].extend(writes)
        return len(writes)

    async def current(
        tenant: object, target: str, target_id: object
    ) -> dict[str, Any]:  # Any: a test double
        return seen["values"]

    async def issue(ctx: object, **kwargs: object) -> uuid.UUID:
        seen["issues"].append(kwargs)
        return uuid.uuid4()

    from abacus.modules.review import api as review_api

    monkeypatch.setattr(run_steps, "_write", write)
    monkeypatch.setattr(run_steps, "current_values", current)
    monkeypatch.setattr(review_api, "create_issue", issue)
    return seen


def test_no_depreciation_import_stops_at_needs_attention_with_one_issue(
    io_stub: dict[str, Any],  # Any: a test double
) -> None:
    result = asyncio.run(
        run_steps.depreciation_register(_Agent(), _facts("depreciation_register"))  # type: ignore[arg-type] -- a test double stands in for the typed object
    )
    assert (result.state, result.error_code) == ("failed", "import_required")
    (issue,) = io_stub["issues"]
    assert issue["source_ref"] == "run_step:depreciation_register:import_required"
    assert issue["blocks"] == ("final_approval",) and issue["work_item_id"] == RETURN


def test_an_imported_report_lets_the_step_succeed(
    io_stub: dict[str, Any],  # Any: a test double
) -> None:  # Any: a test double
    io_stub["values"] = {
        w.address.replace("02!", "02!"): {"v": None if w.value is None else str(w.value)}
        for w in writes_for(parse("depreciation_register", REPORT.encode()))
    }
    result = asyncio.run(
        run_steps.depreciation_register(_Agent(), _facts("depreciation_register"))  # type: ignore[arg-type] -- a test double stands in for the typed object
    )
    assert (result.state, result.records_read) == ("succeeded", 2)
    bonus = asyncio.run(run_steps.bonus_eligibility(_Agent(), _facts("bonus_eligibility")))  # type: ignore[arg-type] -- a test double stands in for the typed object
    assert (bonus.state, bonus.records_read) == ("succeeded", 1)


def test_apportionment_writes_06_d_as_federal_times_the_percentage(
    io_stub: dict[str, Any],  # Any: a test double
) -> None:
    io_stub["values"] = {
        "06!A2": {"v": "1"},
        "06!C2": {"v": "1256200"},
        "06!A3": {"v": "2"},
        "06!C3": {"v": "96400"},
        "08!F2": {"v": "NY"},
        "08!G2": {"v": "62.5"},
        "08!H2": {"v": "48000"},
    }
    result = asyncio.run(run_steps.apportionment_ptet(_Agent(), _facts("apportionment_ptet")))  # type: ignore[arg-type] -- a test double stands in for the typed object
    assert result.state == "succeeded"
    written = {w.address: (w.value, w.formula) for w in io_stub["writes"]}
    assert written["06!D2"] == (D(785125), "=ROUND(C2*'08'!G2/100,0)")
    assert written["06!D3"] == (D(60250), "=ROUND(C3*'08'!G2/100,0)")


def test_no_state_schedule_is_needs_attention(
    io_stub: dict[str, Any],  # Any: a test double
) -> None:  # Any: a test double
    result = asyncio.run(run_steps.state_k1s_k3s(_Agent(), _facts("state_k1s_k3s")))  # type: ignore[arg-type] -- a test double stands in for the typed object
    assert (result.state, result.error_code) == ("failed", "import_required")


def test_every_part_two_step_has_a_real_handler() -> None:
    assert set(run_steps.PART_TWO_HANDLERS) == set(run_steps.PART_TWO)


# --- the §706(d) convention question -------------------------------------------------------------


def test_the_convention_is_a_run_question_with_options_from_code() -> None:
    question = convention_question([date(2025, 6, 18)], None)
    assert [o["key"] for o in question.options] == ["calendar_day", "semi_monthly", "monthly"]
    assert question.options[2]["title"] == "Monthly (books close Jun 30, 2025)"
    assert question.recommended == "calendar_day" and "§1.706-4" in question.reason
    plan = plan_steps(selected("all", ()), consent=True, convention=question)
    by_key = {s.key: s for s in plan}
    asked = by_key[QUESTION_706D]
    assert asked.kind == "question" and asked.arguments["recommended"] == "calendar_day"
    interim = by_key["interim_closing_706d"]
    assert QUESTION_706D in interim.depends_on and interim.level > asked.level
    assert by_key["capital_m2"].level > interim.level  # levels stay dependency depth


def test_the_readers_convention_is_recommended_and_a_settled_one_asks_nothing() -> None:
    assert convention_question([date(2025, 6, 30)], "monthly").recommended == "monthly"
    plan = plan_steps(selected("all", ()), consent=True, convention=None)
    assert QUESTION_706D not in {s.key for s in plan}
