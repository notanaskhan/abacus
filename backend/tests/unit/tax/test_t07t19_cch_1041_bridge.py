"""T-07-T19 (TASK-8080; T-07 F10): the CCH Axcess file bridge in 1041 mode. Row acceptance: "A
synthetic CCH export round-trips with an empty diff, a one-dollar difference on line 18 raises one
engine_diagnostic issue, and no transmit path exists."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- import order
from abacus.modules.tax import export
from abacus.modules.tax import export_fiduciary as xf
from abacus.modules.tax import fiduciary_service as fs
from abacus.modules.tax.compute import fiduciary as f

D = Decimal
NORA = "00000000-0000-4000-8000-00000000a0a1"
THEO = "00000000-0000-4000-8000-00000000a0a2"


def _outputs() -> dict[str, object]:
    result = f.compute(
        f.FiduciaryInputs(
            2025,
            f.Determinations("complex_trust"),
            (
                f.FaiLine("interest", "interest", D("107500")),
                f.FaiLine("dividends", "ordinary_dividends", D("322500"), qualified=D("258000")),
            ),
            (f.TrustExpense("fees", D("30000"), "principal"),),
            (
                f.Distribution(NORA, "Nora Calloway", date(2025, 6, 30), D("80000")),
                f.Distribution(NORA, "Nora Calloway", date(2025, 12, 15), D("80000")),
                f.Distribution(THEO, "Theo Calloway", date(2025, 12, 15), D("80000")),
            ),
        )
    )
    return fs.computed_outputs(result, {})


def _section() -> xf.FiduciarySection:
    out = _outputs()
    return xf.FiduciarySection(tuple(xf.field_rows(out, "complex_trust")), tuple(xf.k1_rows(out)))


def _engine_from_export(raw: bytes) -> dict[str, dict[str, object]]:
    """What a synthetic CCH import would carry back: every exported 1041 figure, unchanged."""
    book = load_workbook(io.BytesIO(raw), read_only=True)
    out: dict[str, dict[str, object]] = {}
    for row in list(book["Fiduciary"].iter_rows(values_only=True))[1:]:
        out[str(row[0])] = {"t": "decimal", "v": str(row[2])}
    for row in list(book["K1_1041"].iter_rows(values_only=True))[1:]:
        out[f"k1_1041.{row[0]}.box_{row[2]}"] = {"t": "decimal", "v": str(row[3])}
    return out


def _export() -> bytes:
    return export.workbook(
        engine_id="2025F:CALLOWAY",
        tax_year=2025,
        form="1041",
        values={},
        at=datetime(2026, 1, 1, tzinfo=UTC),
        fiduciary=_section(),
    )


def test_ac_line_18_and_the_k1_boxes_are_exported() -> None:
    fields = {r.engine_field_key: r.value for r in _section().fields}
    assert fields["f1041.line_18"] == "240000.00"
    assert fields["f1041.type_of_entity"] == "complex"
    boxes = {(k.beneficiary_ref, k.box): k.amount for k in _section().k1}
    assert boxes[(THEO, "1")] == D("20000.00") and boxes[(NORA, "2b")] == D("96000.00")


def test_ac_a_synthetic_export_round_trips_with_an_empty_diff() -> None:
    rows = xf.compare(_section(), _engine_from_export(_export()))
    assert rows and not [r for r in rows if r.differs]
    assert _export() == _export()  # the same section, the same bytes


def test_ac_one_dollar_on_line_18_is_one_difference() -> None:
    engine = _engine_from_export(_export())
    engine["f1041.line_18"] = {"t": "decimal", "v": "240001.00"}
    differing = [r for r in xf.compare(_section(), engine) if r.differs]
    assert [r.key for r in differing] == ["f1041.line_18"]


def test_ac_no_transmit_path_exists() -> None:
    source = Path(xf.__file__).read_text()
    for word in ("transmit(", "efile(", "submit_return", "import httpx", "requests.post"):
        assert word not in source
    assert not any(name.startswith("transmit") for name in dir(xf))
