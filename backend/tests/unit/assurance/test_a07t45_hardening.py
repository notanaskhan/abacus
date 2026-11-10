"""A-07-T45 (ADR-079): the release-and-archive mutation scope, its floor, and the p95 budgets; plus
survivor triage for the pure helpers the weekly run mutates first (grant digest, workflow ids,
the seal's canonical form and Merkle root)."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import UUID

import pytest

from abacus.modules.assurance import release
from abacus.modules.assurance.archive_seal import EmptyBinder, Leaf, canonical, merkle_root
from abacus_tools.loadtest import a07_budgets
from abacus_tools.quality import mutation
from abacus_tools.quality.mutation_floors import FILE, parse

W = UUID("00000000-0000-4000-8000-0000000004f1")
V = UUID("00000000-0000-4000-8000-0000000005a1")


def test_the_scope_covers_the_red_files_and_has_a_floor() -> None:
    for path in (
        "src/abacus/modules/assurance/release.py",
        "src/abacus/modules/assurance/archive_gate.py",
        "src/abacus/modules/assurance/archive_lock.py",
        "src/abacus/modules/assurance/archive_seal.py",
    ):
        assert mutation.scope_of(path) == "assurance/release_archive"
    assert mutation.scope_of("src/abacus/modules/evidence/archive.py") == "evidence"
    assert mutation.scope_of("src/abacus/kernel/db/archive_guard.py") == "kernel/db"
    assert "assurance/release_archive" in parse(FILE.read_text())


def test_the_grant_digest_binds_every_part() -> None:
    base = release.grant_digest(W, V, "a" * 64, "b" * 64)
    assert (
        base
        == hashlib.sha256(f"report.release:{W}:{V}:{'a' * 64}:{'b' * 64}".encode()).hexdigest()
    )
    assert release.grant_digest(W, V, "a" * 64, "c" * 64) != base
    assert release.grant_digest(W, V, "c" * 64, "b" * 64) != base
    assert release.grant_digest(V, V, "a" * 64, "b" * 64) != base


def test_the_release_workflow_id_is_one_per_decision() -> None:
    g = UUID("00000000-0000-4000-8000-0000000009a1")
    assert release.workflow_id(V, W, g) == f"release:{V}:{W}:{g}"


def test_the_merkle_root_carries_an_odd_node_and_refuses_an_empty_binder() -> None:
    one = [Leaf("row", "a", "1" * 64)]
    assert merkle_root(one) == hashlib.sha256(one[0].text().encode()).hexdigest()
    three = [Leaf("row", c, str(i) * 64) for i, c in enumerate("abc", start=1)]
    two = merkle_root(three[:2])
    assert merkle_root(three) != two
    with pytest.raises(EmptyBinder):
        merkle_root([])


def test_the_canonical_form_refuses_floats_and_sorts_keys() -> None:
    assert canonical({"b": 1, "a": "x"}) == b'{"a":"x","b":1}'
    with pytest.raises((TypeError, ValueError)):
        canonical({"a": 1.5})


def test_the_budgets_and_their_breaches() -> None:
    names = {b.name for b in a07_budgets.BUDGETS}
    assert names == {
        "report_release",
        "archive_lock_enqueue",
        "archive_seal_northwind",
        "archived_guard_per_row",
    }
    ok = {b.name: b.p95_ms for b in a07_budgets.BUDGETS}
    assert a07_budgets.breaches(ok) == []
    slow = {**ok, "report_release": Decimal(3001)}
    assert a07_budgets.breaches(slow) == ["report_release: p95 3001 ms > 3000 ms"]
    assert a07_budgets.breaches({}) and all("not measured" in b for b in a07_budgets.breaches({}))
