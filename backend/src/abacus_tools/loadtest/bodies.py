"""Generated request bodies a scenario step names (`body: <name>`; Q-03-T044).

`pbc_import_300` is chapter 10 §10.11.3's PBC import burst: a 300-row request-list workbook for
`POST /v1/engagements/{id}/request-items/import` (SPEC-018, the firm's request-list import). The
rows are the F-04 generator's request list (`synthetic.requests.request_list`, glossary terms and
audit areas only), cycled to 300 and numbered so each description is distinct. Columns: Request
(0), Area (1), Tier (2), on a sheet named `Requests`; the scenario's query string names them.

Built once per process and cached: the bytes are the same on every call, so a re-import of the same
engagement creates nothing new after the first (the service counts the rows as duplicates), which
still exercises the parse and duplicate check at full size.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Final

from openpyxl import Workbook

from abacus_tools.synthetic.requests import request_list

XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PBC_IMPORT_ROWS: Final = 300
PBC_SHEET: Final = "Requests"
PBC_HEADERS: Final = ("Request", "Area", "Tier")


@dataclass(frozen=True)
class Body:
    content: bytes
    content_type: str


def pbc_rows(count: int = PBC_IMPORT_ROWS) -> list[tuple[str, str, str]]:
    """(description, area, tier) for `count` rows, cycling the generator's request list."""
    items = request_list().items
    rows: list[tuple[str, str, str]] = []
    for n in range(count):
        item = items[n % len(items)]
        rows.append(
            (
                f"{item.description} (request {n + 1:03d})",
                item.audit_area,
                item.retrievability_tier,
            )
        )
    return rows


@cache
def pbc_import_300() -> Body:
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:  # openpyxl always makes one; the type says it may not
        raise RuntimeError("openpyxl made a workbook without a sheet")
    sheet.title = PBC_SHEET
    sheet.append(PBC_HEADERS)
    for row in pbc_rows():
        sheet.append(row)
    out = io.BytesIO()
    workbook.save(out)
    return Body(out.getvalue(), XLSX)


BODIES: Final[Mapping[str, Callable[[], Body]]] = {"pbc_import_300": pbc_import_300}
