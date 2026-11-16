"""T-07-T16 (TASK-8076; SPEC-656 AC-7.1, AC-8.1): the fiduciary service's pure parts.

Row acceptance: "Editing Theo's Dec 15 distribution to 100,000 creates a version showing 260,000 /
140,000 / 139,900 with struck priors and a stale L2 sign-off, and two exports of one version are
byte-identical." The stale sign-off and the version rows are the integration test's (end pass);
here the outputs, the struck priors against the signed version and the export bytes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.tax import fiduciary_service as fs
from abacus.modules.tax.compute import fiduciary as f

D = Decimal
DET = f.Determinations(
    "complex_trust",
    gains_clause_ref="Art. II",
    distribution_clause_ref="Art. III(a)",
    retained_clause_ref="Art. IV(a)",
)
LINES = (
    f.FaiLine("interest", "interest", D("107500")),
    f.FaiLine("dividends", "ordinary_dividends", D("322500"), qualified=D("258000")),
)
FEES = (f.TrustExpense("trustee_fees", D("30000"), "principal"),)
NORA = "00000000-0000-4000-8000-00000000a0a1"
THEO = "00000000-0000-4000-8000-00000000a0a2"


def _result(theo: str) -> f.FiduciaryResult:
    return f.compute(
        f.FiduciaryInputs(
            2025,
            DET,
            LINES,
            FEES,
            (
                f.Distribution(NORA, "Nora Calloway", date(2025, 6, 30), D("80000")),
                f.Distribution(NORA, "Nora Calloway", date(2025, 12, 15), D("80000")),
                f.Distribution(THEO, "Theo Calloway", date(2025, 12, 15), D(theo)),
            ),
        )
    )


def test_ac71_theo_100000_shows_260000_140000_139900_with_struck_priors() -> None:
    signed = fs.computed_outputs(_result("80000"), {"theo-dec15": "80000.00"})
    edited = fs.computed_outputs(_result("100000"), {"theo-dec15": "100000.00"})
    assert (edited["distributions"], edited["retained_dni"], edited["taxable_income"]) == (
        "260000.00",
        "140000.00",
        "139900.00",
    )
    prior = fs._prior_amounts(signed["tree"])  # type: ignore[arg-type] -- the test's loose input
    nodes = fs._flatten(edited["tree"], None, 0, prior)  # type: ignore[arg-type] -- the test's loose input
    changed = [n for n in nodes if n.changed]
    assert changed, "the edit changes rows against the signed version"
    assert all(n.prior_value is not None and n.prior_value != n.value for n in changed)
    unchanged = [n for n in nodes if not n.changed]
    assert all(n.prior_value is None for n in unchanged)


def test_ac81_two_exports_of_one_version_are_byte_identical() -> None:
    outputs = fs.computed_outputs(_result("100000"), {})
    first = fs.workbook_of(2, outputs)
    assert first == fs.workbook_of(2, outputs)
    assert first[:2] == b"PK"


def test_the_content_hash_moves_with_the_outputs() -> None:
    assert fs.outputs_hash(fs.computed_outputs(_result("80000"), {})) != fs.outputs_hash(
        fs.computed_outputs(_result("100000"), {})
    )
