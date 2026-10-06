"""SPEC-001 AC-4 to AC-7 and AC-10: accounting invariants hold for any seed (Hypothesis)."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from itertools import pairwise

from hypothesis import example, given, settings
from hypothesis import strategies as st

from abacus_tools.synthetic import (
    Account,
    Aging,
    BankStatement,
    ClientEntity,
    JournalEntry,
    TrialBalance,
    generate,
)

# --- invariant helpers (duplicated per test module: tests cannot import each other) ----------

ZERO = Decimal("0.00")
ARTEFACTS = ("general_ledger", "trial_balance", "bank_statement", "ar_aging", "ap_aging")
INVARIANTS = frozenset({"entries", "tb_balanced", "tb_ties", "bank_internal", "bank_ties"}) | {
    "ar_ties",
    "ap_ties",
}


class Ledger:
    """Cumulative GL balances (debit minus credit) by account code, cached per date."""

    def __init__(self, entity: ClientEntity) -> None:
        self._rows = [
            (entry.date, line.account_code, line.debit - line.credit)
            for entry in entity.journal_entries
            for line in entry.lines
        ]
        self._cache: dict[date, dict[str, Decimal]] = {}

    def net(self, as_of: date) -> dict[str, Decimal]:
        if as_of not in self._cache:
            totals: dict[str, Decimal] = {}
            for when, code, amount in self._rows:
                if when <= as_of:
                    totals[code] = totals.get(code, ZERO) + amount
            self._cache[as_of] = {k: v for k, v in totals.items() if v != 0}
        return self._cache[as_of]


def entry_ok(entry: JournalEntry, codes: set[str]) -> bool:
    if len(entry.lines) < 2:
        return False
    for line in entry.lines:
        if line.account_code not in codes:
            return False
        if line.debit < 0 or line.credit < 0 or (line.debit != 0 and line.credit != 0):
            return False
    return sum((x.debit for x in entry.lines), ZERO) == sum((x.credit for x in entry.lines), ZERO)


def tb_ties(tb: TrialBalance, ledger: Ledger, accounts: dict[str, Account]) -> bool:
    shown: dict[str, Decimal] = {}
    for line in tb.lines:
        if line.debit < 0 or line.credit < 0 or (line.debit != 0 and line.credit != 0):
            return False
        if line.account_code not in accounts:
            return False
        if line.account_name != accounts[line.account_code].name:
            return False
        shown[line.account_code] = shown.get(line.account_code, ZERO) + line.debit - line.credit
    return {k: v for k, v in shown.items() if v != 0} == ledger.net(tb.as_of)


def bank_internal_ok(statement: BankStatement) -> bool:
    running = statement.opening_balance
    for line in statement.lines:
        running += line.amount
        if line.balance != running:
            return False
    return running == statement.closing_balance


def bank_ties_ok(entity: ClientEntity, ledger: Ledger, statement: BankStatement) -> bool:
    gl_by_number = {b.account_number: b.gl_account_code for b in entity.bank_accounts}
    code = gl_by_number.get(statement.account_number)
    if code is None:
        return False
    deposits = sum(
        (i.amount for i in statement.reconciling_items if i.kind == "deposit_in_transit"), ZERO
    )
    cheques = sum(
        (i.amount for i in statement.reconciling_items if i.kind == "outstanding_cheque"), ZERO
    )
    cash = ledger.net(statement.period_end).get(code, ZERO)
    return cash == statement.closing_balance + deposits - cheques


def aging_ties(aging: Aging, ledger: Ledger) -> bool:
    balance = ledger.net(aging.as_of).get(aging.control_account_code, ZERO)
    return aging.total == (balance if aging.kind == "ar" else -balance)


def failures(entity: ClientEntity) -> set[str]:
    """Names of the SPEC-001 AC-4 to AC-7 invariants that do not hold for this entity."""
    ledger = Ledger(entity)
    accounts = {a.code: a for a in entity.accounts}
    out: set[str] = set()
    codes = set(accounts)
    if not all(entry_ok(e, codes) for e in entity.journal_entries):
        out.add("entries")
    for tb in entity.trial_balances:
        if tb.total_debits != tb.total_credits:
            out.add("tb_balanced")
        if not tb_ties(tb, ledger, accounts):
            out.add("tb_ties")
    previous: dict[str, BankStatement] = {}
    for statement in entity.bank_statements:
        if not bank_internal_ok(statement):
            out.add("bank_internal")
        earlier = previous.get(statement.account_number)
        if earlier is not None and earlier.closing_balance != statement.opening_balance:
            out.add("bank_continuity")
        previous[statement.account_number] = statement
        if not bank_ties_ok(entity, ledger, statement):
            out.add("bank_ties")
    if not aging_ties(entity.ar_aging, ledger):
        out.add("ar_ties")
    if not aging_ties(entity.ap_aging, ledger):
        out.add("ap_ties")
    return out


SEEDS = st.integers(min_value=0, max_value=2**32)
ENTITIES = st.integers(min_value=1, max_value=2)
MONTHS = st.integers(min_value=1, max_value=3)
LONG_MONTHS = st.integers(min_value=1, max_value=14)
# Edge starts: month start, mid-month, a weekend (Sat/Sun), Feb 29, a month end, July fiscal year.
EDGE_STARTS = [
    date(2025, 1, 1),
    date(2025, 1, 15),
    date(2025, 3, 1),
    date(2025, 3, 2),
    date(2024, 2, 29),
    date(2025, 1, 31),
    date(2024, 7, 1),
    date(2023, 7, 1),
]
STARTS = st.sampled_from(EDGE_STARTS)
PROPERTY = settings(max_examples=25, deadline=None)
LONG_PROPERTY = settings(max_examples=12, deadline=None)


def month_end(start: date, offset: int) -> date:
    index = start.year * 12 + start.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, calendar.monthrange(year, month + 1)[1])


def check_close(entity: ClientEntity, start: date, months: int) -> int:
    """After each fiscal-year-end close, revenue and expense balances are zero. Returns closes."""
    ledger = Ledger(entity)
    types = {a.code: a.type for a in entity.accounts}
    closes = 0
    for year in range(1, months // 12 + 1):
        year_end = month_end(start, 12 * year - 1)
        for code, balance in ledger.net(year_end).items():
            assert types[code] not in ("revenue", "expense"), (year_end, code, balance)
        closes += 1
    return closes


@PROPERTY
@given(seed=SEEDS, entities=ENTITIES, months=MONTHS, start=STARTS)
def test_ac4_entries_balance_and_trial_balances_equal_the_ledger(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    assert len(client.client_entities) == entities
    for entity in client.client_entities:
        assert len(entity.journal_entries) > 0
        ledger = Ledger(entity)
        accounts = {a.code: a for a in entity.accounts}
        assert entity.period_start == start
        assert [tb.as_of for tb in entity.trial_balances] == [
            month_end(start, i) for i in range(months)
        ]
        assert all(tb.client_entity == entity.name for tb in entity.trial_balances)
        for entry in entity.journal_entries:
            assert entry_ok(entry, set(accounts)), entry.id
            assert start <= entry.date <= entity.period_end
        for tb in entity.trial_balances:
            assert tb.total_debits == tb.total_credits
            assert tb_ties(tb, ledger, accounts), tb.as_of


@LONG_PROPERTY
@example(seed=1, entities=1, months=12, start=date(2025, 1, 1))
@example(seed=2, entities=1, months=13, start=date(2024, 2, 29))
@example(seed=3, entities=1, months=12, start=date(2025, 1, 15))
@example(seed=4, entities=1, months=14, start=date(2024, 7, 1))
@example(seed=5, entities=1, months=12, start=date(2025, 3, 1))
@example(seed=6, entities=1, months=12, start=date(2025, 3, 2))
@example(seed=7, entities=1, months=12, start=date(2025, 1, 31))
@given(seed=SEEDS, entities=st.just(1), months=LONG_MONTHS, start=STARTS)
def test_ac4_to_ac7_close_and_start_invariants_across_a_fiscal_year(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    for entity in client.client_entities:
        assert failures(entity) == set()
        assert min(e.date for e in entity.journal_entries) >= start
        assert entity.period_start == start
        assert [tb.as_of for tb in entity.trial_balances] == [
            month_end(start, i) for i in range(months)
        ]
        assert check_close(entity, start, months) == months // 12
        if months >= 12:
            year_end = month_end(start, 11)
            assert any(
                "close" in e.memo.lower() and e.date == year_end for e in entity.journal_entries
            )


@PROPERTY
@given(seed=SEEDS, entities=ENTITIES, months=MONTHS, start=STARTS)
def test_ac4_amounts_are_two_place_decimals(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    for entity in client.client_entities:
        amounts: list[Decimal] = []
        for entry in entity.journal_entries:
            for line in entry.lines:
                amounts += [line.debit, line.credit]
        for tb in entity.trial_balances:
            for tb_line in tb.lines:
                amounts += [tb_line.debit, tb_line.credit]
        for statement in entity.bank_statements:
            amounts += [statement.opening_balance, statement.closing_balance]
            for bank_line in statement.lines:
                amounts += [bank_line.amount, bank_line.balance]
        assert all(isinstance(a, Decimal) and a.as_tuple().exponent == -2 for a in amounts)


@PROPERTY
@given(seed=SEEDS, entities=ENTITIES, months=MONTHS, start=STARTS)
def test_ac6_bank_statements_reconcile_to_cash_after_reconciling_items(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    for entity in client.client_entities:
        ledger = Ledger(entity)
        assert len(entity.bank_accounts) >= 1
        assert len(entity.bank_statements) == months * len(entity.bank_accounts)
        for account in entity.bank_accounts:
            mine = [
                s for s in entity.bank_statements if s.account_number == account.account_number
            ]
            assert [s.period_end for s in mine] == [month_end(start, i) for i in range(months)]
            for i, statement in enumerate(mine):
                month_start = month_end(start, i).replace(day=1)
                assert statement.period_start in (month_start, max(month_start, start))
                assert statement.currency == "USD"
                assert bank_internal_ok(statement)
                assert bank_ties_ok(entity, ledger, statement)
                assert all(i2.amount > 0 for i2 in statement.reconciling_items)
                assert all(
                    statement.period_start <= x.date <= statement.period_end
                    for x in statement.lines
                )
            for before, after in pairwise(mine):
                assert before.closing_balance == after.opening_balance
        codes = {a.code: a.type for a in entity.accounts}
        assert all(codes[b.gl_account_code] == "asset" for b in entity.bank_accounts)


@PROPERTY
@given(seed=SEEDS, entities=ENTITIES, months=MONTHS, start=STARTS)
def test_ac7_agings_equal_control_accounts_at_period_end(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    for entity in client.client_entities:
        ledger = Ledger(entity)
        types = {a.code: a.type for a in entity.accounts}
        for aging, kind, control_type in (
            (entity.ar_aging, "ar", "asset"),
            (entity.ap_aging, "ap", "liability"),
        ):
            assert aging.kind == kind
            assert aging.as_of == entity.period_end
            assert types[aging.control_account_code] == control_type
            assert aging_ties(aging, ledger)
            assert aging.total == sum((x.total for x in aging.lines), ZERO)
            for line in aging.lines:
                parts = (line.current, line.days_1_30, line.days_31_60, line.days_61_90)
                assert line.total == sum(parts, ZERO) + line.over_90


@PROPERTY
@given(seed=SEEDS, entities=ENTITIES, months=MONTHS, start=STARTS)
def test_ac10_without_flaws_manifest_is_empty_and_every_invariant_holds(
    seed: int, entities: int, months: int, start: date
) -> None:
    client = generate(seed, entities=entities, months=months, start=start)
    assert client.manifest.flaws == ()
    assert client.manifest.adversarial == ()
    for entity in client.client_entities:
        assert failures(entity) == set()


@PROPERTY
@given(seed=SEEDS, months=MONTHS)
def test_ac1_generation_is_a_pure_function_of_seed_and_parameters(seed: int, months: int) -> None:
    assert generate(seed, months=months) == generate(seed, months=months)


@PROPERTY
@given(seed=SEEDS, months=MONTHS)
def test_ac11_adversarial_content_does_not_break_invariants(seed: int, months: int) -> None:
    client = generate(seed, months=months, adversarial=True)
    assert client.manifest.flaws == ()
    for entity in client.client_entities:
        assert failures(entity) == set()


def test_ac5_twelve_month_client_has_all_account_types_and_entry_kinds() -> None:
    for seed in (1, 2):
        entity = generate(seed, months=12).client_entities[0]
        assert {a.type for a in entity.accounts} == {
            "asset",
            "liability",
            "equity",
            "revenue",
            "expense",
        }
        assert len({a.code for a in entity.accounts}) == len(entity.accounts) >= 20
        assert len({e.id for e in entity.journal_entries}) == len(entity.journal_entries)
        assert len(entity.trial_balances) == 12
        text = " ".join(
            [e.memo for e in entity.journal_entries]
            + [x.description for e in entity.journal_entries for x in e.lines]
        ).lower()
        for kind in (
            ("opening",),
            ("sale", "invoice"),
            ("purchase", "bill", "vendor"),
            ("receipt", "collection"),
            ("payment", "paid"),
            ("payroll", "salar", "wage"),
            ("depreciation",),
            ("accrual", "accrued"),
            ("close",),
        ):
            assert any(word in text for word in kind), kind
        closing = [e for e in entity.journal_entries if "close" in e.memo.lower()]
        assert closing
        assert all(e.date == entity.period_end for e in closing)
        assert failures(entity) == set()
