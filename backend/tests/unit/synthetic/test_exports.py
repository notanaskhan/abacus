"""SPEC-001 AC-13, AC-14, AC-15: export layout and formats, synthetic identifiers, secrets scan."""

from __future__ import annotations

import csv
import dataclasses
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import cast

import pytest

from abacus_tools.quality import secrets_scan
from abacus_tools.synthetic import (
    FAILURE_CATEGORIES,
    ClientEntity,
    SyntheticClient,
    generate,
    to_csv,
    to_json,
    to_xlsx,
)

SEED = 31
SUFFIX = " (Synthetic)"
SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
AMOUNT = re.compile(r"-?\d+\.\d+")
EXPONENT = re.compile(r"-?\d+(?:\.\d+)?[eE][+-]?\d+")


@cache
def build(
    seed: int = SEED, entities: int = 1, months: int = 3, flaws: tuple[str, ...] = ()
) -> SyntheticClient:
    return generate(seed, entities=entities, months=months, flaws=flaws)


def export_all(client: SyntheticClient, root: Path) -> tuple[Path, Path, Path]:
    """CSV dir, JSON file and XLSX file written under root."""
    (root / "csv").mkdir(parents=True)
    (root / "json").mkdir()
    to_csv(client, root / "csv")
    return root / "csv", to_json(client, root / "json"), to_xlsx(client, root / "client.xlsx")


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def read_rows(path: Path) -> list[list[str]]:
    text = path.read_bytes().decode("utf-8")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert text == "" or not text.startswith("﻿")
    return rows


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def expected_files(entity: ClientEntity) -> set[str]:
    names = {"chart_of_accounts.csv", "general_ledger.csv", "ar_aging.csv", "ap_aging.csv"}
    names |= {f"trial_balance_{tb.as_of.isoformat()}.csv" for tb in entity.trial_balances}
    names |= {
        f"bank_statement_{s.account_number}_{s.period_end:%Y-%m}.csv"
        for s in entity.bank_statements
    }
    return names


def entity_dirs(csv_root: Path) -> list[Path]:
    return sorted(p for p in csv_root.iterdir() if p.is_dir())


def strings(obj: object) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, tuple):
        for item in cast("tuple[object, ...]", obj):
            yield from strings(item)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from strings(getattr(obj, f.name))


def aba_valid(digits: str) -> bool:
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + d[2] + d[5] + d[8]) % 10 == 0


# --- AC-15: CSV -------------------------------------------------------------------------------


def test_ac15_csv_layout_matches_the_contract(tmp_path: Path) -> None:
    client = build(entities=2)
    csv_root, _, _ = export_all(client, tmp_path)
    assert {p.name for p in csv_root.iterdir() if p.is_file()} == {
        "request_list.csv",
        "manifest.json",
    }
    dirs = entity_dirs(csv_root)
    assert len(dirs) == 2
    assert all(SLUG.fullmatch(d.name) for d in dirs)
    found = sorted(sorted(p.name for p in d.iterdir()) for d in dirs)
    wanted = sorted(sorted(expected_files(e)) for e in client.client_entities)
    assert found == wanted


def test_ac15_to_csv_returns_every_exported_file_sorted(tmp_path: Path) -> None:
    (tmp_path / "csv").mkdir()
    paths = to_csv(build(entities=2), tmp_path / "csv")
    assert isinstance(paths, tuple)
    assert list(paths) == sorted(paths)
    assert set(paths) == {p for p in (tmp_path / "csv").rglob("*") if p.is_file()}
    assert all(p.is_relative_to(tmp_path / "csv") for p in paths)


def test_ac15_csv_is_utf8_lf_with_a_header_and_rectangular_rows(tmp_path: Path) -> None:
    csv_root, _, _ = export_all(build(), tmp_path)
    files = sorted(csv_root.rglob("*.csv"))
    assert len(files) > 5
    for path in files:
        raw = path.read_bytes()
        assert b"\r" not in raw, path.name
        assert raw.endswith(b"\n"), path.name
        rows = read_rows(path)
        header = rows[0]
        assert len(header) >= 2
        assert all(h.strip() != "" for h in header)
        assert all(len(r) == len(header) for r in rows), path.name


