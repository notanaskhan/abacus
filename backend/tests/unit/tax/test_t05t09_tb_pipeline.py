"""T-05-T09 (TASK-6810; SPEC-651 §1; DEC-3408): the entity TB pipeline on Ridgeline's 2025 TB
(TXP-02, verbatim: debits positive, credits negative, whole dollars).

Row acceptance: "Ridgeline ATB total assets 17,914,500 = 11,048,300 + 6,866,200, every column
foots to $0, and Unmapped 1 blocks export in the Run 1 variant."
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from abacus.modules.tax.compute.entity.tb_pipeline import COLUMNS, TbAccount, run

D = Decimal


def _a(
    number: str,
    name: str,
    section: str,
    line: str | None,
    py: str,
    utb: str,
    aje: str = "0",
    tje: str = "0",
    role: str | None = None,
) -> TbAccount:
    return TbAccount(
        number, name, section, line, D(utb), aje=D(aje), tje=D(tje), py=D(py), capital_role=role
    )  # type: ignore[arg-type]


RIDGELINE = (
    _a("1000", "Cash — operating", "assets", "L1", "463067", "693667"),
    _a("1100", "Tenant receivables", "assets", "L2a", "90200", "96000"),
    _a("1200", "Municipal bond fund", "assets", "L5", "225600", "240000"),
    _a("1300", "Escrows & other assets", "assets", "L13", "148500", "158000"),
    _a("1500", "Land", "assets", "L11", "3600000", "3600000"),
    _a("1600", "Buildings & improvements", "assets", "L9a", "15040000", "15752000"),
    _a("1650", "Accumulated depreciation", "assets", "L9b", "-1891667", "-2625167"),
    _a("2000", "Accounts payable", "liabilities", "L15", "-112800", "-120000"),
    _a("2050", "Accrued expenses", "liabilities", "L17", "-88400", "-75500", aje="-18500"),
    _a("2100", "Tenant security deposits", "liabilities", "L17", "-114500", "-121800"),
    _a(
        "2500",
        "Mortgage notes payable (nonrecourse)",
        "liabilities",
        "L18",
        "-11400000",
        "-10712500",
    ),
    _a(
        "3000",
        "Partners' capital — beginning",
        "equity",
        "L21",
        "-5129900",
        "-5960000",
        role="beginning",
    ),
    _a("3100", "Partner contributions", "equity", "M-2 2a", "0", "-250000", role="contributions"),
    _a(
        "3200",
        "Partner distributions",
        "equity",
        "M-2 6a",
        "560000",
        "600000",
        role="distributions",
    ),
    _a("4000", "Rental income", "income", "8825 Rents", "-3549900", "-3776500"),
    _a("4100", "Parking & other property income", "income", "8825 Rents", "-90600", "-96400"),
    _a("4500", "Interest income", "income", "K 5", "-17300", "-18400"),
    _a("4510", "Tax-exempt interest (book)", "income", "M-3 perm.", "-5800", "-6200", tje="6200"),
    _a(
        "4510-T",
        "Tax-exempt interest — Sch K 18a (tax only)",
        "income",
        "K 18a",
        "0",
        "0",
        tje="-6200",
    ),
    _a("5000", "Repairs & maintenance", "deductions", "8825 Repairs", "387600", "412300"),
    _a("5100", "Utilities", "deductions", "8825 Utilities", "175700", "186900"),
    _a("5200", "Property management fees", "deductions", "8825 Other", "154200", "164000"),
    _a("5300", "Real estate taxes", "deductions", "8825 Taxes", "374600", "380000", aje="18500"),
    _a("5400", "Insurance", "deductions", "8825 Insurance", "114400", "121700"),
    _a("5500", "Mortgage interest", "deductions", "8825 Interest", "481700", "512400"),
    _a("5600", "Depreciation", "deductions", "8825 Deprec.", "480000", "733500"),
    _a("5700", "Professional fees", "deductions", "8825 Legal/prof.", "45100", "48000"),
    _a("5800", "Other operating expenses", "deductions", "8825 Other", "60200", "64000"),
)


def test_ac_atb_total_assets_equal_liabilities_plus_equity_and_income() -> None:
    result = run(RIDGELINE)
    assert result.total_assets("atb") == D("17914500")
    assert -result.totals["atb"]["liabilities"] == D("11048300")
    assert -result.totals["atb"]["equity"] + result.book_income == D("6866200")
    assert result.book_income == D("1256200")
    assert all(t.ok for t in result.balance_sheet.values())
    assert result.capital.ok


def test_ac_every_column_foots_to_zero() -> None:
    result = run(RIDGELINE)
    for column in ("utb", "aje", "rje", "atb", "tje", "ttb"):
        assert result.column_foots[column].ok, column  # type: ignore[index]
    assert set(result.column_foots) == set(COLUMNS)


def test_the_statement_roll_ups_and_form_lines() -> None:
    result = run(RIDGELINE)
    assert result.totals["atb"]["income"] == D("-3897500")
    assert result.totals["atb"]["deductions"] == D("2641300")
    assert result.by_form_line["8825 Rents"] == D("-3872900")  # 3,776,500 + 96,400
    assert result.by_form_line["K 18a"] == D("-6200")
    assert result.by_form_line["M-3 perm."] == D("0")  # book only: the TJE moves it to 18a


def test_ac_unmapped_1_blocks_export_in_the_run_1_variant() -> None:
    assert run(RIDGELINE).export_ready
    variant = [replace(a, form_line=None) if a.number == "1300" else a for a in RIDGELINE]
    result = run(variant)
    assert result.unmapped == ("1300",)
    assert not result.export_ready and result.blocked_by == ("unmapped:1300",)


def test_every_output_carries_its_stamp() -> None:
    first, second = run(RIDGELINE), run(RIDGELINE)
    assert first.stamp.engine_name == "entity.tb_pipeline" and first.stamp.engine_version == "1"
    assert first.stamp.inputs_hash == second.stamp.inputs_hash
    changed = run([replace(RIDGELINE[0], utb=D("693668")), *RIDGELINE[1:]])
    assert changed.stamp.inputs_hash != first.stamp.inputs_hash
    assert not changed.export_ready  # the UTB no longer foots
