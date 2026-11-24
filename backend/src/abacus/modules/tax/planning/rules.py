"""Planning screening rules (T-08-T19; TAX-15; ADR-050; DEC-5916).

A rule is a pure function of one return's facts (the approved engine summary's lines, the form,
the filing status) and the CPA-reviewed parameters: it answers a `Candidate` (its key, category,
product kind, the title code writes and the estimate) or None. No rule reads client documents or
calls a model; the narrative is the `planning_screen` mode's (T-08-T26), on consented clients
only, and until it runs the rationale is code's template over the same figures.

Rules registered here, by form (the estimate in brackets):

- `daf_bunching` (1040): gifts at least the minimum, itemized deductions without gifts below the
  standard deduction, two years' gifts in one year itemizing above it (calculators.daf_bunching).
- `solo_401k` (1040): Schedule C net profit at least the minimum and no self-employed retirement
  deduction (the deferral at the marginal rate).
- `dependent_care_fsa` (1040): Form 2441 qualifying expenses and no employer-provided benefits
  (the smaller of the limit and the expenses at the marginal rate).
- `qcd` (1040): IRA distributions and gifts, the taxpayer reaching 70 1/2 within the planning
  years or no age on the return (none: eligibility).
- `roth_conversion` (1040): IRA or pension income, a rate at most the maximum and room below the
  next bracket at least the minimum (none: a conversation).
- `reasonable_compensation` (1120-S): ordinary income at least the minimum and officer
  compensation below the minimum share (none: risk reduction).

Every rule is a tax service to the same client (§301.7216-2(h)); a `non_tax_product` rule would
also need `other_services_use` in force (the service's consent filter).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast

from abacus.modules.tax.planning import calculators as calc
from abacus.modules.tax.planning.calculators import Estimate, FilingStatus, Parameters

ZERO: Final = Decimal(0)
ProductKind = Literal["tax_service", "non_tax_product"]


@dataclass(frozen=True)
class ReturnFacts:
    form: str
    tax_year: int
    status: FilingStatus
    lines: Mapping[str, Decimal]  # the approved engine summary, `<form>.<line>` keys
    taxpayer_age: int | None = None

    def get(self, key: str) -> Decimal:
        return self.lines.get(key, ZERO)

    def has(self, key: str) -> bool:
        return self.lines.get(key, ZERO) != ZERO


@dataclass(frozen=True)
class Candidate:
    rule_key: str
    category: str
    product_kind: ProductKind
    title: str
    estimate: Estimate
    template: str  # code's rationale, numbers by name from `estimate` (rendered by `rationale`)
    extra: Mapping[str, str] = field(default_factory=dict[str, str])  # words, not numbers


Rule = Callable[[ReturnFacts, Parameters], Candidate | None]


def _s(amount: Decimal) -> str:
    return format(amount, "f")


def _rate(facts: ReturnFacts, params: Parameters) -> Decimal:
    return calc.marginal_rate(facts.get("1040.15"), facts.status, params)


def daf_bunching(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1040":
        return None
    gifts = facts.get("scha.11")
    if gifts < params.get("daf_bunching", "min_annual_gifts"):
        return None
    standard = params.standard_deduction[facts.status]
    salt, mortgage = facts.get("scha.5e"), facts.get("scha.8a")
    found = calc.daf_bunching(
        agi=facts.get("1040.11"), salt=salt, mortgage_interest=mortgage, annual_gifts=gifts,
        rate_pct=_rate(facts, params), status=facts.status, params=params,
    )  # fmt: skip
    if salt + mortgage >= standard or not found.savings:
        return None
    first, last = params.planning_years[0], params.planning_years[-1]
    return Candidate(
        "daf_bunching", "charitable", "tax_service",
        f"Bunch {first}–{last} gifts through a donor-advised fund", found,  # noqa: RUF001
        "The client gives about {gifts} a year. Without gifts the itemized deductions would be "
        "{without_gifts}, below the {standard} standard deduction. From {first}, itemizers also "
        "lose the first 0.5% of AGI in gifts, about {floor}. Giving two years of gifts in one "
        "year through a donor-advised fund deducts {bunched} over the two years instead of "
        "{unbunched}: about {savings} at the {rate_pct}% rate.",
        {"first": str(first)},
    )  # fmt: skip


def solo_401k(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1040":
        return None
    profit = facts.get("sch1.3")
    if profit < params.get("solo_401k", "min_net_profit") or facts.has("sch1.16"):
        return None
    amount = min(params.get("solo_401k", "elective_deferral"), profit)
    found = calc.deferral_savings(
        "solo_401k", amount=amount, rate_pct=_rate(facts, params),
        inputs={"sch1.3": _s(profit), "sch1.16": "0", "1040.15": _s(facts.get("1040.15"))},
        params=params,
    )  # fmt: skip
    return Candidate(
        "solo_401k", "retirement", "tax_service", "Solo 401(k) for the consulting practice",
        found,
        "Schedule C shows a net profit of {sch1.3} and no self-employed retirement deduction. An "
        "elective deferral of {amount} to a solo 401(k) saves about {savings} at the "
        "{rate_pct}% rate.",
    )  # fmt: skip


def dependent_care_fsa(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1040":
        return None
    expenses = facts.get("f2441.3")
    if expenses <= ZERO or facts.has("f2441.12"):
        return None
    limit = params.get("dependent_care_fsa", "limit")
    found = calc.deferral_savings(
        "dependent_care_fsa", amount=min(limit, expenses), rate_pct=_rate(facts, params),
        inputs={"f2441.3": _s(expenses), "f2441.12": "0", "1040.15": _s(facts.get("1040.15"))},
        params=params,
    )  # fmt: skip
    first = params.planning_years[0]
    return Candidate(
        "dependent_care_fsa", "benefits", "tax_service",
        f"Dependent care FSA at the new {limit:,} limit ({first})", found,
        "Form 2441 shows {f2441.3} of qualifying care expenses and no employer-provided "
        "benefits. Paying {amount} through a dependent care FSA saves about {savings} at the "
        "{rate_pct}% rate.",
    )  # fmt: skip


def qcd(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1040" or not facts.has("1040.4a") or not facts.has("scha.11"):
        return None
    months = int(params.get("qcd", "min_age_months"))
    horizon = params.planning_years[-1] - facts.tax_year
    if facts.taxpayer_age is not None and (facts.taxpayer_age + horizon) * 12 < months:
        return None
    found = calc.no_estimate(
        "qcd", {"1040.4a": _s(facts.get("1040.4a")), "scha.11": _s(facts.get("scha.11"))},
        params,
    )  # fmt: skip
    return Candidate(
        "qcd", "charitable", "tax_service", "Qualified charitable distributions from the IRA",
        found,
        "The return shows IRA distributions of {1040.4a} and gifts of {scha.11}. From age 70½ "
        "gifts paid straight from the IRA leave income instead of being deducted; confirm the "
        "taxpayer's age before raising it.",
    )  # fmt: skip


def roth_conversion(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1040" or not (facts.has("1040.4b") or facts.has("1040.5b")):
        return None
    taxable = facts.get("1040.15")
    rate = _rate(facts, params)
    room = calc.bracket_room(taxable, facts.status, params)
    if rate > params.get("roth_conversion", "max_rate_pct"):
        return None
    if room < params.get("roth_conversion", "min_bracket_room"):
        return None
    found = calc.no_estimate(
        "roth_conversion", {"1040.15": _s(taxable), "1040.4b": _s(facts.get("1040.4b")),
                            "1040.5b": _s(facts.get("1040.5b"))}, params,
    )  # fmt: skip
    found = calc.Estimate(
        found.calculator, None, found.inputs,
        {"room": _s(room), "rate_pct": _s(rate)}, found.parameter_version,
    )  # fmt: skip
    return Candidate(
        "roth_conversion", "retirement", "tax_service", "Roth conversion window", found,
        "Taxable income of {1040.15} leaves {room} before the next bracket at the {rate_pct}% "
        "rate, with retirement income on the return: a partial conversion this year fills it.",
    )  # fmt: skip


def reasonable_compensation(facts: ReturnFacts, params: Parameters) -> Candidate | None:
    if facts.form != "1120s":
        return None
    comp, income = facts.get("1120s.7"), facts.get("1120s.21")
    if income < params.get("reasonable_compensation", "min_ordinary_income"):
        return None
    share = ZERO if comp + income <= ZERO else comp * 100 / (comp + income)
    if share >= params.get("reasonable_compensation", "min_comp_share_pct"):
        return None
    found = calc.no_estimate(
        "reasonable_compensation", {"1120s.7": _s(comp), "1120s.21": _s(income)}, params
    )
    found = calc.Estimate(
        found.calculator, None, found.inputs, {"share_pct": _s(calc.whole(share))},
        found.parameter_version,
    )  # fmt: skip
    return Candidate(
        "reasonable_compensation", "compliance", "tax_service",
        "Reasonable compensation review for the owner", found,
        "Officer compensation of {1120s.7} is {share_pct}% of compensation plus ordinary income "
        "of {1120s.21}: a review of the owner's pay reduces the reclassification risk.",
    )  # fmt: skip


RULES: Final[tuple[Rule, ...]] = (
    daf_bunching, solo_401k, dependent_care_fsa, qcd, roth_conversion, reasonable_compensation,
)  # fmt: skip


def screen(facts: ReturnFacts, params: Parameters) -> list[Candidate]:
    """Every registered rule over the return, in registry order."""
    return [c for rule in RULES if (c := rule(facts, params)) is not None]


def _money(raw: str) -> str:
    try:
        return f"{calc.whole(Decimal(raw)):,}"
    except InvalidOperation:
        return raw


def rationale(candidate: Candidate) -> str:
    """Code's template filled from the estimate's inputs and figures (whole dollars)."""
    est = candidate.estimate
    values: dict[str, str] = {}
    for key, raw in {**est.inputs, **est.figures}.items():
        values[key] = raw if key.endswith("_pct") else _money(raw)
    values["gifts"] = values.get("scha.11", "")
    if est.savings is not None:
        values["savings"] = f"{est.savings:,}"
    values |= candidate.extra
    text = candidate.template
    for key in sorted(values, key=len, reverse=True):
        text = text.replace("{" + key + "}", values[key])
    return text


def facts_from_lines(
    form: str, tax_year: int, status: FilingStatus, lines: object, age: int | None = None
) -> ReturnFacts:
    """The engine summary's `lines` (`[{line_key, amount}]`) as facts."""
    found: dict[str, Decimal] = {}
    for raw in cast("list[object]", lines) if isinstance(lines, list) else []:
        if not isinstance(raw, dict):
            continue
        entry = cast("dict[str, object]", raw)
        key, amount = entry.get("line_key"), entry.get("amount")
        if isinstance(key, str) and amount is not None:
            try:
                found[key] = Decimal(str(amount))
            except InvalidOperation:
                continue
    return ReturnFacts(form, tax_year, status, found, age)


__all__ = ["RULES", "Candidate", "ReturnFacts", "facts_from_lines", "rationale", "screen"]
