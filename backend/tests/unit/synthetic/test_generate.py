"""SPEC-001 AC-1, AC-2, AC-3, AC-16, AC-17 and parameter validation for the synthetic generator."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pytest

from abacus_tools import synthetic
from abacus_tools.synthetic import (
    ADVERSARIAL_CATEGORIES,
    FAILURE_CATEGORIES,
    GENERATOR_VERSION,
    SyntheticClient,
    generate,
    to_csv,
    to_json,
    to_xlsx,
)

TAXONOMY = Path(__file__).resolve().parents[4] / "docs" / "product" / "failure-taxonomy.md"

# AC-3: the golden hash is pinned together with the generator version it was produced by.
# Changing GENERATOR_VERSION without updating both constants in the same change fails the
# golden test. "PENDING" fails the test until the implementer fills both in once.
GOLDEN_VERSION: str = "1.2.0"
GOLDEN_SHA256: str = "a4b281bb626facdd4f52d2dfad410d92dfc869553f3ea8888559d7e54f5eace4"

ARTEFACTS = ("general_ledger", "trial_balance", "bank_statement", "ar_aging", "ap_aging")

DIGEST_SCRIPT = """
import hashlib
import sys
import tempfile
from pathlib import Path

from abacus_tools.synthetic import generate, to_csv, to_json, to_xlsx

seed = int(sys.argv[1])
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "csv").mkdir()
    (root / "json").mkdir()
    client = generate(seed)
    to_csv(client, root / "csv")
    to_json(client, root / "json")
    to_xlsx(client, root / "client.xlsx")
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(rel + b"\\0" + str(len(data)).encode() + b"\\0" + data)
    sys.stdout.write(digest.hexdigest())
"""


def export_all(client: SyntheticClient, root: Path) -> Path:
    """Write CSV, JSON and XLSX exports under root and return root."""
    (root / "csv").mkdir(parents=True)
    (root / "json").mkdir()
    to_csv(client, root / "csv")
    to_json(client, root / "json")
    to_xlsx(client, root / "client.xlsx")
    return root


def digest_of(root: Path) -> str:
    """SHA-256 over every exported file's relative path, length and bytes (same as the script)."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(rel + b"\0" + str(len(data)).encode() + b"\0" + data)
    return digest.hexdigest()


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def taxonomy_code_names(heading: str) -> tuple[str, ...]:
    """Code-name column (second column) of the table under the given '## ' heading."""
    text = TAXONOMY.read_text(encoding="utf-8")
    section = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    names: list[str] = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2:
            match = re.fullmatch(r"`([a-z_]+)`", cells[1])
            if match:
                names.append(match.group(1))
    return tuple(names)


# --- AC-1 -------------------------------------------------------------------------------------


def test_ac1_same_seed_gives_identical_client_and_exports(tmp_path: Path) -> None:
    first = generate(42)
    second = generate(42)
    assert first == second
    a = snapshot(export_all(first, tmp_path / "a"))
    b = snapshot(export_all(second, tmp_path / "b"))
    assert a.keys() == b.keys()
    assert a == b
    assert len(a) > 10


def test_ac1_repeated_export_of_one_client_is_byte_identical(tmp_path: Path) -> None:
    client = generate(7, months=3)
    a = snapshot(export_all(client, tmp_path / "a"))
    b = snapshot(export_all(client, tmp_path / "b"))
    assert a == b


