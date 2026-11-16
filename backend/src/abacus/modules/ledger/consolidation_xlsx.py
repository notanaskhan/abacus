"""The consolidated trial balance as Excel (A-09-T19; AUD-33's Open in Excel): one sheet per
level, the engine's columns as figures and captions as text (`kernel.safe_xlsx`: no formula,
fixed clock and zip times), so the same consolidation renders byte-identical files."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.modules.ledger.compute.consolidation import Level


def render_levels(levels: Sequence[Level], names: Mapping[str, str]) -> bytes:
    sheets: list[Sheet] = []
    for level in sorted(levels, key=lambda lv: lv.level):
        head = ["Caption", "Section", *(names.get(c, c) for c in level.columns)]
        rows: list[list[object]] = [list(head)]
        for row in level.rows:
            rows.append([row.caption, row.section, *(row.amount(c) for c in level.columns)])
        rows.append(["Total", "", *(level.column_totals[c] for c in level.columns)])
        rows.append(["Total assets", "", *([""] * (len(level.columns) - 1)), level.total_assets])
        rows.append(["Net income", "", *([""] * (len(level.columns) - 1)), level.net_income])
        sheets.append(Sheet(f"Level {level.level}", rows))  # type: ignore[arg-type] -- cells are text or Decimal
    return workbook(sheets)