def test_ac15_csv_row_counts_match_the_model(tmp_path: Path) -> None:
    client = build()
    entity = client.client_entities[0]
    csv_root, _, _ = export_all(client, tmp_path)
    (directory,) = entity_dirs(csv_root)
    assert len(read_rows(directory / "chart_of_accounts.csv")) == len(entity.accounts) + 1
    lines = sum(len(e.lines) for e in entity.journal_entries)
    assert len(read_rows(directory / "general_ledger.csv")) == lines + 1
    for tb in entity.trial_balances:
        rows = read_rows(directory / f"trial_balance_{tb.as_of.isoformat()}.csv")
        assert len(rows) == len(tb.lines) + 1
    for s in entity.bank_statements:
        rows = read_rows(directory / f"bank_statement_{s.account_number}_{s.period_end:%Y-%m}.csv")
        # A statement CSV also carries its opening/closing balances and reconciling items.
        assert len(rows) >= len(s.lines) + 1
        cells = {cell for row in rows for cell in row}
        assert {str(s.opening_balance), str(s.closing_balance)} <= cells
        assert {str(i.amount) for i in s.reconciling_items} <= cells
    assert len(read_rows(directory / "ar_aging.csv")) == len(entity.ar_aging.lines) + 1
    assert len(read_rows(directory / "ap_aging.csv")) == len(entity.ap_aging.lines) + 1
    assert len(read_rows(csv_root / "request_list.csv")) == len(client.request_list.items) + 1


def test_ac15_decimal_amounts_are_rendered_as_plain_two_place_strings(tmp_path: Path) -> None:
    client = build()
    entity = client.client_entities[0]
    csv_root, _, _ = export_all(client, tmp_path)
    (directory,) = entity_dirs(csv_root)
    ledger = read_rows(directory / "general_ledger.csv")[1:]
    flat = [(e, x) for e in entity.journal_entries for x in e.lines]
    assert len(ledger) == len(flat)
    for row, (entry, line) in zip(ledger, flat, strict=True):
        wanted = {entry.id, entry.date.isoformat(), line.account_code}
        assert wanted | {str(line.debit), str(line.credit)} <= set(row)
    tb = entity.trial_balances[-1]
    for row, tb_line in zip(
        read_rows(directory / f"trial_balance_{tb.as_of.isoformat()}.csv")[1:],
        tb.lines,
        strict=True,
    ):
        assert {tb_line.account_code, str(tb_line.debit), str(tb_line.credit)} <= set(row)
    s = entity.bank_statements[0]
    name = f"bank_statement_{s.account_number}_{s.period_end:%Y-%m}.csv"
    bank_rows = [set(row) for row in read_rows(directory / name)[1:]]
    for bank_line in s.lines:
        wanted = {bank_line.date.isoformat(), str(bank_line.amount), str(bank_line.balance)}
        assert any(wanted <= row for row in bank_rows), bank_line
    for aging, file in ((entity.ar_aging, "ar_aging.csv"), (entity.ap_aging, "ap_aging.csv")):
        for row, a_line in zip(read_rows(directory / file)[1:], aging.lines, strict=True):
            buckets = {str(a_line.current), str(a_line.days_1_30), str(a_line.over_90)}
            assert {a_line.counterparty} | buckets <= set(row)


def test_ac15_no_amount_cell_uses_exponent_notation_or_extra_places(tmp_path: Path) -> None:
    csv_root, _, _ = export_all(build(), tmp_path)
    numeric = 0
    for path in csv_root.rglob("*.csv"):
        for row in read_rows(path)[1:]:
            for cell in row:
                assert not EXPONENT.fullmatch(cell), (path.name, cell)
                if AMOUNT.fullmatch(cell):
                    numeric += 1
                    assert re.fullmatch(r"-?\d+\.\d{2}", cell), (path.name, cell)
    assert numeric > 100


