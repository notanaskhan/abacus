"""T-05-T60 (TASK-7936; T-05 F11; ADR-150 W2; DEC-49, DEC-78; DEC-4931): the entity section of the
CCH file-bridge export.

Row acceptance: "An export before final approval is refused, and no code path marks the entity
return transmitted except a person."

Unit level: the two sheets from the approved checkpoint's workbook values, the byte-stable
workbook, the Unmapped gate, and the never-transmit rules extended to the entity path (no network
client, no transmit verb, human-only marking and recording). The full export path against a
database (final approval, grant, checkpoint) is T-01's suite, unchanged; T-05-T63 adds the
independent entity tests.
"""

from __future__ import annotations

import ast
import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from abacus.modules.tax import export, export_entity
from abacus.modules.tax.export_entity import (
    ExportUnmapped,
    allocations,
    require_mapped,
    ttb_lines,
)

RETURN = uuid4()
SRC = Path(export_entity.__file__)


def _v(value: object) -> dict[str, object]:
    return {"v": value}


VALUES: dict[str, dict[str, object]] = {
    "03!A1": _v("Form line"), "03!A2": _v("1a"), "03!B2": _v("Gross receipts"),
    "03!C2": _v("1231600"), "03!A3": _v("L1"), "03!B3": _v("Cash"), "03!C3": _v("-18400"),
    "03!A4": _v("Total"),
    "06!A1": _v("Line"), "06!A2": _v("1"), "06!C2": _v("600000"), "06!A3": _v("2"),
    "06!C3": _v("6200"),
    "09!B1": _v("Meera Shah"), "09!C1": _v("Daniel Reyes"),
    "09!B2": _v("360000"), "09!C2": _v("240000"), "09!B3": _v("3720"), "09!C3": _v("2480"),
}  # fmt: skip


def test_ttb_by_cch_line_code_from_sheet_03_skipping_the_total() -> None:
    assert [(r.cch_line_code, r.label, r.amount) for r in ttb_lines(VALUES)] == [
        ("1a", "Gross receipts", Decimal("1231600")),
        ("L1", "Cash", Decimal("-18400")),
    ]


def test_allocations_by_schedule_k_line_and_partner_tie_to_the_line() -> None:
    meera = uuid4()
    rows = allocations(VALUES, RETURN, {"Meera Shah": meera})
    assert [(a.partner, a.schedule_k_line, a.amount) for a in rows] == [
        ("Meera Shah", "1", Decimal("360000")),
        ("Daniel Reyes", "1", Decimal("240000")),
        ("Meera Shah", "2", Decimal("3720")),
        ("Daniel Reyes", "2", Decimal("2480")),
    ]
    assert rows[0].partner_ref == meera
    assert rows[1].partner_ref == allocations(VALUES, RETURN, {})[1].partner_ref  # stable id
    assert sum(a.amount for a in rows if a.schedule_k_line == "1") == Decimal("600000")


def _section() -> export_entity.EntitySection:
    return export_entity.EntitySection(
        tuple(ttb_lines(VALUES)), tuple(allocations(VALUES, RETURN, {}))
    )


def test_the_workbook_carries_the_entity_sheets_and_is_byte_stable() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    args: dict[str, Any] = {  # Any: the workbook's keyword arguments
        "engine_id": "2025P:RIDGELINE", "tax_year": 2025, "form": "1065", "values": {},
        "at": at, "entity": _section(),
    }  # fmt: skip
    first = export.workbook(**args)
    assert first == export.workbook(**args)
    book = load_workbook(io.BytesIO(first))
    assert book.sheetnames == ["Return", "Fields", "TTB", "Allocations"]
    ttb = [list(r) for r in book["TTB"].iter_rows(values_only=True)]
    assert ttb[0] == ["cch_line_code", "label", "amount"]
    assert ttb[2] == ["L1", "Cash", "-18400"]  # a negative figure stays a number, not a formula
    shares = [list(r) for r in book["Allocations"].iter_rows(values_only=True)]
    assert shares[0] == ["partner_ref", "partner", "schedule_k_line", "amount"]
    assert len(shares) == 5


def test_an_individual_return_exports_without_the_entity_sheets() -> None:
    raw = export.workbook(
        engine_id="2025I:FELDJ", tax_year=2025, form="1040", values={},
        at=datetime(2026, 1, 1, tzinfo=UTC),
    )  # fmt: skip
    assert load_workbook(io.BytesIO(raw)).sheetnames == ["Return", "Fields"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unmapped", [None, 1, 3])
async def test_export_is_refused_while_unmapped_is_above_zero(
    monkeypatch: pytest.MonkeyPatch, unmapped: int | None
) -> None:
    async def engagement(*_: object) -> object:
        return uuid4()

    async def count(*_: object) -> int | None:
        return unmapped

    monkeypatch.setattr(export_entity, "engagement_of_return", engagement)
    monkeypatch.setattr(export_entity, "unmapped_accounts", count)
    with pytest.raises(ExportUnmapped):
        await require_mapped(object(), RETURN)  # type: ignore[arg-type] -- stand-in


@pytest.mark.asyncio
async def test_a_fully_mapped_return_passes_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def engagement(*_: object) -> object:
        return uuid4()

    async def count(*_: object) -> int:
        return 0

    monkeypatch.setattr(export_entity, "engagement_of_return", engagement)
    monkeypatch.setattr(export_entity, "unmapped_accounts", count)
    await require_mapped(object(), RETURN)  # type: ignore[arg-type] -- stand-in


def test_the_unmapped_gate_runs_before_the_grant_is_spent() -> None:
    body = Path(export.__file__).read_text(encoding="utf-8")
    assert body.index("await require_mapped(") < body.index("await consume_grant(")
    assert body.index("raise NotFinalApproved") < body.index("await require_mapped(")


# --- never transmit (R-04), extended to the entity path -------------------------------------

_NETWORK = {"httpx", "requests", "aiohttp", "urllib", "socket", "boto3", "botocore", "smtplib"}


def test_the_entity_section_imports_no_network_client_and_names_no_transmit_verb() -> None:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imported.add((n.module or "").split(".")[0])
    assert not imported & _NETWORK
    names = {
        n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert not any(v in name for name in names for v in ("transmit", "submit", "send", "file_"))


def test_only_a_person_exports_marks_exported_or_records_a_transmission() -> None:
    from abacus.modules.identity.authz._matrix import ACTIONS

    for action in ("tax_return.export", "transmission.record", "tax_return.approve"):
        rule = ACTIONS[action]
        assert rule.get("agent") == "deny" and rule.get("system") == "deny", action
    from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS

    assert {"engine_export.generated", "engine_export.marked_exported"} <= HUMAN_ONLY_ACTIONS
