"""SPEC-001 AC-11, AC-12: adversarial payloads are labelled, verbatim and invariant-safe."""

from __future__ import annotations

import csv
import dataclasses
import fnmatch
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import cast

import pytest

from abacus_tools.synthetic import (
    ADVERSARIAL_CATEGORIES,
    Account,
    AdversarialPayload,
    Aging,
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
            out.add("bank_internal")
        previous[statement.account_number] = statement
        if not bank_ties_ok(entity, ledger, statement):
            out.add("bank_ties")
    if not aging_ties(entity.ar_aging, ledger):
        out.add("ar_ties")
    if not aging_ties(entity.ap_aging, ledger):
        out.add("ap_ties")
    return out


SEED = 23
Exports = tuple[Path, Path]
MONTHS = 2
ENTITY_ATTR = {
    "general_ledger": "journal_entries",
    "trial_balance": "trial_balances",
    "bank_statement": "bank_statements",
    "ar_aging": "ar_aging",
    "ap_aging": "ap_aging",
}
CSV_PATTERN = {
    "general_ledger": "general_ledger.csv",
    "trial_balance": "trial_balance_*.csv",
    "bank_statement": "bank_statement_*.csv",
    "ar_aging": "ar_aging.csv",
    "ap_aging": "ap_aging.csv",
}
FORMULA_STARTS = ("=", "+", "-", "@")
BIDI_AND_ZERO_WIDTH = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))} | {
    chr(c) for c in range(0x200B, 0x200E)
}


@cache
def build(flaws: tuple[str, ...] = (), adversarial: bool = True) -> SyntheticClient:
    return generate(SEED, months=MONTHS, flaws=flaws, adversarial=adversarial)


@pytest.fixture(scope="module")
def exports(tmp_path_factory: pytest.TempPathFactory) -> Exports:
    """CSV directory and XLSX path of the adversarial client."""
    root = tmp_path_factory.mktemp("adversarial")
    (root / "csv").mkdir()
    client = build()
    to_csv(client, root / "csv")
    return root / "csv", to_xlsx(client, root / "client.xlsx")


def payloads(category: str) -> list[AdversarialPayload]:
    return [p for p in build().manifest.adversarial if p.category == category]


def strings(obj: object) -> Iterator[tuple[str, str]]:
    """Every (field name, string value) in a dataclass tree."""
    if isinstance(obj, tuple):
        for item in cast("tuple[object, ...]", obj):
            yield from strings(item)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            value: object = getattr(obj, f.name)
            if isinstance(value, str):
                yield f.name, value
            else:
                yield from strings(value)


