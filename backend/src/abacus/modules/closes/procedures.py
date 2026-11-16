"""The close
run's deterministic executors, as pure functions (C-01-T20; C-01 §4.5, F3, F4; ADR-050:
code computes, models judge). Each takes plain inputs and returns its figures, its tally and the
exceptions a person must look at; the run-step handlers (`run_steps.py`) gather the inputs and
record the results. Money is `Decimal` rounded half-up to cents; nothing here reads a clock, a
table or a model, so the same inputs give the same output (`ENGINE_VERSION`, `inputs_hash`).

- `reconcile_statement`: bank ending balance ± outstanding items against the book balance
  (CLS-05): ••4410 184,236.18 + 6,412.40 - 5,658.08 = 184,990.50 = 184,610.50 + 380.00.
- `clear_third_party_sales`: a processor's gross sales less fees and refunds against the deposits
  that landed (Square 73,166.90 - 1,684.54 = 71,482.36 over 21 transfers); an unmatched transfer
  becomes a `close_treatment` decision, never a guess.
- `amortize_prepaid`: straight line over the arrangement's months (8,400 / 12 = 700), the
  schedule's ending balance against the GL (3,500 vs 2,800 is off by 700).
- `depreciate_fixed_assets`: additions under the 2,500 capitalisation threshold are expensed
  (a recategorisation proposal), the rest depreciated straight line by month.
- `recategorize`: firm rules (payee or memo contains, amount band) proposing a target account;
  the first rule that matches wins, ties broken by rule order.
- `roll_accruals`: last month's accrual reversed, this month's estimate booked; the net change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal, cast

ENGINE_VERSION: Final = "close-procedures/1.0"
CENT: Final = Decimal("0.01")
ZERO: Final = Decimal("0.00")
CAPITALISATION_THRESHOLD: Final = Decimal("2500.00")

Tally = Literal["tie", "off"]


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def inputs_hash(payload: object) -> str:
    """SHA-256 of the canonical JSON of the inputs (Decimal and date as strings)."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


# --- reconcile to statements ---------------------------------------------------------------------


@dataclass(frozen=True)
class OutstandingItem:
    side: Literal["bank", "book"]
    kind: str  # deposit_in_transit · outstanding_check · bank_fee · interest · error
    ref: str
    amount: Decimal  # signed: what it adds to its side's balance
    txn_date: date


@dataclass(frozen=True)
class Reconciliation:
    balance_per_bank: Decimal
    adjusted_bank: Decimal
    book_balance: Decimal
    adjusted_book: Decimal
    difference: Decimal
    tally: Tally
    stale_items: tuple[str, ...]  # refs outstanding longer than `stale_days`


def reconcile_statement(
    balance_per_bank: Decimal,
    book_balance: Decimal,
    items: Sequence[OutstandingItem],
    period_end: date,
    stale_days: int = 90,
) -> Reconciliation:
    bank = money(balance_per_bank + sum((i.amount for i in items if i.side == "bank"), ZERO))
    book = money(book_balance + sum((i.amount for i in items if i.side == "book"), ZERO))
    difference = money(bank - book)
    stale = tuple(sorted(i.ref for i in items if (period_end - i.txn_date).days > stale_days))
    return Reconciliation(
        money(balance_per_bank),
        bank,
        money(book_balance),
        book,
        difference,
        "tie" if difference == 0 else "off",
        stale,
    )


# --- third-party sales clearing
# -------------------------------------------------------------------


@dataclass(frozen=True)
class Payout:
    ref: str
    amount: Decimal
    on: date


@dataclass(frozen=True)
class Clearing:
    gross: Decimal
    fees: Decimal
    refunds: Decimal
    expected_net: Decimal
    deposited: Decimal
    difference: Decimal
    matched: int
    unmatched: tuple[str, ...]  # processor payouts with no deposit: a treatment decision each
    tally: Tally


def clear_third_party_sales(
    gross: Decimal,
    fees: Decimal,
    refunds: Decimal,
    payouts: Sequence[Payout],
    deposits: Sequence[Payout],
    window_days: int = 3,
) -> Clearing:
    """Each payout matches one deposit of the same amount within `window_days`; the rest stay."""
    expected = money(gross - fees - refunds)
    free = list(deposits)
    unmatched: list[str] = []
    matched = 0
    for payout in sorted(payouts, key=lambda p: (p.on, p.ref)):
        hit = next(
            (
                d
                for d in free
                if d.amount == payout.amount and abs((d.on - payout.on).days) <= window_days
            ),
            None,
        )
        if hit is None:
            unmatched.append(payout.ref)
        else:
            free.remove(hit)
            matched += 1
    deposited = money(sum((d.amount for d in deposits), ZERO))
    difference = money(expected - deposited)
    return Clearing(
        money(gross),
        money(fees),
        money(refunds),
        expected,
        deposited,
        difference,
        matched,
        tuple(unmatched),
        "tie" if difference == 0 and not unmatched else "off",
    )


