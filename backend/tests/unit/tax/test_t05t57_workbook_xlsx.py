"""T-05-T57 (TASK-7905; TXP-11, TXP-02, TXP-07; ADR P-69 / ADR-237, ADR-042, ADR-052; DEC-4908):
deterministic xlsx export of the entity workbook.

Row acceptance: "Ridgeline_2025_1065_Workbook_v2.xlsx is byte-identical for identical data, opens
with live formulas, and a client string starting with = stays text."
"""

from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import load_workbook

from abacus.modules.tax.workbook_export import export_sheets, filename
from abacus.modules.workpapers.export_xlsx import (
    ExportCell,
    ExportSheet,
    excel_formula,
    render_workbook,
)

VALUES: dict[str, dict[str, object]] = {
    "05!A2": {"t": "text", "v": '=HYPERLINK("http://x","click")'},
    "05!B2": {"t": "decimal", "v": "2000000"},
    "05!F2": {"t": "decimal", "v": "6866200"},
    "05!F2:f": {"t": "text", "v": "=B2+C2-D2+E2"},
    "07!B9": {"t": "decimal", "v": "6860000"},
    "07!B10:f": {"t": "text", "v": "=SUM(05!F2:F3)"},
    "07!B10": {"t": "decimal", "v": "6866200"},
}


def test_ac_byte_identical_for_identical_data() -> None:
    a = render_workbook(export_sheets("1065", VALUES))
    b = render_workbook(export_sheets("1065", dict(reversed(list(VALUES.items())))))
    assert a == b


def test_ac_live_formulas_and_text_stays_text() -> None:
    book = load_workbook(io.BytesIO(render_workbook(export_sheets("1065", VALUES))))
    names = book.sheetnames
    capital = book[next(n for n in names if n.startswith("05"))]
    assert capital["F2"].value == "=B2+C2-D2+E2"
    assert capital["F2"].data_type == "f"
    assert capital["A2"].data_type == "s"
    assert capital["A2"].quotePrefix
    m2 = book[next(n for n in names if n.startswith("07"))]
    assert str(m2["B10"].value).startswith("=SUM('05 ")


def test_ac_formula_outside_the_grammar_is_never_written_as_a_formula() -> None:
    assert excel_formula('=HYPERLINK("x")', "05", {}) is None
    data = render_workbook(
        [ExportSheet("05", "05 Capital", (ExportCell("B2", Decimal(5), "=WEBSERVICE(A1)"),))]
    )
    sheet = load_workbook(io.BytesIO(data))["05 Capital"]
    assert sheet["B2"].value == 5
    assert sheet["B2"].data_type == "n"


def test_ac_filename() -> None:
    assert (
        filename("Ridgeline Property Partners, LP", 2025, "1065", 2, None)
        == "Ridgeline_2025_1065_Workbook_v2.xlsx"
    )
    assert filename("Ridgeline", 2025, "1065", 2, "05").endswith("_Sheet05.xlsx")


def test_ac_one_sheet() -> None:
    sheets = export_sheets("1065", VALUES, "07")
    assert [s.key for s in sheets] == ["07"]


def test_t57_rest_grid_widths_and_a_persons_cells_are_filled() -> None:
    """T-05-T57 rest (TASK-7929): TXP-11's widths on every sheet; only the cells a person wrote
    last carry the fill; the bytes stay identical for identical data."""
    from abacus.modules.tax.workbook_export import GRID_WIDTHS

    human = frozenset({"05!A2"})
    data = render_workbook(export_sheets("1065", VALUES, human=human))
    book = load_workbook(io.BytesIO(data))
    capital = book[next(n for n in book.sheetnames if n.startswith("05"))]
    assert capital.column_dimensions["A"].width == round(GRID_WIDTHS[0] / 7, 1)
    assert capital.column_dimensions["B"].width == round(GRID_WIDTHS[1] / 7, 1)
    assert capital["A2"].fill.fill_type == "solid"
    assert capital["F2"].fill.fill_type is None
    assert render_workbook(export_sheets("1065", VALUES, human=human)) == data
