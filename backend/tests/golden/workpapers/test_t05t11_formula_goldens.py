"""T-05-T11 (TASK-6813; ADR-078 as amended; ADR-237): the workbook formula engine's goldens,
written from the screen specs (`formula_dag.yaml`) and run against `workpapers/compute/dag.py`."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from abacus.modules.workpapers.compute.dag import CellInput, Workbook, canonical, evaluate

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "formula_dag.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_formula_golden(case: dict[str, Any]) -> None:  # Any: one YAML case
    sheet = case["sheet"]
    others = case.get("other", {})
    book = Workbook((sheet, *others))
    for a1, value in case["cells"].items():
        book.set(sheet, a1, CellInput(Decimal(value) if value is not None else None))
    for other, cells in others.items():
        for a1, value in cells.items():
            book.set(other, a1, CellInput(Decimal(value)))
    for a1, text in case["formula"].items():
        book.set(sheet, a1, CellInput(formula=text))
    results = evaluate(book)
    for a1, want in case["expect"].items():
        assert results[canonical(sheet, a1)].value == Decimal(want), a1


def test_the_goldens_are_pending_review() -> None:
    assert GOLDEN["reviewed_by"].startswith("pending: tax CPA")
    assert all(c["source"] for c in GOLDEN["cases"])