# --- prepaid amortisation ---------------------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    monthly: Decimal
    months_elapsed: int
    expensed_to_date: Decimal
    ending_balance: Decimal
    gl_balance: Decimal
    off_by: Decimal
    tie: Tally


def _months(start: date, through: date) -> int:
    return max(0, (through.year - start.year) * 12 + through.month - start.month + 1)


def amortize_prepaid(
    total: Decimal, months: int, start: date, period_end: date, gl_balance: Decimal
) -> Schedule:
    """Straight line; the last month takes the rounding so the schedule foots to `total`."""
    if months <= 0:
        raise ValueError("months must be positive")
    monthly = money(total / months)
    elapsed = min(_months(start, period_end), months)
    expensed = total if elapsed == months else money(monthly * elapsed)
    ending = money(total - expensed)
    off = money(ending - gl_balance)
    return Schedule(
        monthly,
        elapsed,
        money(expensed),
        ending,
        money(gl_balance),
        off,
        "tie" if off == 0 else "off",
    )


# --- fixed assets
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Addition:
    ref: str
    cost: Decimal
    useful_life_months: int
    placed_in_service: date


@dataclass(frozen=True)
class Depreciation:
    capitalised: tuple[str, ...]
    expensed: tuple[str, ...]  # under the capitalisation threshold: a recategorisation proposal
    month_charge: Decimal


def depreciate_fixed_assets(
    additions: Sequence[Addition],
    period_end: date,
    threshold: Decimal = CAPITALISATION_THRESHOLD,
) -> Depreciation:
    capitalised: list[str] = []
    expensed: list[str] = []
    charge = ZERO
    for a in additions:
        if a.cost < threshold:
            expensed.append(a.ref)
            continue
        capitalised.append(a.ref)
        if a.placed_in_service <= period_end and a.useful_life_months > 0:
            charge += a.cost / a.useful_life_months
    return Depreciation(tuple(capitalised), tuple(expensed), money(charge))


# --- recategorisation ------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    key: str
    contains: str  # matched case-folded against payee and memo
    target_account: str
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None


@dataclass(frozen=True)
class Line:
    ref: str
    account: str
    payee: str | None
    memo: str | None
    amount: Decimal


@dataclass(frozen=True)
class Proposal:
    ref: str
    from_account: str
    to_account: str
    rule: str
    amount: Decimal


def recategorize(lines: Sequence[Line], rules: Sequence[Rule]) -> list[Proposal]:
    out: list[Proposal] = []
    for line in lines:
        words = " ".join(t for t in (line.payee, line.memo) if t).casefold()
        for rule in rules:
            if rule.contains.casefold() not in words:
                continue
            if rule.min_amount is not None and abs(line.amount) < rule.min_amount:
                continue
            if rule.max_amount is not None and abs(line.amount) > rule.max_amount:
                continue
            if rule.target_account != line.account:
                out.append(
                    Proposal(
                        line.ref, line.account, rule.target_account, rule.key, money(line.amount)
                    )
                )
            break
    return out


# --- accrual roll
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class AccrualRoll:
    reversed_prior: Decimal
    booked: Decimal
    net_change: Decimal


def roll_accruals(prior_estimate: Decimal, current_estimate: Decimal) -> AccrualRoll:
    return AccrualRoll(
        money(-prior_estimate), money(current_estimate), money(current_estimate - prior_estimate)
    )


@dataclass(frozen=True)
class Outcome:
    """What a handler records: the figures as JSON-able strings, exceptions and the hash."""

    figures: dict[str, str] = field(default_factory=dict[str, str])
    exceptions: tuple[str, ...] = ()
    tally: Tally = "tie"
    inputs_sha256: str = ""


def outcome_of(result: object, inputs: object) -> Outcome:
    raw = asdict(result)  # type: ignore[call-overload]  # a dataclass result
    figures = {k: str(v) for k, v in raw.items() if not isinstance(v, (list, tuple))}
    exceptions = tuple(
        str(x)
        for v in raw.values()
        if isinstance(v, (list, tuple))
        for x in cast("list[object] | tuple[object, ...]", v)
    )
    tally: Tally = "off" if raw.get("tally") == "off" or raw.get("tie") == "off" else "tie"
    return Outcome(figures, exceptions, tally, inputs_hash(inputs))