@pytest.mark.parametrize("hash_seed", ["1", "2"])
def test_ac1_separate_process_gives_identical_exports(tmp_path: Path, hash_seed: str) -> None:
    expected = digest_of(export_all(generate(42), tmp_path / "local"))
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    result = subprocess.run(
        [sys.executable, "-c", DIGEST_SCRIPT, "42"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd=tmp_path,
    )
    assert result.stdout.strip() == expected


def test_ac1_golden_sha256_of_default_client_exports(tmp_path: Path) -> None:
    actual = digest_of(export_all(generate(42), tmp_path))
    if GOLDEN_SHA256 == "PENDING" or GOLDEN_VERSION == "PENDING":
        pytest.fail(
            "Golden hash not pinned yet. Set GOLDEN_VERSION = "
            f"{GENERATOR_VERSION!r} and GOLDEN_SHA256 = {actual!r} in test_generate.py."
        )
    assert GENERATOR_VERSION == GOLDEN_VERSION, (
        f"GENERATOR_VERSION is {GENERATOR_VERSION!r} but the golden hash was pinned for "
        f"{GOLDEN_VERSION!r}: update GOLDEN_VERSION and GOLDEN_SHA256 ({actual!r}) in the "
        "same change"
    )
    assert actual == GOLDEN_SHA256, (
        "Output of generate(42) changed without a GENERATOR_VERSION bump; bump the version "
        f"and pin the new hash {actual!r}"
    )


# --- AC-2 -------------------------------------------------------------------------------------


def test_ac2_different_seeds_differ_in_names_amounts_and_counts() -> None:
    clients = [generate(seed, months=2) for seed in (1, 2, 3, 4, 5)]
    assert len({c.name for c in clients}) == 5
    assert len({c.client_entities[0].name for c in clients}) == 5
    final_tbs = [c.client_entities[0].trial_balances[-1].lines for c in clients]
    assert len(set(final_tbs)) == 5
    counts = {len(c.client_entities[0].journal_entries) for c in clients}
    assert len(counts) > 1


# --- AC-3 -------------------------------------------------------------------------------------


def test_ac3_generator_version_is_part_of_the_output(tmp_path: Path) -> None:
    client = generate(42, months=1)
    assert isinstance(GENERATOR_VERSION, str)
    assert GENERATOR_VERSION != ""
    assert client.generator_version == GENERATOR_VERSION
    (tmp_path / "json").mkdir()
    path = to_json(client, tmp_path / "json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["generator_version"] == GENERATOR_VERSION


def test_ac3_golden_constants_are_keyed_by_version() -> None:
    assert GOLDEN_VERSION != ""
    assert GOLDEN_SHA256 == "PENDING" or re.fullmatch(r"[0-9a-f]{64}", GOLDEN_SHA256)


# --- taxonomy ---------------------------------------------------------------------------------


def test_failure_categories_match_the_taxonomy_document() -> None:
    expected = taxonomy_code_names("Categories")
    assert len(expected) == 11
    assert expected == FAILURE_CATEGORIES


def test_adversarial_categories_match_the_taxonomy_document() -> None:
    expected = taxonomy_code_names("Adversarial content")
    assert len(expected) == 6
    assert expected == ADVERSARIAL_CATEGORIES


# --- model shape ------------------------------------------------------------------------------


def test_model_is_frozen_dataclasses_with_tuples() -> None:
    client = generate(3, months=1)
    assert isinstance(client, SyntheticClient)
    entity = client.client_entities[0]
    for obj in (
        client,
        entity,
        entity.accounts[0],
        entity.journal_entries[0],
        entity.journal_entries[0].lines[0],
        entity.trial_balances[0],
        entity.bank_statements[0],
        entity.ar_aging,
        client.request_list,
        client.manifest,
    ):
        assert dataclasses.is_dataclass(obj)
        attr = dataclasses.fields(obj)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, attr, None)
    assert isinstance(client.client_entities, tuple)
    assert isinstance(entity.journal_entries, tuple)
    assert isinstance(client.manifest.flaws, tuple)
    assert isinstance(client.manifest.adversarial, tuple)


def test_default_client_shape() -> None:
    client = generate(5, months=2)
    entity = client.client_entities[0]
    assert client.seed == 5
    assert len(client.client_entities) == 1
    assert entity.currency == "USD"
    assert entity.period_start == date(2025, 1, 1)
    assert entity.period_end == date(2025, 2, 28)
    assert [tb.as_of for tb in entity.trial_balances] == [date(2025, 1, 31), date(2025, 2, 28)]
    assert len(entity.bank_accounts) >= 1


def test_leap_year_month_end_and_fiscal_year_not_starting_in_january() -> None:
    client = generate(5, months=12, start=date(2023, 3, 1))
    entity = client.client_entities[0]
    assert entity.period_start == date(2023, 3, 1)
    assert entity.period_end == date(2024, 2, 29)
    assert entity.trial_balances[-1].as_of == date(2024, 2, 29)
    assert len(entity.trial_balances) == 12
    # The year-end close actually happened on the leap-day year end.
    closing = [e for e in entity.journal_entries if "close" in e.memo.lower()]
    assert closing
    assert all(e.date == date(2024, 2, 29) for e in closing)
    types = {a.code: a.type for a in entity.accounts}
    for line in entity.trial_balances[-1].lines:
        if types[line.account_code] in ("revenue", "expense"):
            assert line.debit == 0
            assert line.credit == 0
    assert any(
        types[line.account_code] in ("revenue", "expense")
        for line in entity.trial_balances[-2].lines
    )


@pytest.mark.parametrize("start", [date(2025, 1, 15), date(2025, 3, 1), date(2025, 3, 2)])
def test_no_entry_is_dated_before_a_mid_month_or_weekend_start(start: date) -> None:
    entity = generate(5, months=2, start=start).client_entities[0]
    assert entity.period_start == start
    assert min(e.date for e in entity.journal_entries) >= start
    assert entity.trial_balances[0].as_of >= start


def test_multiple_entities_are_distinct() -> None:
    client = generate(5, entities=3, months=1)
    names = [e.name for e in client.client_entities]
    assert len(names) == 3
    assert len(set(names)) == 3
    assert len({e.ein for e in client.client_entities}) == 3


# --- validation -------------------------------------------------------------------------------


@pytest.mark.parametrize("entities", [0, 6, -1])
def test_entities_out_of_range_raises_naming_valid_range(entities: int) -> None:
    with pytest.raises(ValueError, match="entities") as info:
        generate(1, entities=entities)
    assert "1" in str(info.value)
    assert "5" in str(info.value)


@pytest.mark.parametrize("months", [0, 37, -1])
def test_months_out_of_range_raises_naming_valid_range(months: int) -> None:
    with pytest.raises(ValueError, match="months") as info:
        generate(1, months=months)
    assert "1" in str(info.value)
    assert "36" in str(info.value)


def test_boundary_values_are_accepted() -> None:
    assert len(generate(1, entities=5, months=1).client_entities) == 5
    assert len(generate(1, entities=1, months=1).client_entities[0].trial_balances) == 1


def test_unknown_flaw_category_lists_valid_categories() -> None:
    with pytest.raises(ValueError, match="no_such_flaw") as info:
        generate(1, months=1, flaws=["no_such_flaw"])
    for category in FAILURE_CATEGORIES:
        assert category in str(info.value)


def test_unknown_artefact_lists_valid_artefacts() -> None:
    with pytest.raises(ValueError, match="no_such_artefact") as info:
        generate(1, months=1, flaws=["unbalanced:no_such_artefact"])
    for artefact in ARTEFACTS:
        assert artefact in str(info.value)


def test_flaw_on_artefact_it_cannot_target_names_valid_artefacts() -> None:
    with pytest.raises(ValueError, match="unbalanced") as info:
        generate(1, months=1, flaws=["unbalanced:bank_statement"])
    assert "trial_balance" in str(info.value)


@pytest.mark.parametrize(
    "flaws",
    [
        ["unbalanced", "unreadable:trial_balance"],
        ["wrong_period", "stale"],
        ["duplicate", "incomplete"],
        ["unbalanced", "unbalanced"],
    ],
)
def test_two_flaws_on_the_same_artefact_raise(flaws: list[str]) -> None:
    with pytest.raises(ValueError, match=r"trial_balance|general_ledger"):
        generate(1, months=1, flaws=flaws)


def test_flaws_accepts_any_sequence() -> None:
    from_tuple = generate(1, months=1, flaws=("unbalanced",))
    from_list = generate(1, months=1, flaws=["unbalanced"])
    assert from_tuple == from_list


# --- AC-16 ------------------------------------------------------------------------------------


def test_ac16_request_list_has_items_across_audit_areas_with_tiers() -> None:
    items = generate(11, months=2).request_list.items
    assert len(items) >= 5
    assert len({i.id for i in items}) == len(items)
    assert len({i.audit_area for i in items}) >= 3
    assert {i.retrievability_tier for i in items} <= {"A", "B", "C", "D", "E"}
    assert len({i.retrievability_tier for i in items}) >= 2
    for item in items:
        assert item.description.strip() != ""
        assert item.audit_area.strip() != ""
        assert item.artefact is None or item.artefact in ARTEFACTS
        assert "company" not in item.description.lower()
        assert "pbc_item" not in item.description.lower()
    assert sum(1 for i in items if i.artefact is not None) >= 3


def test_ac16_exactly_one_trial_balance_item_and_it_is_tier_a() -> None:
    items = generate(11, months=2).request_list.items
    tb_items = [i for i in items if i.artefact == "trial_balance"]
    assert len(tb_items) == 1
    assert tb_items[0].retrievability_tier == "A"


# --- AC-17 ------------------------------------------------------------------------------------


# Timing is measured without coverage instrumentation: AC-17 budgets the generator, not the tracer.
@pytest.mark.no_cover
def test_ac17_default_generation_and_exports_finish_within_five_seconds(tmp_path: Path) -> None:
    (tmp_path / "csv").mkdir()
    (tmp_path / "json").mkdir()
    start = time.perf_counter()
    client = generate(42)
    to_csv(client, tmp_path / "csv")
    to_json(client, tmp_path / "json")
    to_xlsx(client, tmp_path / "client.xlsx")
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"generate + exports took {elapsed:.2f}s (budget 5s)"


def test_ac17_default_client_is_about_two_thousand_entries_per_month() -> None:
    entity = generate(42).client_entities[0]
    per_month = len(entity.journal_entries) / 12
    assert 1000 <= per_month <= 4000


def test_public_api_is_exported() -> None:
    for name in (
        "generate",
        "to_csv",
        "to_json",
        "to_xlsx",
        "GENERATOR_VERSION",
        "FAILURE_CATEGORIES",
        "ADVERSARIAL_CATEGORIES",
        "SyntheticClient",
        "ClientEntity",
        "Account",
        "JournalEntry",
        "JournalLine",
        "TrialBalance",
        "TrialBalanceLine",
        "BankAccount",
        "BankStatement",
        "BankLine",
        "ReconcilingItem",
        "Aging",
        "AgingLine",
        "RequestList",
        "RequestItem",
        "Manifest",
        "Flaw",
        "AdversarialPayload",
    ):
        assert hasattr(synthetic, name), name


# --- PR #3 security review ---------------------------------------------------------------------

EVERYDAY_WORDS = frozenset(
    w.lower()
    for w in (
        "Amber",
        "Birch",
        "Cedar",
        "Delta",
        "Echo",
        "Fern",
        "Gale",
        "Jade",
        "Maple",
        "Onyx",
        "Sable",
        "Acorn",
        "Alder",
        "Aspen",
        "Atlas",
        "Basil",
        "Bay",
        "Cobalt",
        "Coral",
        "Crimson",
        "Dawn",
        "Eagle",
        "Ember",
        "Falcon",
        "Forest",
        "Garnet",
        "Harbor",
        "Hazel",
        "Iron",
        "Ivory",
        "Juniper",
        "Lake",
        "Lotus",
        "Meadow",
        "North",
        "Oak",
        "Olive",
        "Opal",
        "Pearl",
        "Pine",
        "Raven",
        "River",
        "Ruby",
        "Silver",
        "Summit",
        "Sun",
        "Willow",
    )
)
BANK_NUMBER = re.compile(r"SYN-\d{4}-\d{4}")


@pytest.mark.parametrize("seed", [1, 2, 3, 42])
def test_bank_account_numbers_use_the_syn_format(seed: int) -> None:
    client = generate(seed, entities=2, months=2)
    for entity in client.client_entities:
        assert entity.bank_accounts
        numbers = {b.account_number for b in entity.bank_accounts}
        for number in numbers:
            assert BANK_NUMBER.fullmatch(number), number
        assert {s.account_number for s in entity.bank_statements} == numbers


@pytest.mark.parametrize("seed", [1, 2, 3, 42])
def test_counterparty_names_are_invented_not_everyday_words(seed: int) -> None:
    client = generate(seed, entities=2, months=2)
    for entity in client.client_entities:
        journal = {
            x.counterparty
            for e in entity.journal_entries
            for x in e.lines
            if x.counterparty is not None
        }
        aging = [x.counterparty for a in (entity.ar_aging, entity.ap_aging) for x in a.lines]
        assert journal
        assert aging
        for name in journal | set(aging):
            assert name.split()[0].lower() not in EVERYDAY_WORDS, name
        for aged in (entity.ar_aging, entity.ap_aging):
            names = [x.counterparty for x in aged.lines]
            assert len(set(names)) == len(names)
