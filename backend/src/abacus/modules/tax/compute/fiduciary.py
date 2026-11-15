"""The fiduciary engine (T-07-T09; TASK-8036; T-07 §3.6; SPEC-656 AC-5.1, AC-6.1 to AC-7.1,
AC-9.2, AC-11.1; ADR-050, DEC-77).

Pure: `Decimal` in, `Decimal` out, no I/O but the parameter file, no clock. It computes the
fiduciary workpaper the firm reviews on TXT-02 and TXT-03 (the engine of record, CCH Axcess,
computes the return; every engine figure ties back to these):

1. **FAI** (fiduciary accounting income) from the FAI lines and the approved FAI definition: the
   lines the instrument allocates to income, less the expenses charged to income. Gains the
   instrument allocates to principal are not FAI.
2. **DNI** under IRC §643(a): the income items in DNI (interest, dividends and their qualified
   subset, tax-exempt interest, other income), less every deductible expense, whether charged to
   income or principal, allocated pro rata by character (Treas. Reg. §1.652(b)-3): the qualified
   subset takes its share of the dividends' portion, and the share on tax-exempt interest is
   not deductible (IRC §265). Capital gains are out of DNI unless a clause includes them.
3. **IDD** under IRC §661: the smaller of the distributions and DNI, less its tax-exempt part.
   A simple trust (IRC §651) is deemed to distribute all FAI, whatever it paid.
4. **Allocation** by each beneficiary's share of the distributions (IRC §§652, 662): DNI by
   character carries out pro rata, so the K-1 (1041) boxes follow: box 1 interest, 2a ordinary
   dividends, 2b qualified dividends (a subset of 2a), and the rest in `box_other` (5 other
   portfolio income, 4a capital gain in DNI, 14 A tax-exempt interest). The tie: the taxable
   boxes sum to IDD for every distribution set (`kernel.numeric.allocate`, largest remainder).
5. **Retained DNI**, the IRC §642(b) exemption by entity type and **taxable income**.
6. The **65-day window** (IRC §663(b)): Jan 1 to the 65th day after year-end.

Every result carries `engine_version` and `inputs_hash` and a tree projection with the clause
each row rests on (TXT-02's CalcTree; clause chips appear only where the instrument governs a
row, AC-6.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast

import yaml

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.entity.stamp import Stamp, stamp

ENGINE_NAME: Final = "tax.fiduciary"
_DIR: Final = Path(__file__).parent / "parameters" / "fiduciary"
ZERO: Final = Decimal("0.00")
_CENT: Final = Decimal("0.01")

Character = Literal[
    "interest", "ordinary_dividends", "tax_exempt_interest", "capital_gains", "other"
]
EntityType = Literal["complex_trust", "simple_trust", "estate"]
# The order the tree and the boxes read in.
_CHARACTERS: Final[tuple[Character, ...]] = (
    "interest", "ordinary_dividends", "tax_exempt_interest", "other", "capital_gains",
)  # fmt: skip
_BOX_OTHER: Final = {"other": "5", "capital_gains": "4a", "tax_exempt_interest": "14A"}


# --- inputs -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaiLine:
    """One income line of the year (a custodial-statement line, cited by the service)."""

    key: str
    character: Character
    amount: Decimal
    qualified: Decimal = ZERO  # dividends only: the qualified part of `amount`
    to_principal: bool = False  # the instrument allocates it to principal (gains, by default)
    clause_ref: str | None = None


@dataclass(frozen=True, slots=True)
class TrustExpense:
    key: str
    amount: Decimal
    charged_to: Literal["income", "principal"]
    deductible: bool = True
    clause_ref: str | None = None


@dataclass(frozen=True, slots=True)
class Distribution:
    beneficiary: str  # the beneficiary's key (a contact id in the service)
    name: str
    paid_on: date
    amount: Decimal
    source: Literal["income", "principal"] = "income"
    clause_ref: str | None = None


@dataclass(frozen=True, slots=True)
class Determinations:
    """What the approved instrument interpretation decided for tax (TXT-01)."""

    entity_type: EntityType
    gains_in_dni: bool = False
    gains_clause_ref: str | None = (
        None  # Art. II: gains to principal, or the clause including them
    )
    distribution_clause_ref: str | None = None  # Art. III(a)
    retained_clause_ref: str | None = None  # Art. IV(a): undistributed income to principal


@dataclass(frozen=True, slots=True)
class FiduciaryInputs:
    tax_year: int
    determinations: Determinations
    fai_lines: tuple[FaiLine, ...]
    expenses: tuple[TrustExpense, ...] = ()
    distributions: tuple[Distribution, ...] = ()


# --- parameters ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FiduciaryParameters:
    tax_year: int
    version: int
    exemption: dict[str, Decimal | None]
    window_days: int
    top_bracket_threshold: Decimal | None
    niit_rate_pct: Decimal


def _dec(value: object) -> Decimal:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError(f"not a decimal: {value!r}")
    return Decimal(str(value))


def parse_parameters(raw: dict[str, object]) -> FiduciaryParameters:
    """The parameter file's mapping, validated (a missing or wrong key raises)."""
    exemption = cast(dict[str, object], raw["exemption"])
    for required in ("estate", "simple_trust", "complex_trust"):
        if exemption.get(required) is None:
            raise ValueError(f"exemption.{required} is required")
    threshold = raw["top_bracket_threshold"]
    return FiduciaryParameters(
        tax_year=int(cast(int, raw["tax_year"])),
        version=int(cast(int, raw["version"])),
        exemption={k: None if v is None else _dec(v) for k, v in exemption.items()},
        window_days=int(cast(int, raw["sixty_five_day_election_days"])),
        top_bracket_threshold=None if threshold is None else _dec(threshold),
        niit_rate_pct=_dec(raw["niit_rate_pct"]),
    )


