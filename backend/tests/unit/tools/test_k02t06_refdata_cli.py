"""K-02-T06 (TASK-2308; SPEC-500 AC-35 to AC-38): the reference-set operator CLI.

The row's acceptance: the founder who drafted a version cannot publish it, formula cells are read
as cached values only, and the diff lists every changed row. No database: the two-person refusal
is the CLI's own check before the definer's (0400 refuses it again).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from openpyxl import Workbook

from abacus_tools import refdata
from abacus_tools.local import db_guard


def test_ac36_formula_cells_are_read_as_cached_values_only(tmp_path: Path) -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["date", "name", "jurisdiction"])
    sheet.append(["2026-01-01", '=HYPERLINK("http://x","New Year")', "US"])
    path = tmp_path / "holidays.xlsx"
    book.save(path)  # openpyxl saves no cached value for a formula it wrote
    payload, problems = refdata.payload_from("legal_holidays", path)
    assert problems == []
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert rows[0] == {"date": "2026-01-01", "jurisdiction": "US"}  # no value, never evaluated


def test_ac36_a_csv_is_rows_by_header_and_problems_name_cells_not_contents(
    tmp_path: Path,
) -> None:
    path = tmp_path / "t.csv"
    path.write_text("form,payment_year,threshold_usd\n1099-NEC,2026,600\n,,\n")
    payload, problems = refdata.payload_from("information_return_thresholds", path)
    assert (
        problems == []
        and payload["rows"] == [{"form": "1099-NEC", "payment_year": 2026, "threshold_usd": 600}]
    ) or payload["rows"] == [{"form": "1099-NEC", "payment_year": "2026", "threshold_usd": "600"}]
    bad = tmp_path / "b.csv"
    bad.write_text("form,,form\nx,y,z\n")
    _, found = refdata.payload_from("form_8879_set", bad)
    assert {p.code for p in found} >= {"header_missing", "header_duplicate"}
    assert all("x" not in str(p) for p in found)


def test_ac37_the_diff_lists_every_changed_row() -> None:
    current = [
        {"form": "1065", "fye_rule": "dec", "original": "03-15"},
        {"form": "1120S", "fye_rule": "dec", "original": "03-15"},
        {"form": "990", "fye_rule": "dec", "original": "05-15"},
    ]
    draft = [
        {"form": "1065", "fye_rule": "dec", "original": "03-16"},  # changed
        {"form": "1120S", "fye_rule": "dec", "original": "03-15"},  # same
        {"form": "1041", "fye_rule": "dec", "original": "04-15"},  # added
    ]
    found = refdata.diff("due_date_rules", current, draft)
    assert [r["form"] for r in found.added] == ["1041"]
    assert [r["form"] for r in found.removed] == ["990"]
    assert [(a["original"], b["original"]) for a, b in found.changed] == [("03-15", "03-16")]
    assert len(found.lines()) == 4 and not found.empty
    assert refdata.diff("due_date_rules", current, current).empty


async def test_ac35_the_drafter_never_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Conn:
        async def fetchval(self, sql: str, *args: object) -> str:
            return "ayush"

        async def execute(self, sql: str, *args: object) -> None:
            raise AssertionError("published by the drafter")

        async def close(self) -> None:
            return None

    async def connect(dsn: str) -> Conn:
        return Conn()

    monkeypatch.setattr(refdata, "connect", connect)
    monkeypatch.setattr(refdata, "_owner_dsn", lambda: "postgresql://local")
    args = argparse.Namespace(version="v", approver="ayush", reason="r")
    with pytest.raises(refdata.Refused, match="approver_is_drafter"):
        await refdata.publish(args)
    two = argparse.Namespace(version="v", operator="a", approver="a", reason="r")
    with pytest.raises(refdata.Refused, match="approver_is_operator"):
        await refdata.withdraw(two)


def test_ac38_nothing_runs_beside_a_hosted_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_guard, "lock_holder", lambda: "held: deploy-staging (deploy)")
    with pytest.raises(refdata.Refused, match="deploy lock"):
        refdata.guard()
    monkeypatch.setattr(db_guard, "lock_holder", lambda: None)
    monkeypatch.setattr(db_guard, "violations", lambda: ["ABACUS_MIGRATIONS_DATABASE_URL"])
    monkeypatch.delenv("ABACUS_OPS_TASK", raising=False)
    with pytest.raises(refdata.Refused, match="hosted database"):
        refdata.guard()
    monkeypatch.setenv("ABACUS_OPS_TASK", "1")
    refdata.guard()  # the ops task itself runs against its own environment


def test_ac38_main_refuses_with_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_guard, "lock_holder", lambda: "held: x")
    assert refdata.main(["publish", "--version", "v", "--approver", "a", "--reason", "r"]) == 2
