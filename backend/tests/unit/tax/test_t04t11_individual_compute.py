"""T-04-T11 (TASK-6524; T-04 §4.4, AC-3.2, AC-6.3, AC-7.2, AC-8.2; DEC-3124): the individual
return compute package on the Feld 2025 inputs.

Row acceptance: "Every function is pure and on the Feld inputs returns 615,605, 61,580 < 98,450,
4,674,575, 141,634/96,989/69,277 and 11,279 exactly."
"""

from __future__ import annotations

import ast
from decimal import Decimal as D
from pathlib import Path

from abacus.modules.tax.compute.individual import forms, k1, residency

PKG = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "abacus"
    / "modules"
    / "tax"
    / "compute"
    / "individual"
)


def test_1040_line_2b() -> None:
    assert forms.leadsheet_line("2b", [D(2310), D(4600)]).total == D(6910)


def test_it201_ties() -> None:
    out = forms.it201(
        forms.It201Inputs(
            D(598030), D(1550), D(16025), D(16050), D(29791), D(23014),
            (D(17400), D(9390), D(20000), D(4746)),
        )
    )  # fmt: skip
    assert out.line33_ny_agi == D(615605)
    assert out.line37_taxable == D(599555)
    assert (out.total_tax, out.total_payments, out.balance_due) == (D(52805), D(51536), D(1269))


def test_qbi_under_the_limit() -> None:
    out = k1.qbi_199a(D(307900), D(0), D(3938000), 2025)
    assert (out.tentative, out.limit, out.deduction, out.below_limit) == (
        D(61580),
        D(98450),
        D(61580),
        True,
    )


def test_outside_basis() -> None:
    assert k1.outside_basis(D(1912500), D(2762075)).total == D(4674575)


def test_state_sourcing_foots_by_largest_remainder() -> None:
    out = k1.state_sourcing(D(307900), [("IL", D("46.0")), ("CO", D("31.5")), ("NY", D("22.5"))])
    assert out.shares == (("IL", D(141634)), ("CO", D(96989)), ("NY", D(69277)))
    assert sum(v for _, v in out.shares) == D(307900)


def test_ptet_shares_half_up() -> None:
    out = k1.ptet_share([("IL", D(28044)), ("CO", D(17070)), ("NY", D(18982))], 2025)
    assert [v for _, v in out.shares] == [D(7011), D(4268), D(4746)] and out.total == D(16025)


def test_allocation_it112r_it225() -> None:
    assert residency.allocation([D(268400), D(6910), D(14820), D(307900)]).total == D(598030)
    credit = residency.it112r(D(11279), D(41070), D(238623), D(615605))
    assert (credit.limit, credit.credit) == (D(15920), D(11279))
    assert residency.it225([D(4746), D(11279)]).total == D(16025)


def test_residency_rules() -> None:
    full = residency.residency_rules(residency.ResidencyFacts(281, True, False), 2025)
    assert (full.recommended, full.conflict) == ("full_year_nys_nyc", False)
    split = residency.residency_rules(residency.ResidencyFacts(150, True, True), 2025)
    assert split.conflict is True


def test_the_same_inputs_give_the_same_stamp() -> None:
    a = k1.outside_basis(D(1912500), D(2762075)).stamp
    assert a == k1.outside_basis(D(1912500), D(2762075)).stamp and len(a.inputs_hash) == 64


def test_the_package_imports_only_the_kernel_numeric_and_itself() -> None:
    allowed = ("abacus.kernel.numeric", "abacus.modules.tax.compute.individual")
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("abacus")
            ):
                assert node.module.startswith(allowed), (path.name, node.module)