@cache
def parameters(tax_year: int) -> FiduciaryParameters:
    """`parameters/fiduciary/ty<tax_year>.yaml` (PROTECTED). A missing year raises LookupError."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.is_file():
        raise LookupError(f"fiduciary parameters: ty{tax_year}")
    return parse_parameters(cast(dict[str, object], yaml.safe_load(path.read_text("utf-8"))))


# --- outputs ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BeneficiaryAllocation:
    beneficiary: str
    name: str
    distributions: Decimal
    share: Decimal  # of the distributions, six places (numeric(9,6))
    dni_allocated: Decimal  # the taxable DNI carried out: box 1 + 2a + the taxable others
    box_1: Decimal
    box_2a: Decimal
    box_2b: Decimal
    box_other: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class TreeRow:
    """One CalcTree row (TXT-02): a code-computed figure and the clause it rests on, if any."""

    key: str
    label: str
    amount: Decimal
    clause_ref: str | None = None
    children: tuple[TreeRow, ...] = ()


@dataclass(frozen=True, slots=True)
class FiduciaryResult:
    tax_year: int
    entity_type: EntityType
    fai: Decimal
    income_by_character: dict[str, Decimal]
    expense_by_character: dict[str, Decimal]
    dni: Decimal
    dni_by_character: dict[str, Decimal]
    dni_qualified: Decimal
    distributions: Decimal
    principal_distributions: Decimal
    idd: Decimal
    exempt_carried_out: Decimal
    allocations: tuple[BeneficiaryAllocation, ...]
    retained_dni: Decimal
    fai_not_distributed: Decimal
    deductible_expenses: Decimal
    exemption: Decimal
    taxable_income: Decimal
    tie: bool
    tree: tuple[TreeRow, ...]
    engine_name: str
    engine_version: str
    inputs_hash: str
    notes: tuple[str, ...] = field(default=())


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


def _split(total: Decimal, weights: Sequence[Decimal]) -> tuple[Decimal, ...]:
    """`total` across `weights` to the cent, summing exactly (largest remainder); nothing to
    split when every weight is zero."""
    if total == 0 or not weights or sum(weights, Decimal(0)) == 0:
        return tuple(ZERO for _ in weights)
    return allocate(_cents(total), list(weights))


def _in_dni(line: FaiLine, determinations: Determinations) -> bool:
    if line.character == "capital_gains":
        return determinations.gains_in_dni
    return True


def compute(inputs: FiduciaryInputs) -> FiduciaryResult:
    """The year's fiduciary workpaper from its inputs (deterministic; the same inputs give the
    same result and the same `inputs_hash`)."""
    params = parameters(inputs.tax_year)
    det = inputs.determinations
    lines = inputs.fai_lines

    # 1. FAI: income lines the instrument keeps in income, less the expenses charged to income.
    income_lines = [line for line in lines if not line.to_principal]
    income_expenses = sum(
        (e.amount for e in inputs.expenses if e.charged_to == "income"), Decimal(0)
    )
    fai = _cents(sum((line.amount for line in income_lines), Decimal(0)) - income_expenses)

    # 2. DNI by character: the income items in DNI, less every deductible expense pro rata.
    income_by: dict[str, Decimal] = {c: ZERO for c in _CHARACTERS}
    qualified = ZERO
    for line in lines:
        if _in_dni(line, det):
            income_by[line.character] = _cents(income_by[line.character] + line.amount)
            if line.character == "ordinary_dividends":
                qualified = _cents(qualified + line.qualified)
    deductible = _cents(sum((e.amount for e in inputs.expenses if e.deductible), Decimal(0)))
    chars = [c for c in _CHARACTERS if income_by[c] != 0]
    shares = _split(deductible, [income_by[c] for c in chars])
    expense_by: dict[str, Decimal] = {c: ZERO for c in _CHARACTERS}
    for c, share in zip(chars, shares, strict=True):
        expense_by[c] = share
    dni_by = {c: _cents(income_by[c] - expense_by[c]) for c in _CHARACTERS}
    # The qualified subset takes its part of the dividends' expense share.
    dividends = income_by["ordinary_dividends"]
    qualified_expense = (
        _split(expense_by["ordinary_dividends"], [qualified, dividends - qualified])[0]
        if dividends != 0 and qualified != 0
        else ZERO
    )
    dni_qualified = _cents(qualified - qualified_expense)
    dni = _cents(sum(dni_by.values(), Decimal(0)))
    exempt_expense = expense_by["tax_exempt_interest"]  # IRC §265: never deductible

    # 3. IDD (IRC §661; a simple trust distributes all FAI, IRC §651).
    paid = _cents(sum((d.amount for d in inputs.distributions), Decimal(0)))
    principal_paid = _cents(
        sum((d.amount for d in inputs.distributions if d.source == "principal"), Decimal(0))
    )
    deemed = max(paid, fai) if det.entity_type == "simple_trust" else paid
    carried = min(deemed, max(dni, ZERO))
    carried_by: dict[str, Decimal] = dict(
        zip(_CHARACTERS, _carry(carried, dni, dni_by), strict=True)
    )
    exempt_carried = carried_by["tax_exempt_interest"]
    idd = _cents(carried - exempt_carried)

    # 4. Allocation by share of the distributions; boxes follow the character carried out. The
    # qualified subset carries out in the dividends' own proportion.
    carried_dividends = carried_by["ordinary_dividends"]
    dni_dividends = dni_by["ordinary_dividends"]
    qualified_carried = (
        _split(carried_dividends, [dni_qualified, dni_dividends - dni_qualified])[0]
        if carried_dividends != 0 and dni_qualified != 0 and dni_dividends > 0
        else ZERO
    )
    allocations = _allocate(inputs.distributions, carried_by, qualified_carried)

    # 5. Retained DNI, exemption, taxable income.
    retained = _cents(max(dni, ZERO) - carried)
    exemption = cast(Decimal, params.exemption[det.entity_type])
    taxable_receipts = _cents(
        sum((line.amount for line in lines if line.character != "tax_exempt_interest"), Decimal(0))
    )
    deductions = _cents(deductible - exempt_expense)
    taxable_income = _cents(taxable_receipts - deductions - idd - exemption)
    tie = sum((a.dni_allocated for a in allocations), ZERO) == idd

    inputs_stamp: Stamp = stamp(
        ENGINE_NAME, {"inputs": inputs, "parameters": [params.tax_year, params.version]}
    )
    not_distributed = _cents(max(fai - (paid - principal_paid), ZERO))
    notes: list[str] = []
    if not_distributed > 0:
        notes.append(f"fai_not_distributed:{not_distributed}")
    if principal_paid > 0:
        notes.append(f"principal_invaded:{principal_paid}")
    return FiduciaryResult(
        tax_year=inputs.tax_year,
        entity_type=det.entity_type,
        fai=fai,
        income_by_character={c: income_by[c] for c in _CHARACTERS if income_by[c] != 0},
        expense_by_character={c: expense_by[c] for c in _CHARACTERS if expense_by[c] != 0},
        dni=dni,
        dni_by_character={c: dni_by[c] for c in _CHARACTERS if dni_by[c] != 0},
        dni_qualified=dni_qualified,
        distributions=paid,
        principal_distributions=principal_paid,
        idd=idd,
        exempt_carried_out=exempt_carried,
        allocations=allocations,
        retained_dni=retained,
        fai_not_distributed=not_distributed,
        deductible_expenses=deductions,
        exemption=exemption,
        taxable_income=taxable_income,
        tie=tie,
        tree=_tree(inputs, fai, dni, dni_by, dni_qualified, expense_by, paid, idd, retained,
                   exemption, taxable_income, allocations),
        engine_name=inputs_stamp.engine_name,
        engine_version=inputs_stamp.engine_version,
        inputs_hash=inputs_stamp.inputs_hash,
        notes=tuple(notes),
    )  # fmt: skip


def _carry(carried: Decimal, dni: Decimal, dni_by: dict[str, Decimal]) -> tuple[Decimal, ...]:
    """DNI by character carried out pro rata (Treas. Reg. §1.662(b)-1), to the cent."""
    if carried == 0 or dni <= 0:
        return tuple(ZERO for _ in _CHARACTERS)
    weights = [max(dni_by[c], ZERO) for c in _CHARACTERS]
    return _split(carried, weights)


def _allocate(
    distributions: Sequence[Distribution],
    carried_by: dict[str, Decimal],
    qualified_carried: Decimal,
) -> tuple[BeneficiaryAllocation, ...]:
    """Each beneficiary's boxes: every character carried out, split by share of the
    distributions (largest remainder, so each box column sums to its carried total)."""
    order: list[str] = []
    paid_by: dict[str, Decimal] = {}
    names: dict[str, str] = {}
    for d in distributions:
        if d.beneficiary not in paid_by:
            order.append(d.beneficiary)
            paid_by[d.beneficiary] = ZERO
            names[d.beneficiary] = d.name
        paid_by[d.beneficiary] = _cents(paid_by[d.beneficiary] + d.amount)
    if not order:
        return ()
    weights = [paid_by[b] for b in order]
    total_weight = sum(weights, Decimal(0))
    split = {c: _split(carried_by[c], weights) for c in _CHARACTERS}
    qualified_split = _split(qualified_carried, weights)
    out: list[BeneficiaryAllocation] = []
    for i, beneficiary in enumerate(order):
        other = {
            _BOX_OTHER[c]: split[c][i]
            for c in ("other", "capital_gains", "tax_exempt_interest")
            if split[c][i] != 0
        }
        taxable = _cents(
            split["interest"][i]
            + split["ordinary_dividends"][i]
            + split["other"][i]
            + split["capital_gains"][i]
        )
        out.append(
            BeneficiaryAllocation(
                beneficiary=beneficiary,
                name=names[beneficiary],
                distributions=paid_by[beneficiary],
                share=(weights[i] / total_weight).quantize(Decimal("0.000001")),
                dni_allocated=taxable,
                box_1=split["interest"][i],
                box_2a=split["ordinary_dividends"][i],
                box_2b=qualified_split[i],
                box_other=other,
            )
        )
    return tuple(out)


def sixty_five_day_window(tax_year: int) -> tuple[date, date]:
    """IRC §663(b): Jan 1 to the 65th day after the calendar year-end (Mar 6, or Mar 5 in a leap
    year): TY2025 → Mar 6, 2026; TY2026 → Mar 6, 2027; TY2027 → Mar 5, 2028."""
    days = parameters(tax_year).window_days
    start = date(tax_year + 1, 1, 1)
    return start, start + timedelta(days=days - 1)


def _tree(
    inputs: FiduciaryInputs,
    fai: Decimal,
    dni: Decimal,
    dni_by: dict[str, Decimal],
    dni_qualified: Decimal,
    expense_by: dict[str, Decimal],
    paid: Decimal,
    idd: Decimal,
    retained: Decimal,
    exemption: Decimal,
    taxable_income: Decimal,
    allocations: Sequence[BeneficiaryAllocation],
) -> tuple[TreeRow, ...]:
    det = inputs.determinations
    labels = {
        "interest": "Interest",
        "ordinary_dividends": "Ordinary dividends",
        "tax_exempt_interest": "Tax-exempt interest",
        "other": "Other income",
        "capital_gains": "Capital gains",
    }
    income_rows = tuple(
        TreeRow(f"fai.{line.key}", labels[line.character], _cents(line.amount), line.clause_ref)
        for line in inputs.fai_lines
        if not line.to_principal
    )
    expense_rows = tuple(
        TreeRow(f"expense.{e.key}", "Trustee fees" if "fee" in e.key else e.key,
                _cents(e.amount), e.clause_ref)
        for e in inputs.expenses
    )  # fmt: skip
    gains = [line for line in inputs.fai_lines if line.character == "capital_gains"]
    dni_rows = [
        TreeRow(f"dni.{c}", labels[c], dni_by[c], None) for c in _CHARACTERS if dni_by[c] != 0
    ]
    if dni_qualified != 0:
        dni_rows.append(TreeRow("dni.qualified_dividends", "Qualified dividends", dni_qualified))
    if gains and not det.gains_in_dni:
        dni_rows.append(
            TreeRow("dni.capital_gains_excluded", "Capital gains (to principal)", ZERO,
                    det.gains_clause_ref)
        )  # fmt: skip
    del expense_by
    distribution_rows = tuple(
        TreeRow(f"distribution.{d.beneficiary}.{d.paid_on.isoformat()}", d.name, _cents(d.amount),
                d.clause_ref or det.distribution_clause_ref)
        for d in inputs.distributions
    )  # fmt: skip
    allocation_rows = tuple(
        TreeRow(f"allocation.{a.beneficiary}", a.name, a.dni_allocated, None) for a in allocations
    )
    return (
        TreeRow("fai", "Fiduciary accounting income", fai, None, income_rows),
        TreeRow("expenses", "Expenses", _cents(sum((e.amount for e in inputs.expenses),
                Decimal(0))), None, expense_rows),
        TreeRow("dni", "Distributable net income", dni, None, tuple(dni_rows)),
        TreeRow("distributions", "Distributions", paid, det.distribution_clause_ref,
                distribution_rows),
        TreeRow("idd", "Income distribution deduction", idd, None, allocation_rows),
        TreeRow("retained_dni", "Retained DNI", retained, det.retained_clause_ref),
        TreeRow("exemption", "Exemption", -exemption),
        TreeRow("taxable_income", "Taxable income", taxable_income),
    )  # fmt: skip