def test_ac15_manifest_json_beside_csvs_lists_flaws_and_payloads(tmp_path: Path) -> None:
    client = build(flaws=("unbalanced", "altered"))
    (tmp_path / "csv").mkdir()
    to_csv(client, tmp_path / "csv")
    data = json.loads((tmp_path / "csv" / "manifest.json").read_text(encoding="utf-8"))
    assert [(f["category"], f["artefact"]) for f in data["flaws"]] == [
        (f.category, f.artefact) for f in client.manifest.flaws
    ]
    assert data["adversarial"] == []


# --- AC-15: JSON ------------------------------------------------------------------------------


def no_floats(text: str) -> object:
    def reject(value: str) -> float:
        raise AssertionError(f"float in JSON: {value}")

    def sorted_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        keys = [k for k, _ in pairs]
        assert keys == sorted(keys), keys
        return dict(pairs)

    return json.loads(text, parse_float=reject, object_pairs_hook=sorted_keys)


def test_ac15_json_is_one_file_with_sorted_keys_string_amounts_and_iso_dates(
    tmp_path: Path,
) -> None:
    client = build()
    entity = client.client_entities[0]
    (tmp_path / "json").mkdir()
    path = to_json(client, tmp_path / "json")
    assert path == tmp_path / "json" / "client.json"
    assert [p.name for p in (tmp_path / "json").iterdir()] == ["client.json"]
    data = cast("dict[str, object]", no_floats(path.read_bytes().decode("utf-8")))
    assert data["seed"] == client.seed
    assert data["name"] == client.name
    assert data["generator_version"] == client.generator_version
    first = cast("list[dict[str, object]]", data["client_entities"])[0]
    assert first["name"] == entity.name
    assert first["period_start"] == entity.period_start.isoformat()
    assert first["period_end"] == entity.period_end.isoformat()
    tbs = cast("list[dict[str, object]]", first["trial_balances"])
    assert tbs[-1]["as_of"] == entity.trial_balances[-1].as_of.isoformat()
    tb_lines = cast("list[dict[str, object]]", tbs[-1]["lines"])
    assert tb_lines[0]["debit"] == str(entity.trial_balances[-1].lines[0].debit)
    assert tb_lines[0]["credit"] == str(entity.trial_balances[-1].lines[0].credit)
    entries = cast("list[dict[str, object]]", first["journal_entries"])
    assert len(entries) == len(entity.journal_entries)
    assert entries[0]["date"] == entity.journal_entries[0].date.isoformat()


# --- AC-15: XLSX ------------------------------------------------------------------------------


