"""T-05-T61 (TASK-7939; T-05 F11; DEC-77; DEC-4934): reconciliation to the engine of record.

Row acceptance: "A seeded one-dollar difference raises one engine_diagnostic issue, and a matching
import reports zero unexplained differences."

Unit level: the workbook's engine-owned figures by code (Schedule K, each partner's K-1 lines,
ending capital, M-2), the comparison with an approved import's figures, one issue per difference
with a figure-free title, and the shadow label.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from abacus.modules.tax import entity_reconciliation as recon

RETURN = uuid4()


def _v(value: object) -> dict[str, object]:
    return {"v": value}


VALUES: dict[str, dict[str, object]] = {
    "06!A2": _v("1"), "06!C2": _v("600000"),
    "09!B1": _v("Meera Shah"), "09!B2": _v("360000"), "09!C1": _v("Daniel Reyes"),
    "09!C2": _v("240000"),
    "05!A2": _v("Meera Shah"), "05!F2": _v("1231600"),
    "07!B1": _v("1000"), "07!B2": _v("500"), "07!B9": _v("1500"),
}  # fmt: skip
KNOWN = {"Meera Shah": uuid4(), "Daniel Reyes": uuid4()}


def _engine(figures: list[recon.Figure], bump: str | None = None) -> dict[str, dict[str, Any]]:
    out = {f.key: {"v": str(f.amount)} for f in figures}
    if bump is not None:
        out[bump] = {"v": str(Decimal(str(out[bump]["v"])) + 1)}
    return out


def test_the_workbook_figures_cover_k_k1s_capital_and_m2() -> None:
    figures = recon.workbook_figures(VALUES, RETURN, KNOWN)
    keys = {f.key for f in figures}
    meera = KNOWN["Meera Shah"]
    assert "schedule_k.1" in keys and f"k1.{meera}.1" in keys
    assert f"capital.{meera}.ending" in keys and "m2.9" in keys
    by_key = {f.key: f.amount for f in figures}
    assert by_key[f"k1.{meera}.1"] == Decimal("360000")
    assert by_key["m2.5"] == Decimal("1500")  # footed by code, not read


def test_a_matching_import_reports_zero_unexplained_differences() -> None:
    figures = recon.workbook_figures(VALUES, RETURN, KNOWN)
    rows = recon.compare(figures, _engine(figures))
    assert rows and recon.differences(rows) == []


def test_a_one_dollar_difference_is_one_row_to_explain() -> None:
    figures = recon.workbook_figures(VALUES, RETURN, KNOWN)
    found = recon.differences(recon.compare(figures, _engine(figures, bump="schedule_k.1")))
    assert [(r.key, r.engine - r.accrued) for r in found] == [("schedule_k.1", Decimal(1))]  # type: ignore[operator]


def test_an_engine_figure_accrued_lacks_needs_explaining() -> None:
    figures = recon.workbook_figures(VALUES, RETURN, KNOWN)
    engine = _engine(figures) | {"k1.stranger.1": {"v": "10"}}
    found = recon.differences(recon.compare(figures, engine))
    assert [r.key for r in found] == ["k1.stranger.1"]


@pytest.mark.asyncio
async def test_each_difference_raises_one_issue_naming_the_line_not_the_figure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    figures = recon.workbook_figures(VALUES, RETURN, KNOWN)
    rows = recon.compare(figures, _engine(figures, bump="schedule_k.1"))
    raised: list[dict[str, Any]] = []

    async def fake_reconcile(*_: object) -> list[recon.ReconRow]:
        return rows

    async def fake_issue(_ctx: object, **kwargs: Any) -> object:
        raised.append(kwargs)
        return uuid4()

    monkeypatch.setattr(recon, "reconcile", fake_reconcile)
    monkeypatch.setattr(recon, "record_engine_issue", fake_issue)
    ctx = type("Ctx", (), {"tenant": None})()
    assert await recon.raise_differences(ctx, RETURN) == 1  # type: ignore[arg-type]
    assert raised[0]["source_ref"] == "recon:schedule_k.1"
    assert raised[0]["title"] == "CCH reconciliation · Schedule K line 1"
    assert "600000" not in raised[0]["title"]


def test_the_shadow_label_is_decided_wording() -> None:
    assert recon.SHADOW_LABEL == "Accrued tie-out (shadow)"
