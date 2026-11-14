"""W-02-T20 (TASK-7938; W-02 §3.8 AC-R2 to AC-R4; DEC-4933): run artifacts and drill.

Row acceptance: "The preview matches the stored workbook, a download writes one audit event, and
the Action required 11 drill lists 11 returns with no model call."

Unit level: the preview reads the stored bytes' values (the O4 Summary tab, the stage-definition
footnote), the drill title and the tax source's rows (visible returns of the workbook's year in
that status, TAX-02 links), the slot's refusals, and that the module imports no gateway. The
routes against a database are W-02-T21's journey and the end-pass integration run.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.modules.agents import run_artifacts

SUMMARY = Sheet(
    "Summary",
    [
        ["Office", "Gather", "Prepare", "Review", "Deliver", "Total"],
        ["Chicago", 4, 11, 12, 7, 34],
        ["Denver", 3, 8, 7, 5, 23],
        ["New York", 3, 7, 7, 5, 22],
        ["Total", 10, 26, 26, 17, 79],
        [None, None, None, None, None, None],
        ["Gather = Not started 2 + Gathering 8 · Prepare = Preparing 9 + Prepared 17 · "
         "Review = In review 15 + Action required 11 · Deliver = Ready 7 + Awaiting signature 10"],
    ],
)  # fmt: skip
TABS = [SUMMARY, *(Sheet(n, [["Return", "Status"]]) for n in ("Gather", "Prepare", "Review",
                                                               "Deliver"))]  # fmt: skip


def test_ac_r2_the_preview_is_the_stored_summary_with_its_footnote() -> None:
    names, chosen, columns, rows, footnote = run_artifacts.preview_of(workbook(TABS), None)
    assert names == ["Summary", "Gather", "Prepare", "Review", "Deliver"]
    assert chosen == "Summary"
    assert columns == ["Office", "Gather", "Prepare", "Review", "Deliver", "Total"]
    assert [c.value for c in rows[0]] == ["Chicago", "4", "11", "12", "7", "34"]
    assert [c.value for c in rows[-1]] == ["Total", "10", "26", "26", "17", "79"]
    assert all(c.bold for c in rows[-1]) and not any(c.bold for c in rows[0])
    assert footnote is not None and footnote.startswith("Gather = Not started 2")


def test_a_named_tab_is_shown_and_an_unknown_one_falls_back_to_the_first() -> None:
    assert run_artifacts.preview_of(workbook(TABS), "Review")[1] == "Review"
    assert run_artifacts.preview_of(workbook(TABS), "Nope")[1] == "Summary"


def test_the_drill_title_names_the_group_and_its_count() -> None:
    assert run_artifacts.drill_title("Action required", 11) == "Action required 11"


@pytest.mark.asyncio
async def test_ac_r4_the_tax_source_lists_the_visible_returns_in_that_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.tax import board

    def r(status: str) -> object:
        return SimpleNamespace(work_item_id=uuid4(), form="1065", status=status)

    rows = [(r("action_required"), SimpleNamespace(client_name=f"Client {i:02d}"))
            for i in range(11)]  # fmt: skip
    rows += [(r("in_review"), SimpleNamespace(client_name="Other"))]
    years: list[object] = []

    async def fake_board(_ctx: object, year: object) -> object:
        years.append(year)
        return SimpleNamespace(rows=rows)

    monkeypatch.setattr(board, "_board", fake_board)
    ctx: Any = SimpleNamespace()  # Any: a test stand-in
    found = await board.season_group(ctx, "TY2025 Season Progress — by office.xlsx",
                                     "action_required")  # fmt: skip
    assert found is not None
    words, listed = found
    assert words == "Action required" and len(listed) == 11 and years == [2025]
    assert all(x.href == f"/tax-returns/{x.ref_id}" for x in listed)
    assert await board.season_group(SimpleNamespace(), "x", "not_a_status") is None  # type: ignore[arg-type] -- stand-in


@pytest.mark.asyncio
async def test_an_unknown_group_is_refused_without_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = SimpleNamespace(session_id=(sid := uuid4()), name="TY2025.xlsx")

    async def readable(*_: object) -> object:
        return row

    monkeypatch.setattr(run_artifacts, "_readable", readable)
    with pytest.raises(run_artifacts.DrillGroupUnknown):
        await run_artifacts.drill(SimpleNamespace(), sid, uuid4(), "office:chicago", "k")  # type: ignore[arg-type] -- stand-in
    with pytest.raises(run_artifacts.NotFound):
        await run_artifacts.drill(SimpleNamespace(), uuid4(), uuid4(), "status:prepared", "k")  # type: ignore[arg-type] -- stand-in


def test_tax_registers_the_status_source() -> None:
    import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- stand-in

    assert "status" in run_artifacts.drill_sources()


def test_the_artifact_routes_call_no_model() -> None:
    tree = ast.parse(Path(run_artifacts.__file__).read_text(encoding="utf-8"))
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("ai_gateway" in m or "harness" in m for m in modules)


def test_the_download_is_audited_once_with_ids_only() -> None:
    body = Path(run_artifacts.__file__).read_text(encoding="utf-8")
    start = body.index("async def download(")
    chunk = body[start : body.index("return row.name, content", start)]
    assert chunk.count("tx.record(") == 1
    assert "after=Ref(artifact=row.id, sha256=row.sha256)" in chunk


def test_workbench_writes_the_drill_item_not_agents() -> None:
    """OWN-001: the session tables are workbench's; agents lists the group and hands the item to
    the writer workbench registers."""
    # importing workbench's api registers the writer
    import abacus.modules.workbench.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- slot
    from abacus.modules.workbench.run_drill import append_drill

    writers = run_artifacts._WRITER  # pyright: ignore[reportPrivateUsage] -- the slot
    assert writers == [append_drill]
    body = Path(run_artifacts.__file__).read_text(encoding="utf-8")
    assert "session_items" not in body and "workbench_sessions" not in body