def test_ac15_xlsx_is_a_valid_zip_with_one_sheet_per_csv(tmp_path: Path) -> None:
    client = build()
    csv_root, _, workbook = export_all(client, tmp_path)
    csv_rows = sorted(len(read_rows(p)) for p in csv_root.rglob("*.csv"))
    with zipfile.ZipFile(workbook) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        for name in names:
            if name.endswith((".xml", ".rels")):
                parse_xml(archive.read(name))
        sheets = [
            el.attrib["name"]
            for el in parse_xml(archive.read("xl/workbook.xml")).iter()
            if local(el.tag) == "sheet"
        ]
        worksheets = [n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml")]
        row_counts = sorted(
            sum(1 for el in parse_xml(archive.read(n)).iter() if local(el.tag) == "row")
            for n in worksheets
        )
        stamps = {info.date_time for info in archive.infolist()}
    assert len(sheets) == len(csv_rows)
    assert len(set(sheets)) == len(sheets)
    assert all(0 < len(s) <= 31 for s in sheets)
    assert len(worksheets) == len(sheets)
    assert row_counts == csv_rows
    assert len(stamps) == 1


def test_ac15_to_xlsx_returns_the_given_path(tmp_path: Path) -> None:
    target = tmp_path / "out.xlsx"
    assert to_xlsx(build(), target) == target
    assert target.is_file()


def test_ac15_repeated_exports_are_byte_identical(tmp_path: Path) -> None:
    client = build(entities=2)
    first = snapshot(export_all(client, tmp_path / "a")[0].parent)
    second = snapshot(export_all(client, tmp_path / "b")[0].parent)
    assert first == second
    assert any(name.endswith(".xlsx") for name in first)
    assert any(name.endswith("client.json") for name in first)
    assert any(name.endswith(".csv") for name in first)
    again = snapshot(export_all(generate(SEED, entities=2, months=3), tmp_path / "c")[0].parent)
    assert again == first


# --- AC-13 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ac13_identifiers_are_in_reserved_or_invalid_ranges(seed: int) -> None:
    client = build(seed, entities=3, months=2)
    for entity in client.client_entities:
        assert re.fullmatch(r"00-\d{7}", entity.ein), "EIN must use the unassigned prefix 00"
        for account in entity.bank_accounts:
            assert re.fullmatch(r"\d{9}", account.routing_number)
            assert not aba_valid(account.routing_number)
            assert not (
                account.account_number.isdigit() and 13 <= len(account.account_number) <= 19
            )
        for entry in entity.journal_entries:
            assert not (entry.id.isdigit() and 13 <= len(entry.id) <= 19)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ac13_no_ssns_cards_real_emails_or_phone_numbers_in_any_string(seed: int) -> None:
    client = build(seed, entities=2, months=2)
    emails = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+)")
    phones = re.compile(r"\(?(\d{3})\)?[-. ](\d{3})[-. ](\d{4})\b")
    short_phones = re.compile(r"\b555-(\d{4})\b")
    for text in strings(client):
        assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", text), "SSN-shaped value"
        assert not re.search(r"\d{13,19}", text), "card-number-shaped value"
        for domain in emails.findall(text):
            assert domain in {"example.com", "example.org"}
        for _, exchange, line in phones.findall(text):
            assert exchange == "555"
            assert line.startswith("01")
        for line in short_phones.findall(text):
            assert line.startswith("01")


# --- AC-14 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_ac14_client_and_client_entity_names_end_with_the_synthetic_marker(seed: int) -> None:
    client = build(seed, entities=3, months=1)
    assert client.name.endswith(SUFFIX)
    assert client.name.removesuffix(SUFFIX).strip() != ""
    names = [e.name for e in client.client_entities]
    assert all(n.endswith(SUFFIX) and n.removesuffix(SUFFIX).strip() != "" for n in names)
    assert len(set(names)) == len(names)


def test_ac14_exports_carry_the_synthetic_marker(tmp_path: Path) -> None:
    client = build()
    _, json_path, _ = export_all(client, tmp_path)
    data = json_path.read_text(encoding="utf-8")
    assert json.dumps(client.name)[1:-1] in data
    assert client.client_entities[0].name.endswith(SUFFIX)


# --- AC-13: secrets_scan ----------------------------------------------------------------------

SCAN_SCENARIOS: list[tuple[int, tuple[str, ...], bool]] = [
    (1, (), False),
    (2, (), False),
    (3, (), False),
    (4, ("incomplete", "unbalanced", "altered", "does_not_tie", "stale:ap_aging"), False),
    (5, (), True),
    (6, ("unbalanced", "wrong_currency"), True),
    *[(7, (category,), False) for category in FAILURE_CATEGORIES],
]


@pytest.mark.parametrize(
    ("seed", "flaws", "adversarial"),
    SCAN_SCENARIOS,
    ids=[f"seed{s}-{'+'.join(f) or 'plain'}{'-adv' if a else ''}" for s, f, a in SCAN_SCENARIOS],
)
def test_ac13_secrets_scan_finds_nothing_in_any_export(
    tmp_path: Path, seed: int, flaws: tuple[str, ...], adversarial: bool
) -> None:
    client = generate(seed, months=3, flaws=flaws, adversarial=adversarial)
    export_all(client, tmp_path)
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert len(files) > 10
    violations = secrets_scan.scan(tmp_path, files=files)
    assert violations == [], [str(v) for v in violations]


def test_ac13_secrets_scan_covers_default_client_exports(tmp_path: Path) -> None:
    export_all(generate(42), tmp_path)
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert secrets_scan.scan(tmp_path, files=files) == []
