"""Failure-taxonomy flaws (SPEC-001 AC-8 to AC-10; docs/product/failure-taxonomy.md).

Flaws are applied to copies of derived artefacts of the first client entity, never to the books, so
every invariant not involving the flawed artefact still holds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from random import Random

from abacus_tools.synthetic.artefacts import (
    aging,
    balances_at,
    previous_month_end,
    trial_balance_from,
)
from abacus_tools.synthetic.ledger import Books
from abacus_tools.synthetic.model import (
    Aging,
    BankLine,
    BankStatement,
    ClientEntity,
    Flaw,
    ReconcilingItem,
    RequestList,
    TrialBalance,
    money,
)

FAILURE_CATEGORIES: tuple[str, ...] = (
    "wrong_period",
    "wrong_entity",
    "incomplete",
    "unbalanced",
    "does_not_tie",
    "duplicate",
    "stale",
    "wrong_currency",
    "altered",
    "irrelevant",
    "unreadable",
)
ARTEFACTS: tuple[str, ...] = (
    "general_ledger",
    "trial_balance",
    "bank_statement",
    "ar_aging",
    "ap_aging",
)
# Allowed artefacts per category in SPEC-001 §7 table order; the first is the default target.
TARGETS: dict[str, tuple[str, ...]] = {
    "wrong_period": ("trial_balance", "bank_statement", "ar_aging", "ap_aging"),
    "wrong_entity": ("trial_balance", "bank_statement"),
    "incomplete": ("general_ledger", "bank_statement"),
    "unbalanced": ("trial_balance",),
    "does_not_tie": ("ar_aging", "ap_aging", "bank_statement"),
    "duplicate": ("general_ledger", "bank_statement"),
    "stale": ("trial_balance", "ar_aging", "ap_aging"),
    "wrong_currency": ("bank_statement",),
    "altered": ("bank_statement", "ar_aging", "ap_aging"),
    "irrelevant": ("general_ledger", "bank_statement", "ar_aging", "ap_aging"),
    "unreadable": ARTEFACTS,
}
EUR_PER_USD = Decimal("0.92")


@dataclass(frozen=True)
class FlawRequest:
    category: str
    artefact: str


@dataclass
class Context:
    entity: ClientEntity
    books: Books
    requests: RequestList
    rng: Random
    decoy: Callable[[], ClientEntity]


def parse(flaws: Sequence[str]) -> tuple[FlawRequest, ...]:
    requests: list[FlawRequest] = []
    for raw in flaws:
        category, _, artefact = raw.partition(":")
        if category not in TARGETS:
            raise ValueError(
                f"unknown flaw category {category!r}; valid: {', '.join(FAILURE_CATEGORIES)}"
            )
        allowed = TARGETS[category]
        target = artefact or allowed[0]
        if target not in ARTEFACTS:
            raise ValueError(f"unknown artefact {target!r}; valid: {', '.join(ARTEFACTS)}")
        if target not in allowed:
            raise ValueError(
                f"flaw {category!r} cannot target {target!r}; valid: {', '.join(allowed)}"
            )
        if any(r.artefact == target for r in requests):
            raise ValueError(f"two flaws target {target!r}; at most one flaw per artefact")
        requests.append(FlawRequest(category, target))
    return tuple(requests)


def apply(
    ctx: Context, flaws: tuple[FlawRequest, ...]
) -> tuple[ClientEntity, RequestList, tuple[Flaw, ...]]:
    records: list[Flaw] = []
    for flaw in flaws:
        where = location(ctx.entity, flaw.artefact)
        if flaw.category == "irrelevant":
            where = f"request_item {_tb_request_id(ctx.requests)} served {flaw.artefact}"
        _APPLY[flaw.category](ctx, flaw.artefact)
        detection = "ai" if flaw.category == "irrelevant" else "mechanical"
        records.append(Flaw(flaw.category, flaw.artefact, ctx.entity.name, where, detection))
    return ctx.entity, ctx.requests, tuple(records)


def location(entity: ClientEntity, artefact: str) -> str:
    if artefact == "trial_balance":
        return f"trial_balance {entity.period_end.isoformat()}"
    if artefact == "bank_statement":
        return f"bank_statement {entity.bank_accounts[0].account_number} for {entity.period_end:%Y-%m}"
    if artefact in ("ar_aging", "ap_aging"):
        return f"{artefact} {entity.period_end.isoformat()}"
    return "general_ledger"


def last_statement_index(entity: ClientEntity) -> int:
    """Position of the first bank account's period-end statement.

    Statements are ordered by bank account, then month, so this is positional: it stays correct
    after a flaw rewrites the statement's dates or account number.
    """
    return len(entity.trial_balances) - 1


def minus_year(d: date) -> date:
    return d.replace(year=d.year - 1, day=28 if (d.month, d.day) == (2, 29) else d.day)


# --- accessors ---------------------------------------------------------------------------------


def _tb(ctx: Context) -> TrialBalance:
    return ctx.entity.trial_balances[-1]


def _set_tb(ctx: Context, tb: TrialBalance) -> None:
    ctx.entity = replace(ctx.entity, trial_balances=(*ctx.entity.trial_balances[:-1], tb))


def _statement(ctx: Context) -> BankStatement:
    return ctx.entity.bank_statements[last_statement_index(ctx.entity)]


def _set_statement(ctx: Context, statement: BankStatement) -> None:
    i = last_statement_index(ctx.entity)
    statements = ctx.entity.bank_statements
    ctx.entity = replace(
        ctx.entity, bank_statements=(*statements[:i], statement, *statements[i + 1 :])
    )


def _aging(ctx: Context, artefact: str) -> Aging:
    return ctx.entity.ar_aging if artefact == "ar_aging" else ctx.entity.ap_aging


def _set_aging(ctx: Context, artefact: str, value: Aging) -> None:
    field = "ar_aging" if artefact == "ar_aging" else "ap_aging"
    ctx.entity = replace(ctx.entity, **{field: value})


def _amount(ctx: Context) -> Decimal:
    return money(ctx.rng.randint(10_000, 500_000))


def _tb_request_id(requests: RequestList) -> str:
    return next(item.id for item in requests.items if item.artefact == "trial_balance")


# --- categories --------------------------------------------------------------------------------


def _wrong_period(ctx: Context, artefact: str) -> None:
    if artefact == "trial_balance":
        _set_tb(ctx, replace(_tb(ctx), as_of=minus_year(_tb(ctx).as_of)))
    elif artefact == "bank_statement":
        s = _statement(ctx)
        lines = tuple(replace(ln, date=minus_year(ln.date)) for ln in s.lines)
        _set_statement(
            ctx,
            replace(
                s,
                period_start=minus_year(s.period_start),
                period_end=minus_year(s.period_end),
                lines=lines,
            ),
        )
    else:
        a = _aging(ctx, artefact)
        _set_aging(ctx, artefact, replace(a, as_of=minus_year(a.as_of)))


def _wrong_entity(ctx: Context, artefact: str) -> None:
    other = ctx.decoy()
    if artefact == "trial_balance":
        _set_tb(ctx, other.trial_balances[-1])
    else:
        _set_statement(ctx, other.bank_statements[last_statement_index(other)])


def _incomplete(ctx: Context, artefact: str) -> None:
    if artefact == "general_ledger":
        months = sorted({(e.date.year, e.date.month) for e in ctx.entity.journal_entries})
        year, month = months[ctx.rng.randrange(len(months))]
        kept = tuple(
            e for e in ctx.entity.journal_entries if (e.date.year, e.date.month) != (year, month)
        )
        ctx.entity = replace(ctx.entity, journal_entries=kept)
    else:
        s = _statement(ctx)
        i = ctx.rng.randrange(len(s.lines))
        _set_statement(ctx, replace(s, lines=(*s.lines[:i], *s.lines[i + 1 :])))


def _unbalanced(ctx: Context, artefact: str) -> None:
    del artefact
    tb = _tb(ctx)
    i = next(n for n, ln in enumerate(tb.lines) if ln.debit > 0)
    line = replace(tb.lines[i], debit=tb.lines[i].debit + _amount(ctx))
    _set_tb(ctx, replace(tb, lines=(*tb.lines[:i], line, *tb.lines[i + 1 :])))


def _does_not_tie(ctx: Context, artefact: str) -> None:
    if artefact == "bank_statement":
        s = _statement(ctx)
        if s.reconciling_items:
            items = s.reconciling_items[1:]
        else:
            items = (ReconcilingItem("deposit_in_transit", "DEPOSIT", _amount(ctx)),)
        _set_statement(ctx, replace(s, reconciling_items=items))
    else:
        a = _aging(ctx, artefact)
        extra = _amount(ctx)
        first = a.lines[0]
        line = replace(first, current=first.current + extra, total=first.total + extra)
        _set_aging(ctx, artefact, replace(a, lines=(line, *a.lines[1:])))


def _duplicate(ctx: Context, artefact: str) -> None:
    if artefact == "general_ledger":
        entries = ctx.entity.journal_entries
        i = ctx.rng.randrange(len(entries))
        ctx.entity = replace(
            ctx.entity, journal_entries=(*entries[: i + 1], entries[i], *entries[i + 1 :])
        )
    else:
        s = _statement(ctx)
        i = ctx.rng.randrange(len(s.lines))
        _set_statement(ctx, replace(s, lines=(*s.lines[: i + 1], s.lines[i], *s.lines[i + 1 :])))


def _stale(ctx: Context, artefact: str) -> None:
    earlier = previous_month_end(ctx.entity.period_end)
    if artefact == "trial_balance":
        _set_tb(ctx, trial_balance_from(balances_at(ctx.books.entries, earlier), earlier))
    else:
        items = ctx.books.receivables if artefact == "ar_aging" else ctx.books.payables
        _set_aging(ctx, artefact, aging("ar" if artefact == "ar_aging" else "ap", items, earlier))


def _wrong_currency(ctx: Context, artefact: str) -> None:
    del artefact
    s = _statement(ctx)

    def fx(value: Decimal) -> Decimal:
        return money(value * EUR_PER_USD)

    lines = tuple(
        BankLine(ln.date, ln.description, fx(ln.amount), fx(ln.balance)) for ln in s.lines
    )
    items = tuple(replace(item, amount=fx(item.amount)) for item in s.reconciling_items)
    _set_statement(
        ctx,
        replace(
            s,
            opening_balance=fx(s.opening_balance),
            closing_balance=fx(s.closing_balance),
            lines=lines,
            reconciling_items=items,
        ),
    )


def _altered(ctx: Context, artefact: str) -> None:
    if artefact == "bank_statement":
        s = _statement(ctx)
        i = ctx.rng.randrange(len(s.lines))
        line = replace(s.lines[i], balance=s.lines[i].balance + _amount(ctx))
        _set_statement(ctx, replace(s, lines=(*s.lines[:i], line, *s.lines[i + 1 :])))
    else:
        a = _aging(ctx, artefact)
        first = a.lines[0]
        _set_aging(
            ctx,
            artefact,
            replace(a, lines=(replace(first, current=first.current + _amount(ctx)), *a.lines[1:])),
        )


def _irrelevant(ctx: Context, artefact: str) -> None:
    items = tuple(
        replace(item, artefact=artefact) if item.artefact == "trial_balance" else item
        for item in ctx.requests.items
    )
    ctx.requests = RequestList(items)


def _unreadable(ctx: Context, artefact: str) -> None:
    del ctx, artefact  # the exporter writes the artefact's file empty, guided by the manifest


_APPLY: dict[str, Callable[[Context, str], None]] = {
    "wrong_period": _wrong_period,
    "wrong_entity": _wrong_entity,
    "incomplete": _incomplete,
    "unbalanced": _unbalanced,
    "does_not_tie": _does_not_tie,
    "duplicate": _duplicate,
    "stale": _stale,
    "wrong_currency": _wrong_currency,
    "altered": _altered,
    "irrelevant": _irrelevant,
    "unreadable": _unreadable,
}
