"""SPEC-001 AC-8, AC-9: every flaw category on every allowed artefact, labelled and contained."""

from __future__ import annotations

import calendar
import dataclasses
import json
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from abacus_tools.synthetic import (
    FAILURE_CATEGORIES,
    Account,
    Aging,
    AgingLine,
    BankStatement,
    ClientEntity,
    JournalEntry,
    SyntheticClient,
    TrialBalance,
    generate,
    to_csv,
    to_json,
    to_xlsx,
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


SEED = 17
CURRENT = [3]  # months of the current run; every test runs at 3 months and at 1 month

# SPEC-001 section 7 table; "aging" means either aging, "any" means every artefact.
ALLOWED: dict[str, tuple[str, ...]] = {
    "wrong_period": ("trial_balance", "bank_statement", "ar_aging", "ap_aging"),
    "wrong_entity": ("trial_balance", "bank_statement"),
    "incomplete": ("general_ledger", "bank_statement"),
    "unbalanced": ("trial_balance",),
    "does_not_tie": ("ar_aging", "ap_aging", "bank_statement"),
    "duplicate": ("general_ledger", "bank_statement"),
    "stale": ("trial_balance", "ar_aging", "ap_aging"),
    "wrong_currency": ("bank_statement",),
    "altered": ("bank_statement", "ar_aging", "ap_aging"),
    # irrelevant:trial_balance raises: serving the TB for the TB request is not irrelevant.
    "irrelevant": tuple(a for a in ARTEFACTS if a != "trial_balance"),
    "unreadable": ARTEFACTS,
}
DEFAULT_ARTEFACT = {
    "wrong_period": "trial_balance",
    "wrong_entity": "trial_balance",
    "incomplete": "general_ledger",
    "unbalanced": "trial_balance",
    "does_not_tie": "ar_aging",
    "duplicate": "general_ledger",
    "stale": "trial_balance",
    "wrong_currency": "bank_statement",
    "altered": "bank_statement",
    "irrelevant": "general_ledger",
    "unreadable": "general_ledger",
}
CASES = [(c, a) for c, artefacts in ALLOWED.items() for a in artefacts]
DISALLOWED = [(c, a) for c in ALLOWED for a in ARTEFACTS if a not in ALLOWED[c]]
# Invariants that may legitimately fail because the named artefact is the flawed one.
RELATED: dict[str, set[str]] = {
    "general_ledger": {"tb_ties", "bank_ties", "ar_ties", "ap_ties"},
    "trial_balance": {"tb_balanced", "tb_ties"},
    "bank_statement": {"bank_internal", "bank_continuity", "bank_ties"},
    "ar_aging": {"ar_ties"},
    "ap_aging": {"ap_ties"},
}
ENTITY_FIELD = {
    "general_ledger": "journal_entries",
    "trial_balance": "trial_balances",
    "bank_statement": "bank_statements",
    "ar_aging": "ar_aging",
    "ap_aging": "ap_aging",
}
READ_ONLY_FLAWS = ("irrelevant", "unreadable")


@pytest.fixture(autouse=True, params=[3, 1], ids=["months3", "months1"])
def months_in_use(request: pytest.FixtureRequest) -> int:
    CURRENT[0] = int(request.param)
    return CURRENT[0]


@cache
def build_months(flaws: tuple[str, ...], entities: int, months: int) -> SyntheticClient:
    return generate(SEED, entities=entities, months=months, flaws=flaws)


def build(flaws: tuple[str, ...] = (), entities: int = 1) -> SyntheticClient:
    return build_months(flaws, entities, CURRENT[0])


def period_end() -> date:
    year, month = 2025, CURRENT[0]
    return date(year, month, calendar.monthrange(year, month)[1])


def stale_tb_rejected(flaws: tuple[str, ...]) -> bool:
    """With one month there is no earlier month end, so a stale trial balance is rejected."""
    return CURRENT[0] == 1 and any(f in ("stale", "stale:trial_balance") for f in flaws)


def expect_rejected(flaws: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        build(flaws)


def spec(category: str, artefact: str) -> tuple[str, ...]:
    return (f"{category}:{artefact}",)


def bank_target(entity: ClientEntity) -> int:
    """Index of the last month's statement of the first bank account."""
    number = entity.bank_accounts[0].account_number
    mine = [i for i, s in enumerate(entity.bank_statements) if s.account_number == number]
    return max(mine, key=lambda i: entity.bank_statements[i].period_end)


def differing(a: tuple[object, ...], b: tuple[object, ...]) -> list[int]:
    assert len(a) == len(b)
    return [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]


def one_year_earlier(d: date) -> date:
    return d.replace(year=d.year - 1)


def month_index(d: date) -> int:
    return d.year * 12 + d.month


def aging_of(entity: ClientEntity, artefact: str) -> Aging:
    return entity.ar_aging if artefact == "ar_aging" else entity.ap_aging


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = parse_xml(archive.read("xl/workbook.xml"))
    return [el.attrib["name"] for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "sheet"]


def target_csv_name(entity: ClientEntity, artefact: str) -> str:
    if artefact == "general_ledger":
        return "general_ledger.csv"
    if artefact == "trial_balance":
        return f"trial_balance_{entity.trial_balances[-1].as_of.isoformat()}.csv"
    if artefact == "bank_statement":
        s = entity.bank_statements[bank_target(entity)]
        return f"bank_statement_{s.account_number}_{s.period_end:%Y-%m}.csv"
    return f"{artefact}.csv"


# --- AC-8: the manifest ----------------------------------------------------------------------


def test_ac8_every_category_has_an_allowed_artefact_table_entry() -> None:
    assert set(ALLOWED) == set(FAILURE_CATEGORIES)


@pytest.mark.parametrize(("category", "artefact"), CASES)
def test_ac8_manifest_lists_exactly_the_requested_flaw(category: str, artefact: str) -> None:
    if stale_tb_rejected(spec(category, artefact)):
        return expect_rejected(spec(category, artefact))
    client = build(spec(category, artefact))
    entity = client.client_entities[0]
    assert client.manifest.adversarial == ()
    assert len(client.manifest.flaws) == 1
    flaw = client.manifest.flaws[0]
    assert flaw.category == category
    assert flaw.artefact == artefact
    assert flaw.client_entity == entity.name
    assert flaw.detection == ("ai" if category == "irrelevant" else "mechanical")
    assert flaw.location.strip() != ""
    if category != "irrelevant":
        assert artefact in flaw.location


@pytest.mark.parametrize(("category", "artefact"), list(DEFAULT_ARTEFACT.items()))
def test_ac8_plain_category_targets_its_first_artefact(category: str, artefact: str) -> None:
    if stale_tb_rejected((category,)):
        return expect_rejected((category,))
    client = build((category,))
    assert [(f.category, f.artefact) for f in client.manifest.flaws] == [(category, artefact)]
    assert client == build(spec(category, artefact))


def test_ac8_no_flaws_means_empty_manifest_and_unchanged_output() -> None:
    assert build().manifest.flaws == ()
    assert generate(SEED, months=CURRENT[0], flaws=[]) == build()


def test_ac8_several_compatible_flaws_are_all_injected() -> None:
    flaws = ("incomplete", "unbalanced", "altered", "does_not_tie", "stale:ap_aging")
    client = build(flaws)
    entity = client.client_entities[0]
    got = {(f.category, f.artefact) for f in client.manifest.flaws}
    assert len(client.manifest.flaws) == 5
    assert got == {
        ("incomplete", "general_ledger"),
        ("unbalanced", "trial_balance"),
        ("altered", "bank_statement"),
        ("does_not_tie", "ar_aging"),
        ("stale", "ap_aging"),
    }
    related = {name for names in RELATED.values() for name in names}
    assert failures(entity) <= related
    assert {"entries"} & failures(entity) == set()


def test_ac8_same_category_on_different_artefacts_is_allowed() -> None:
    client = build(("wrong_period:trial_balance", "wrong_period:bank_statement"))
    assert [(f.category, f.artefact) for f in client.manifest.flaws] == [
        ("wrong_period", "trial_balance"),
        ("wrong_period", "bank_statement"),
    ]


@pytest.mark.parametrize(("category", "artefact"), DISALLOWED)
def test_ac8_flaw_on_an_artefact_it_cannot_target_raises(category: str, artefact: str) -> None:
    with pytest.raises(ValueError) as info:
        generate(SEED, months=1, flaws=spec(category, artefact))
    assert all(valid in str(info.value) for valid in ALLOWED[category])


# --- AC-8 / AC-9: containment ----------------------------------------------------------------


@pytest.mark.parametrize(("category", "artefact"), CASES)
def test_ac9_only_the_named_artefact_changes_and_unrelated_invariants_hold(
    category: str, artefact: str
) -> None:
    if stale_tb_rejected(spec(category, artefact)):
        return expect_rejected(spec(category, artefact))
    base = build((), entities=2)
    client = build(spec(category, artefact), entities=2)
    base0, entity = base.client_entities[0], client.client_entities[0]
    assert client.client_entities[1] == base.client_entities[1]
    assert failures(client.client_entities[1]) == set()
    assert failures(base0) == set()
    if category in READ_ONLY_FLAWS:
        assert entity == base0
        assert failures(entity) == set()
        return
    field = ENTITY_FIELD[artefact]
    assert getattr(entity, field) != getattr(base0, field)
    restored = dataclasses.replace(entity, **{field: getattr(base0, field)})
    assert restored == base0
    assert client.request_list == base.request_list
    assert failures(entity) <= RELATED[artefact]


@pytest.mark.parametrize("category", ["wrong_period", "stale", "unbalanced", "wrong_entity"])
def test_ac9_trial_balance_flaw_touches_only_the_period_end_trial_balance(category: str) -> None:
    if stale_tb_rejected(spec(category, "trial_balance")):
        return expect_rejected(spec(category, "trial_balance"))
    base = build().client_entities[0]
    flawed = build(spec(category, "trial_balance")).client_entities[0]
    assert differing(flawed.trial_balances, base.trial_balances) == [CURRENT[0] - 1]


@pytest.mark.parametrize(
    "category",
    [c for c, arts in ALLOWED.items() if "bank_statement" in arts and c not in READ_ONLY_FLAWS],
)
def test_ac9_bank_flaw_touches_only_the_last_statement_of_the_first_account(
    category: str,
) -> None:
    base = build().client_entities[0]
    flawed = build(spec(category, "bank_statement")).client_entities[0]
    assert differing(flawed.bank_statements, base.bank_statements) == [bank_target(base)]


# --- flaw effects ----------------------------------------------------------------------------


def test_ac9_unbalanced_trial_balance_only_and_general_ledger_stays_balanced() -> None:
    base = build().client_entities[0]
    entity = build(("unbalanced",)).client_entities[0]
    tb = entity.trial_balances[-1]
    assert tb.total_debits != tb.total_credits
    assert all(t.total_debits == t.total_credits for t in entity.trial_balances[:-1])
    assert entity.journal_entries == base.journal_entries
    assert all(entry_ok(e, {a.code for a in entity.accounts}) for e in entity.journal_entries)
    assert failures(entity) >= {"tb_balanced"}
    assert failures(entity) <= {"tb_balanced", "tb_ties"}


@pytest.mark.parametrize("artefact", ALLOWED["wrong_period"])
def test_ac8_wrong_period_moves_the_artefact_one_year_earlier(artefact: str) -> None:
    base = build().client_entities[0]
    entity = build(spec("wrong_period", artefact)).client_entities[0]
    if artefact == "trial_balance":
        assert entity.trial_balances[-1].as_of == one_year_earlier(base.trial_balances[-1].as_of)
    elif artefact == "bank_statement":
        before = base.bank_statements[bank_target(base)]
        after = entity.bank_statements[bank_target(base)]
        assert after.period_start == one_year_earlier(before.period_start)
        assert after.period_end == one_year_earlier(before.period_end)
    else:
        assert aging_of(entity, artefact).as_of == one_year_earlier(period_end())


@pytest.mark.parametrize("artefact", ALLOWED["stale"])
def test_ac8_stale_as_of_is_at_least_a_month_before_period_end(artefact: str) -> None:
    if stale_tb_rejected(spec("stale", artefact)):
        return expect_rejected(spec("stale", artefact))
    entity = build(spec("stale", artefact)).client_entities[0]
    as_of = entity.trial_balances[-1].as_of if artefact == "trial_balance" else None
    if as_of is None:
        as_of = aging_of(entity, artefact).as_of
    assert month_index(period_end()) - month_index(as_of) >= 1
    assert as_of < period_end()


def test_ac8_wrong_entity_trial_balance_does_not_belong_to_the_entity() -> None:
    base = build().client_entities[0]
    entity = build(("wrong_entity",)).client_entities[0]
    assert entity.trial_balances[-1] != base.trial_balances[-1]
    assert "tb_ties" in failures(entity)


@pytest.mark.parametrize("entities", [1, 2])
def test_ac8_wrong_entity_bank_statement_uses_a_foreign_account_number(entities: int) -> None:
    base = build((), entities).client_entities[0]
    entity = build(spec("wrong_entity", "bank_statement"), entities).client_entities[0]
    statement = entity.bank_statements[bank_target(base)]
    assert statement.account_number not in {b.account_number for b in entity.bank_accounts}
    assert "bank_ties" in failures(entity)


def test_ac8_incomplete_general_ledger_has_a_month_without_entries() -> None:
    base = build().client_entities[0]
    entity = build(("incomplete",)).client_entities[0]
    wanted = {(2025, m) for m in range(1, CURRENT[0] + 1)}
    assert {(e.date.year, e.date.month) for e in base.journal_entries} >= wanted
    assert not wanted <= {(e.date.year, e.date.month) for e in entity.journal_entries}
    assert len(entity.journal_entries) < len(base.journal_entries)


def test_ac8_incomplete_bank_statement_has_a_line_removed() -> None:
    base = build().client_entities[0]
    entity = build(spec("incomplete", "bank_statement")).client_entities[0]
    index = bank_target(base)
    assert len(entity.bank_statements[index].lines) < len(base.bank_statements[index].lines)
    assert failures(entity) & {"bank_internal", "bank_continuity", "bank_ties"}


@pytest.mark.parametrize("artefact", ["ar_aging", "ap_aging"])
def test_ac8_does_not_tie_aging_total_differs_from_control_account(artefact: str) -> None:
    entity = build(spec("does_not_tie", artefact)).client_entities[0]
    assert not aging_ties(aging_of(entity, artefact), Ledger(entity))
    assert failures(entity) == {artefact.replace("aging", "ties")}


def test_ac8_does_not_tie_bank_statement_fails_the_cash_reconciliation() -> None:
    entity = build(spec("does_not_tie", "bank_statement")).client_entities[0]
    assert "bank_ties" in failures(entity)


def test_ac8_duplicate_general_ledger_repeats_an_entry_id() -> None:
    base = build().client_entities[0]
    entity = build(("duplicate",)).client_entities[0]
    assert max(Counter(e.id for e in base.journal_entries).values()) == 1
    assert max(Counter(e.id for e in entity.journal_entries).values()) >= 2
    assert all(entry_ok(e, {a.code for a in entity.accounts}) for e in entity.journal_entries)


def test_ac8_duplicate_bank_statement_repeats_a_line() -> None:
    base = build().client_entities[0]
    entity = build(spec("duplicate", "bank_statement")).client_entities[0]
    index = bank_target(base)

    def surplus(statement: BankStatement) -> int:
        keys = Counter((x.date, x.description, x.amount) for x in statement.lines)
        return sum(n - 1 for n in keys.values())

    assert len(entity.bank_statements[index].lines) > len(base.bank_statements[index].lines)
    assert surplus(entity.bank_statements[index]) > surplus(base.bank_statements[index])


def test_ac8_wrong_currency_keeps_usd_label_but_amounts_do_not_reconcile() -> None:
    base = build().client_entities[0]
    entity = build(("wrong_currency",)).client_entities[0]
    index = bank_target(base)
    statement = entity.bank_statements[index]
    assert statement.currency == "USD"
    assert statement != base.bank_statements[index]
    assert "bank_ties" in failures(entity)
    # Contract revision 1: the converted statement is internally consistent.
    assert bank_internal_ok(statement)
    assert "bank_internal" not in failures(entity)
    assert failures(entity) <= {"bank_ties", "bank_continuity"}


def test_ac8_altered_bank_statement_has_an_inconsistent_running_balance() -> None:
    entity = build(("altered",)).client_entities[0]
    assert "bank_internal" in failures(entity)


@pytest.mark.parametrize("artefact", ["ar_aging", "ap_aging"])
def test_ac8_altered_aging_has_a_line_whose_buckets_do_not_sum_to_its_total(
    artefact: str,
) -> None:
    base = build().client_entities[0]
    entity = build(spec("altered", artefact)).client_entities[0]
    aging = aging_of(entity, artefact)
    assert aging != aging_of(base, artefact)
    assert aging.as_of == aging_of(base, artefact).as_of

    def bucket_sum(x: AgingLine) -> Decimal:
        return x.current + x.days_1_30 + x.days_31_60 + x.days_61_90 + x.over_90

    assert any(x.total != bucket_sum(x) for x in aging.lines)
    assert all(x.total == bucket_sum(x) for x in aging_of(base, artefact).lines)


@pytest.mark.parametrize("artefact", ALLOWED["irrelevant"])
def test_ac8_irrelevant_repoints_the_trial_balance_request_item(artefact: str) -> None:
    base = build()
    client = build(spec("irrelevant", artefact))
    (tb_item,) = [i for i in base.request_list.items if i.artefact == "trial_balance"]
    after = {i.id: i for i in client.request_list.items}
    assert after[tb_item.id].artefact != "trial_balance"
    assert after[tb_item.id].artefact in ARTEFACTS
    assert [i.id for i in client.request_list.items] == [i.id for i in base.request_list.items]
    others = [i for i in base.request_list.items if i.id != tb_item.id]
    assert [after[i.id] for i in others] == others


# --- unreadable: exports ---------------------------------------------------------------------


@pytest.mark.parametrize("artefact", ARTEFACTS)
def test_ac8_unreadable_artefact_exports_an_empty_csv_and_no_xlsx_sheet(
    tmp_path: Path, artefact: str
) -> None:
    base = build()
    client = build(spec("unreadable", artefact))
    for name, c in (("base", base), ("flawed", client)):
        (tmp_path / name).mkdir()
        to_csv(c, tmp_path / name)
        to_xlsx(c, tmp_path / f"{name}.xlsx")
    base_files = {p.relative_to(tmp_path / "base") for p in (tmp_path / "base").rglob("*.csv")}
    flawed_files = {
        p.relative_to(tmp_path / "flawed") for p in (tmp_path / "flawed").rglob("*.csv")
    }
    assert flawed_files == base_files
    entity = client.client_entities[0]
    (entity_dir,) = [p for p in (tmp_path / "flawed").iterdir() if p.is_dir()]
    target = entity_dir / target_csv_name(entity, artefact)
    assert target.is_file()
    assert target.stat().st_size == 0
    for path in entity_dir.glob("*.csv"):
        if path != target:
            assert path.stat().st_size > 0, path.name
    base_sheets = sheet_names(tmp_path / "base.xlsx")
    flawed_sheets = sheet_names(tmp_path / "flawed.xlsx")
    assert len(flawed_sheets) == len(base_sheets) - 1
    assert set(flawed_sheets) < set(base_sheets)
    (tmp_path / "json").mkdir()
    data = json.loads(to_json(client, tmp_path / "json").read_text(encoding="utf-8"))
    assert data["manifest"]["flaws"][0]["category"] == "unreadable"


# --- conflicts and validation ----------------------------------------------------------------


@pytest.mark.parametrize(
    "flaws",
    [
        ("unbalanced", "unreadable:trial_balance"),
        ("stale", "wrong_period"),
        ("incomplete:bank_statement", "altered"),
        ("duplicate", "incomplete:general_ledger"),
        ("does_not_tie:ar_aging", "wrong_period:ar_aging"),
    ],
)
def test_ac8_conflicting_flaws_on_one_artefact_raise(flaws: tuple[str, ...]) -> None:
    with pytest.raises(ValueError) as info:
        generate(SEED, months=1, flaws=flaws)
    assert any(artefact in str(info.value) for artefact in ARTEFACTS)


@pytest.mark.parametrize("bad", ["", ":trial_balance", "unbalanced:a:b", "Unbalanced"])
def test_ac8_malformed_flaw_specs_raise(bad: str) -> None:
    with pytest.raises(ValueError):
        generate(SEED, months=1, flaws=(bad,))


# --- contract revision 1 ---------------------------------------------------------------------


@pytest.mark.parametrize("flaw", ["stale", "stale:trial_balance"])
def test_rev1_stale_trial_balance_with_one_month_raises(flaw: str) -> None:
    with pytest.raises(ValueError):
        generate(SEED, months=1, flaws=(flaw,))
    assert generate(SEED, months=2, flaws=(flaw,)).manifest.flaws[0].category == "stale"


def test_rev1_wrong_entity_trial_balance_carries_the_other_entitys_name() -> None:
    base = build().client_entities[0]
    entity = build(("wrong_entity",)).client_entities[0]
    assert all(tb.client_entity == base.name for tb in base.trial_balances)
    assert entity.trial_balances[-1].client_entity != entity.name
    assert entity.trial_balances[-1].client_entity.endswith(" (Synthetic)")
    assert all(tb.client_entity == entity.name for tb in entity.trial_balances[:-1])


def test_rev1_trial_balance_flaws_other_than_wrong_entity_keep_the_entity_name() -> None:
    for category in ("unbalanced", "wrong_period"):
        entity = build(spec(category, "trial_balance")).client_entities[0]
        assert all(tb.client_entity == entity.name for tb in entity.trial_balances)
