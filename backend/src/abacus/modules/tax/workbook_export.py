"""Open in Excel for the entity workbook (T-05-T57; TASK-7905; TXP-11, TXP-02, TXP-07; ADR P-69 /
ADR-237, ADR-042, ADR-052; DEC-4908). Amber.

The route authorised `workbook.export` (fresh MFA, never an agent) and checked the flag. This
module reads the workbook's cells (the live workbook, or as it stood when a finished run ended),
hands them to `workpapers.api.render_workbook` (closed-grammar formulas, client strings as text,
fixed properties and ZIP times) and audits `workbook.exported` with the file's SHA-256 and sheet
count.

- Whole workbook or one sheet (`sheet`); the name is `<Entity>_<year>_<form>_Workbook_v<n>.xlsx`
  (`Ridgeline_2025_1065_Workbook_v2.xlsx`), `n` the version read (the newest finished run, or the
  one asked for).
- The live workbook is refused while a run is open (409 `export_blocked`): its cells may move.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax.workbook_service import WORKBOOK, sheets_of
from abacus.modules.workpapers.api import ExportCell, ExportSheet, render_workbook

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExportBlocked(DomainConflict):
    """A run of the return is open: the live workbook may still move."""

    code = "export_blocked"


@dataclass(frozen=True)
class WorkbookFile:
    filename: str
    data: bytes
    sha256: str
    version: int


def _decimal(raw: object) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def export_sheets(
    form: str, values: Mapping[str, Mapping[str, object]], only: str | None = None
) -> list[ExportSheet]:
    """The form's sheets in order (or one), each cell's stored value and formula."""
    out: list[ExportSheet] = []
    for key, title in sheets_of(form):
        if only is not None and key != only:
            continue
        cells: list[ExportCell] = []
        for field, typed in values.items():
            if field.endswith(":f") or not field.startswith(f"{key}!"):
                continue
            raw = typed.get("v")
            value: Decimal | str | None
            if raw is None:
                value = None
            elif typed.get("t") == "decimal":
                value = _decimal(raw)
            else:
                value = str(raw)
            formula = values.get(f"{field}:f", {}).get("v")
            cells.append(
                ExportCell(
                    field.split("!", 1)[1], value, None if formula is None else str(formula)
                )
            )
        out.append(ExportSheet(key, f"{key} {title}", tuple(cells)))
    return out


def filename(entity: str, year: int, form: str, version: int, sheet: str | None) -> str:
    """ASCII, no spaces: the entity's first word, year, form, `Workbook`, version."""
    word = re.sub(r"[^A-Za-z0-9]", "", (entity.split() or ["Workbook"])[0]) or "Workbook"
    form_part = re.sub(r"[^A-Za-z0-9-]", "", form) or "Form"
    tail = f"_Sheet{sheet}" if sheet else ""
    return f"{word}_{year}_{form_part}_Workbook_v{version}{tail}.xlsx"


async def export_workbook(
    ctx: AuthContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    entity: str,
    form: str,
    sheet: str | None,
    version: int | None,
    versions: Sequence[tuple[int, object]],
    run_open: bool,
) -> WorkbookFile:
    """`versions` are the finished runs (number, finished_at), newest first."""
    from abacus.kernel.errors import NotFound
    from abacus.modules.review.api import current_values, values_as_of
    from abacus.modules.tax.overview import tax_year_of
    from abacus.modules.tax.workbook_service import sheet_or_404

    only = None if sheet is None else sheet_or_404(form, sheet)
    newest = versions[0][0] if versions else 1
    if version is None or version == newest:
        if run_open:
            raise ExportBlocked(facts={"return_id": str(return_id)})
        values = await current_values(ctx.tenant, WORKBOOK, return_id)
        read = newest
    else:
        found = next((v for v in versions if v[0] == version), None)
        if found is None:
            raise NotFound("workbook_version")
        then = await values_as_of(ctx.tenant, WORKBOOK, [return_id], found[1])  # type: ignore[arg-type] -- a finished run's datetime
        values = then.get(return_id, {})
        read = version
    data = render_workbook(export_sheets(form, values, only))
    digest = hashlib.sha256(data).hexdigest()
    year = await tax_year_of(ctx.tenant, return_id)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "workbook.exported",
            target=Target(WORKBOOK, return_id),
            after=Ref(sha256=digest, version=read, sheets=1 if only else len(sheets_of(form))),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return WorkbookFile(filename(entity, year, form, read, only), data, digest, read)


__all__ = [
    "MEDIA_TYPE",
    "ExportBlocked",
    "WorkbookFile",
    "export_sheets",
    "export_workbook",
    "filename",
]
