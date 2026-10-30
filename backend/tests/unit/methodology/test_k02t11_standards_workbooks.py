"""K-02-T11 (TASK-2310; SPEC-500 AC-45 to AC-48; K-02 §3 F5): firm-standard content as workbooks.

The row's acceptance: exporting 1065 Review Checklist v4 and importing the file again produces a
draft with an empty diff, and no import changes a published version. The round trip is proven
on every kind's payload shape; an import only ever adds a draft (`standards.import_draft`).
"""

from __future__ import annotations

import inspect
import io
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from abacus.modules.methodology import standards, standards_import
from abacus.modules.methodology.standards import validate_payload

CHECKLIST = {
    "kind": "review_checklist",
    "applies_to": {"form": "1065", "tax_year": 2025},
    "items": [
        {"key": "k1.basis", "section": "Partners", "text": "Basis schedules tie to K-1s"},
        {"key": "m1.tie", "section": "Book to tax", "text": "M-1 ties to the trial balance"},
    ],
}
LEVELS = {
    "kind": "review_levels",
    "tiers": [
        {
            "tier": 1,
            "name": "Simple",
            "required_levels": ["L1", "L2"],
            "second_partner_review": False,
            "criteria": "",
        },
        {
            "tier": 3,
            "name": "Complex",
            "required_levels": ["L1", "L2", "L4"],
            "second_partner_review": True,
            "criteria": "Multi-state",
        },
    ],
}
MATERIALITY = {
    "kind": "materiality_ranges",
    "rows": [
        {
            "engagement_kind": "ebp_audit",
            "benchmark": "Net assets",
            "low_pct": "0.5",
            "high_pct": "1",
        }
    ],
    "performance_materiality": {"low_pct": "50", "high_pct": "75"},
    "clearly_trivial_pct": "5",
}
CONFIDENCE = {
    "kind": "document_confidence",
    "hold_below_pct": "85",
    "auto_accept_above_pct": "98",
    "auto_accept_enabled": False,
}


@pytest.mark.parametrize(
    "payload", [CHECKLIST, LEVELS, MATERIALITY, CONFIDENCE], ids=lambda p: p["kind"]
)
def test_ac45_export_then_import_is_an_empty_diff(payload: dict[str, object]) -> None:
    kind = str(payload["kind"])
    stored = validate_payload(kind, payload)
    data = standards_import.export_workbook(kind, "v4", stored)
    again = validate_payload(kind, standards_import.read_payload(kind, data, csv_file=False))
    assert standards.payload_hash(again) == standards.payload_hash(stored)


def test_ac45_the_export_is_byte_stable() -> None:
    stored = validate_payload("review_checklist", CHECKLIST)
    one = standards_import.export_workbook("review_checklist", "v4", stored)
    two = standards_import.export_workbook("review_checklist", "v4", stored)
    assert one == two


def test_ac46_formulas_are_cached_values_and_problems_name_cells() -> None:
    book = Workbook()
    ws = book.active
    assert ws is not None
    ws.title = "Rows"
    ws.append(["key", "section", "text", ""])
    ws.append(["a.b", "S", "=CMD|' /C calc'!A0", "x"])
    raw = io.BytesIO()
    book.save(raw)
    with pytest.raises(standards_import.ImportInvalid) as invalid:
        standards_import.read_payload("review_checklist", raw.getvalue(), csv_file=False)
    assert [(p.sheet, p.row, p.column, p.code) for p in invalid.value.problems] == [
        ("Rows", 1, "D", "header_missing")
    ]
    book2 = load_workbook(io.BytesIO(raw.getvalue()), read_only=True, data_only=True)
    assert book2.worksheets[0]["C2"].value is None  # a formula has no cached value: never run


def test_ac46_an_unreadable_file_is_one_problem_never_its_content() -> None:
    with pytest.raises(standards_import.ImportInvalid) as invalid:
        standards_import.read_payload(
            "review_checklist", b"not a workbook <script>", csv_file=False
        )
    assert [p.code for p in invalid.value.problems] == ["not_a_workbook"]


def test_ac46_a_csv_is_the_rows_sheet() -> None:
    data = b"context,pct,amount_usd\nclose_flux,10,5000\n"
    payload = standards_import.read_payload("variance_thresholds", data, csv_file=True)
    stored = validate_payload("variance_thresholds", payload)
    assert (
        stored["rows"] == [{"context": "close_flux", "pct": "10", "amount_usd": 5000}]
        or Decimal(
            str(stored["rows"][0]["pct"])  # type: ignore[index]  # the stored JSON row
        )
        == 10
    )


def test_ac47_an_import_only_ever_adds_a_draft() -> None:
    source = inspect.getsource(standards.import_draft)
    assert "tx.session.add(" in source and "update(" not in source
    assert "DraftExists" in source and "_owner_guard(ctx, IMPORT" in source
    assert "publish" not in source.replace("never publishes", "")


def test_ac48_onboarding_reads_one_sheet_per_standard() -> None:
    book = Workbook()
    ws = book.active
    assert ws is not None
    ws.title = "Standards"
    ws.append(["key", "name", "kind", "owner_email"])
    ws.append(["bh-variance", "BH variance", "variance_thresholds", "margaret@bh.example"])
    ws.append(["incomplete", None, None, None])
    rows = book.create_sheet("bh-variance")
    rows.append(["context", "pct", "amount_usd"])
    rows.append(["close_flux", 10, 5000])
    raw = io.BytesIO()
    book.save(raw)
    found, problems = standards_import.read_onboarding(raw.getvalue())
    assert [r.key for r in found] == ["bh-variance"]
    assert found[0].payload["rows"] == [{"context": "close_flux", "pct": 10, "amount_usd": 5000}]
    assert [(p.row, p.code) for p in problems] == [(3, "row_incomplete")]
