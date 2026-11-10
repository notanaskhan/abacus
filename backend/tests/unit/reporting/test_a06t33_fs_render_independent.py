"""A-06-T33 (TASK-6119; ADR-078): independent tests for the FS render and client sends.

Written from the A-06-T29 row, AR-C 70 and R-02's C18 rules, not from the code. Row acceptance:
"Tests fail if a non-approver client principal can approve an FS draft." Covered: the renderer's
fetcher denies everything but its own assets (the FS kind inherits it), the DRAFT mark on drafts
and none on finals, the AR-C 70 legend on a preparation engagement only, the fs_draft decider rule
(owner or approver of record; a contributor, tcwg or K-1 recipient never), and XLSX cells never
starting a formula.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from abacus.kernel.safe_xlsx import safe_text
from abacus.modules.engagements.api import DECIDER_RULES
from abacus.modules.reporting.fs_render import (
    NO_ASSURANCE,
    Heading,
    Line,
    Note,
    compose_body,
)
from abacus.modules.reporting.render.core import mark_for
from abacus.modules.reporting.render.fetcher import ASSET_SCHEME, AssetFetcher

_INVESTMENTS = {2025: Decimal("14895000"), 2024: Decimal("13940000")}
LINES = [
    Line("net_assets", "Investments, at fair value", 1, _INVESTMENTS),
    Line("net_assets", "Notes receivable from participants", 2, {2025: Decimal("312400")}),
]


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/x.png",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "data:image/png;base64,AAAA",
        f"{ASSET_SCHEME}not-registered",
    ],
)
def test_the_fetcher_refuses_everything_but_its_own_assets(url: str) -> None:
    fetcher = AssetFetcher({"logo": b"\x89PNG"})
    with pytest.raises(Exception):  # noqa: B017 -- any refusal fails the render (fail_on_errors)
        fetcher.fetch(url)
    assert fetcher.refused


def test_a_registered_asset_is_served() -> None:
    fetcher = AssetFetcher({"logo": b"\x89PNG"})
    assert fetcher.fetch(f"{ASSET_SCHEME}logo") is not None


def test_a_draft_is_marked_and_a_final_is_not() -> None:
    assert mark_for("draft") == "DRAFT"
    assert mark_for("final") is None
    assert mark_for("sample") == "SAMPLE"


def _texts(blocks: list[object]) -> list[str]:
    dicts = [cast(dict[str, Any], b) for b in blocks if isinstance(b, dict)]  # render blocks
    return [str(d.get("text", "")) for d in dicts]


def test_ar_c_70_legend_only_on_a_preparation_engagement() -> None:
    # LINES are a plan's net assets (ASC 962), so both headings are a plan's
    prepared = compose_body(
        Heading("Granite Peak", date(2025, 12, 31), preparation=True, plan=True), LINES, []
    )
    audited = compose_body(
        Heading("Northwind", date(2025, 12, 31), preparation=False, plan=True), LINES, []
    )
    assert NO_ASSURANCE in _texts(prepared)
    assert NO_ASSURANCE not in _texts(audited)
    assert NO_ASSURANCE == "No assurance is provided."


def test_the_body_carries_code_s_figures_and_no_checklist_or_source() -> None:
    blocks = compose_body(
        Heading(
            "Northwind Robotics 401(k) Plan", date(2025, 12, 31), preparation=False, plan=True
        ),
        LINES,
        [Note(8, "Reconciliation to Form 5500", "Receivables of 48,600 are not on the form.")],
    )
    dicts = [cast(dict[str, Any], b) for b in blocks if isinstance(b, dict)]  # SDK object or JSON
    tables = [t for t in dicts if t.get("type") == "table"]
    assert (
        tables
        and ["Investments, at fair value", "14,895,000.00", "13,940,000.00"] in tables[0]["rows"]
    )
    flat = " ".join(str(b) for b in blocks).lower()
    for banned in ("checklist", "citation", "agent", "materiality", "source"):
        assert banned not in flat, banned


@pytest.mark.parametrize("kind", ["fs_draft"])
def test_only_the_owner_or_approver_of_record_approves_a_draft(kind: str) -> None:
    rule = DECIDER_RULES[kind]  # type: ignore[index]  # test double or SDK shape
    assert rule.any_of == {"owner", "approver_of_record"}
    for outsider in ("contributor", "tcwg", "k1_recipient", "third_party", "delegate"):
        assert outsider not in rule.any_of


@pytest.mark.parametrize("cell", ['=HYPERLINK("x")', "+1+1", "-2", "@SUM(A1)", "\t=1", "\r=1"])
def test_xlsx_text_never_starts_a_formula(cell: str) -> None:
    escaped = safe_text(cell)
    assert not escaped.startswith(("=", "+", "-", "@", "\t", "\r"))
    assert cell.lstrip("\t\r") in escaped or cell in escaped