def artefact_strings(client: SyntheticClient, artefact: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for entity in client.client_entities:
        found.extend(strings(getattr(entity, ENTITY_ATTR[artefact])))
    return found


def csv_cells(directory: Path, artefact: str) -> list[str]:
    cells: list[str] = []
    previous = csv.field_size_limit(50_000_000)
    try:
        for path in sorted(directory.rglob("*.csv")):
            if fnmatch.fnmatch(path.name, CSV_PATTERN[artefact]):
                text = path.read_bytes().decode("utf-8")
                for row in csv.reader(io.StringIO(text, newline="")):
                    cells.extend(row)
    finally:
        csv.field_size_limit(previous)
    return cells


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def xlsx_texts(path: Path) -> list[str]:
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                root = parse_xml(archive.read(name))
                texts.extend(el.text for el in root.iter() if el.text)
    return texts


def within_one_edit(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1 :] == b[i + 1 :]
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    return shorter[i:] == longer[i + 1 :]


# --- AC-11 ------------------------------------------------------------------------------------


def test_ac11_manifest_labels_at_least_one_payload_per_category() -> None:
    client = build()
    assert client.manifest.flaws == ()
    found = {p.category for p in client.manifest.adversarial}
    assert found == set(ADVERSARIAL_CATEGORIES)
    for category in ADVERSARIAL_CATEGORIES:
        assert len(payloads(category)) >= 1
    for p in client.manifest.adversarial:
        assert p.artefact in ARTEFACTS
        assert p.field.strip() != ""
        assert p.location.strip() != ""
        assert p.payload != ""


def test_ac11_without_adversarial_flag_manifest_has_no_payloads() -> None:
    assert build(adversarial=False).manifest.adversarial == ()
    assert generate(SEED, months=MONTHS).manifest.adversarial == ()


def test_ac11_adversarial_generation_is_deterministic() -> None:
    assert build() == generate(SEED, months=MONTHS, adversarial=True)


@pytest.mark.parametrize("category", ADVERSARIAL_CATEGORIES)
def test_ac11_payload_appears_verbatim_in_the_named_field_and_artefact(category: str) -> None:
    client = build()
    for p in payloads(category):
        wanted = p.field.rsplit(".", 1)[-1]
        values = [v for name, v in artefact_strings(client, p.artefact) if name == wanted]
        assert any(p.payload in v for v in values), (p.artefact, p.field)


@pytest.mark.parametrize("category", ADVERSARIAL_CATEGORIES)
def test_ac11_invariants_hold_with_every_category(category: str) -> None:
    assert payloads(category)
    for entity in build().client_entities:
        assert failures(entity) == set()


def test_ac11_oversized_field_payload_is_at_least_64_kib() -> None:
    assert all(len(p.payload) >= 65_536 for p in payloads("oversized_field"))


def test_ac11_formula_injection_payload_starts_with_a_formula_character() -> None:
    assert all(p.payload.startswith(FORMULA_STARTS) for p in payloads("formula_injection"))


def test_ac11_unicode_deception_payload_has_invisible_or_non_ascii_characters() -> None:
    for p in payloads("unicode_deception"):
        assert not p.payload.isascii()
        assert any(ch in BIDI_AND_ZERO_WIDTH or ord(ch) > 127 for ch in p.payload)


def test_ac11_lookalike_name_is_one_character_from_a_counterparty_in_the_ledger() -> None:
    client = build()
    counterparties: set[str] = set()
    for entity in client.client_entities:
        for entry in entity.journal_entries:
            counterparties.update(x.counterparty for x in entry.lines if x.counterparty)
    for p in payloads("lookalike_name"):
        assert any(within_one_edit(c, p.payload) for c in counterparties), p.payload


@pytest.mark.parametrize("category", ["prompt_injection", "addressed_instruction"])
def test_ac11_text_payloads_are_plain_non_empty_strings(category: str) -> None:
    for p in payloads(category):
        assert p.payload.strip() != ""
        assert len(p.payload) < 65_536


def test_ac11_adversarial_payloads_combine_with_flaws() -> None:
    client = build(("unbalanced",))
    assert [(f.category, f.artefact) for f in client.manifest.flaws] == [
        ("unbalanced", "trial_balance")
    ]
    assert {p.category for p in client.manifest.adversarial} == set(ADVERSARIAL_CATEGORIES)
    entity = client.client_entities[0]
    assert failures(entity) <= {"tb_balanced", "tb_ties"}
    assert "tb_balanced" in failures(entity)


def test_ac11_adversarial_text_does_not_change_the_numbers() -> None:
    plain = build(adversarial=False).client_entities[0]
    entity = build().client_entities[0]
    assert [t.total_debits for t in entity.trial_balances] == [
        t.total_debits for t in plain.trial_balances
    ]
    assert entity.ar_aging.total == plain.ar_aging.total
    assert entity.ap_aging.total == plain.ap_aging.total


# --- AC-12 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("category", ADVERSARIAL_CATEGORIES)
def test_ac12_csv_reproduces_the_payload_exactly(category: str, exports: Exports) -> None:
    directory, _ = exports
    for p in payloads(category):
        cells = csv_cells(directory, p.artefact)
        assert any(p.payload in cell for cell in cells), (p.artefact, p.field)
        if category == "formula_injection":
            assert any(cell.startswith(p.payload) for cell in cells)


@pytest.mark.parametrize("category", ADVERSARIAL_CATEGORIES)
def test_ac12_xlsx_reproduces_the_payload_exactly(category: str, exports: Exports) -> None:
    _, workbook = exports
    texts = xlsx_texts(workbook)
    for p in payloads(category):
        assert any(p.payload in t for t in texts), (p.artefact, p.field)
        if category == "formula_injection":
            assert any(t.startswith(p.payload) for t in texts)


def json_strings(obj: object) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for item in cast("list[object]", obj):
            yield from json_strings(item)
    elif isinstance(obj, dict):
        for value in cast("dict[str, object]", obj).values():
            yield from json_strings(value)


def test_ac12_json_export_reproduces_the_payloads(tmp_path: Path) -> None:
    client = build()
    path = to_json(client, tmp_path)
    found = list(json_strings(json.loads(path.read_text(encoding="utf-8"))))
    for p in client.manifest.adversarial:
        assert any(p.payload in text for text in found), p.category


def test_ac12_manifest_json_marks_every_payload(exports: Exports) -> None:
    directory, _ = exports
    data = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    marked = data["adversarial"]
    assert len(marked) == len(build().manifest.adversarial)
    assert {m["category"] for m in marked} == set(ADVERSARIAL_CATEGORIES)
    assert {m["payload"] for m in marked} == {p.payload for p in build().manifest.adversarial}
    assert data["flaws"] == []


def test_ac12_xlsx_stays_inert_no_formulas_macros_or_external_links(
    exports: Exports,
) -> None:
    _, workbook = exports
    with zipfile.ZipFile(workbook) as archive:
        names = archive.namelist()
        assert not any("vba" in n.lower() or n.endswith(".bin") for n in names)
        assert not any("externalLink" in n for n in names)
        for name in names:
            data = archive.read(name)
            if name.endswith(".rels"):
                assert b'TargetMode="External"' not in data
            if name.startswith("xl/worksheets/"):
                root = parse_xml(data)
                assert not [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "f"]
