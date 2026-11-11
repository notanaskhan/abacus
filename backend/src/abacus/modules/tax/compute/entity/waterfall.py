"""E5 part 2: the targeted waterfall (T-05-T14; T-05 §4.4, F5; SPEC-651 AC-5.4; Reg. §1.704-1(b);
ADR-050; DEC-77, DEC-4305). PROTECTED (red files of the compute package).

A targeted allocation allocates the year's income so each partner's ending 704(b) capital equals
what it would receive if the partnership sold its assets at book value and liquidated through the
agreement's distribution waterfall (a hypothetical liquidation at book value).

- **Distributable.** Book value of net assets: Σ beginning 704(b) capital plus the year's income
  to allocate (both given, whole dollars).
- **Rungs**, in priority order, each paying out of what is left:
  - `return_of_capital`: each partner's unreturned capital (its beginning capital), pro rata.
  - `preferred_return`: `rate` (a percentage) on each limited partner's unreturned capital,
    times `days / year_days` (365 by default, a full year when absent).
  - `catch_up`: the general partner takes `share` percent (100 by default) of the rung until its
    cumulative profit equals `target` percent of all profit distributed so far; the rest of the
    rung, if any, goes to the limited partners by capital.
  - `promote`: everything left, `gp` percent to the general partner and the rest to the limited
    partners by capital (a 20/80 promote is `gp: 20`).
  - `residual` and `straight_pct`: everything left, by `split` ({partner: percent}) or, when
    absent, by beginning capital.
  A rung stops when nothing is left. Anything left after the last rung is refused
  (`undistributed_remainder`).
- **Targets and the back-solve.** A partner's target is what it receives; its plug (the income
  allocated to it) is target less beginning capital. The plugs sum to the income exactly.
- **Checks.** The rungs foot to the distributable, the targets to the distributable and the plugs
  to the income; every split goes through `kernel.numeric.allocate` (largest remainder), so each
  foots exactly. The general partner's profit share is reported as a percentage of the income.
- **Preview.** The engine is pure: TXP-06 d's preview calls it with edited rungs and persists
  nothing; the service stores a result only with a saved structure version.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.entity.stamp import Stamp, stamp

ENGINE: Final = "entity.waterfall"
ZERO: Final = Decimal(0)
HUNDRED: Final = Decimal(100)
DOLLAR: Final = Decimal(1)
PartnerKind = Literal["gp", "lp"]
RuleType = Literal[
    "return_of_capital", "preferred_return", "catch_up", "promote", "residual", "straight_pct"
]


class WaterfallInvalid(ValueError):
    """The structure cannot be run: the code says why (never a partner's figures)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class WaterfallPartner:
    key: str
    kind: PartnerKind
    beginning_capital: Decimal  # 704(b), whole dollars


@dataclass(frozen=True, slots=True)
class Rung:
    priority: int
    rule_type: RuleType
    params: Mapping[str, object] = field(default_factory=dict[str, object])


@dataclass(frozen=True)
class RungResult:
    priority: int
    rule_type: RuleType
    amount: Decimal
    shares: Mapping[str, Decimal]


@dataclass(frozen=True)
class Waterfall:
    stamp: Stamp
    distributable: Decimal
    income: Decimal
    rungs: tuple[RungResult, ...]
    targets: Mapping[str, Decimal]
    plugs: Mapping[str, Decimal]
    gp_profit_percent: Decimal  # the general partners' plugs over the income, 2 places
    checks: Mapping[str, bool]


def _whole(value: Decimal, code: str) -> Decimal:
    if value != value.to_integral_value():
        raise WaterfallInvalid(code)
    return value


def _pct(params: Mapping[str, object], key: str, default: Decimal | None = None) -> Decimal:
    raw = params.get(key)
    if raw is None:
        if default is None:
            raise WaterfallInvalid(f"{key}_required")
        return default
    value = Decimal(str(raw))
    if not ZERO <= value <= HUNDRED:
        raise WaterfallInvalid(f"{key}_out_of_range")
    return value


def _split(amount: Decimal, weights: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """`amount` across `weights` in whole dollars, footing exactly; nothing when no weight."""
    keys = [k for k, w in weights.items() if w > 0]
    if amount == 0 or not keys:
        return {}
    parts = allocate(amount, [weights[k] for k in keys], places=0)
    return dict(zip(keys, parts, strict=True))


def run_waterfall(
    partners: Sequence[WaterfallPartner], rungs: Sequence[Rung], income: Decimal
) -> Waterfall:
    """The hypothetical liquidation and the back-solve (module docstring)."""
    if not partners:
        raise WaterfallInvalid("partners_required")
    if len({p.key for p in partners}) != len(partners):
        raise WaterfallInvalid("duplicate_partner")
    if not any(p.kind == "gp" for p in partners):
        raise WaterfallInvalid("general_partner_required")
    for p in partners:
        _whole(p.beginning_capital, "whole_dollars_only")
        if p.beginning_capital < 0:
            raise WaterfallInvalid("negative_capital")
    _whole(income, "whole_dollars_only")
    ordered = sorted(rungs, key=lambda r: r.priority)
    if [r.priority for r in ordered] != sorted({r.priority for r in ordered}) or not ordered:
        raise WaterfallInvalid("rung_priorities_must_be_unique")
    capital = {p.key: p.beginning_capital for p in partners}
    gps = [p.key for p in partners if p.kind == "gp"]
    lps = [p.key for p in partners if p.kind == "lp"]
    lp_capital = {k: capital[k] for k in lps}
    distributable = sum(capital.values(), ZERO) + income
    if distributable < 0:
        raise WaterfallInvalid("negative_distributable")
    remaining = distributable
    unreturned = dict(capital)
    received: dict[str, Decimal] = {p.key: ZERO for p in partners}
    profit: dict[str, Decimal] = {p.key: ZERO for p in partners}
    results: list[RungResult] = []

    def pay(rule: Rung, shares: Mapping[str, Decimal], *, is_profit: bool) -> None:
        nonlocal remaining
        amount = sum(shares.values(), ZERO)
        remaining -= amount
        for key, value in shares.items():
            received[key] += value
            if is_profit:
                profit[key] += value
        results.append(RungResult(rule.priority, rule.rule_type, amount, dict(shares)))

    for rung in ordered:
        if remaining == 0:
            results.append(RungResult(rung.priority, rung.rule_type, ZERO, {}))
            continue
        if rung.rule_type == "return_of_capital":
            owed = sum(unreturned.values(), ZERO)
            shares = _split(min(remaining, owed), unreturned)
            for key, value in shares.items():
                unreturned[key] -= value
            pay(rung, shares, is_profit=False)
        elif rung.rule_type == "preferred_return":
            rate = _pct(rung.params, "rate") / HUNDRED
            days = Decimal(str(rung.params.get("days", 365)))
            year_days = Decimal(str(rung.params.get("year_days", 365)))
            accrued = {
                k: (lp_capital[k] * rate * days / year_days).quantize(DOLLAR, ROUND_HALF_UP)
                for k in lps
            }
            owed = sum(accrued.values(), ZERO)
            paid = min(remaining, owed)
            pay(rung, accrued if paid == owed else _split(paid, accrued), is_profit=True)
        elif rung.rule_type == "catch_up":
            target = _pct(rung.params, "target") / HUNDRED
            share = _pct(rung.params, "share", HUNDRED) / HUNDRED
            if share <= target:
                raise WaterfallInvalid("catch_up_share_must_exceed_target")
            so_far = sum(profit.values(), ZERO)
            gp_so_far = sum((profit[k] for k in gps), ZERO)
            needed = max(ZERO, (target * so_far - gp_so_far) / (share - target))
            amount = min(remaining, needed.quantize(DOLLAR, ROUND_HALF_UP))
            gp_part = (amount * share).quantize(DOLLAR, ROUND_HALF_UP)
            shares = _split(gp_part, {k: capital[k] or DOLLAR for k in gps})
            for key, value in _split(amount - gp_part, lp_capital).items():
                shares[key] = shares.get(key, ZERO) + value
            pay(rung, shares, is_profit=True)
        elif rung.rule_type == "promote":
            gp_pct = _pct(rung.params, "gp") / HUNDRED
            gp_part = (remaining * gp_pct).quantize(DOLLAR, ROUND_HALF_UP)
            shares = _split(gp_part, {k: capital[k] or DOLLAR for k in gps})
            for key, value in _split(remaining - gp_part, lp_capital).items():
                shares[key] = shares.get(key, ZERO) + value
            pay(rung, shares, is_profit=True)
        else:  # residual, straight_pct
            raw = rung.params.get("split")
            weights: dict[str, Decimal] = (
                {str(k): Decimal(str(v)) for k, v in raw.items()}  # type: ignore[union-attr]  # a JSON object
                if isinstance(raw, dict)
                else dict(capital)
            )
            if any(k not in capital for k in weights):
                raise WaterfallInvalid("unknown_partner_in_split")
            pay(rung, _split(remaining, weights), is_profit=True)
    if remaining != 0:
        raise WaterfallInvalid("undistributed_remainder")
    plugs = {k: received[k] - capital[k] for k in received}
    gp_plug = sum((plugs[k] for k in gps), ZERO)
    gp_percent = (
        (gp_plug * HUNDRED / income).quantize(Decimal("0.01"), ROUND_HALF_UP) if income else ZERO
    )
    checks = {
        "rungs_foot": sum((r.amount for r in results), ZERO) == distributable,
        "targets_foot": sum(received.values(), ZERO) == distributable,
        "plugs_foot": sum(plugs.values(), ZERO) == income,
        "rung_shares_foot": all(sum(r.shares.values(), ZERO) == r.amount for r in results),
    }
    return Waterfall(
        stamp=stamp(
            ENGINE,
            {
                "partners": [
                    {"key": p.key, "kind": p.kind, "capital": p.beginning_capital}
                    for p in partners
                ],
                "rungs": [
                    {"priority": r.priority, "rule": r.rule_type, "params": dict(r.params)}
                    for r in ordered
                ],
                "income": income,
            },
        ),
        distributable=distributable,
        income=income,
        rungs=tuple(results),
        targets=dict(received),
        plugs=plugs,
        gp_profit_percent=gp_percent,
        checks=checks,
    )
