"""A-07-T37 (TASK-6610; SPEC-644 AC-37; ADR-159): the archive seal's manifest, without a database.

Row acceptance: "Locking Northwind on Dec 3, 2026 yields a seal whose recomputation is
byte-identical, a records object retained in COMPLIANCE mode to Oct 9, 2031, and evidence retained
to Oct 9, 2033." The lock workflow's database half runs at the end pass's integration suite.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from abacus.modules.assurance.archive_lock import workflow_id
from abacus.modules.assurance.archive_records import five_year_floor
from abacus.modules.assurance.archive_seal import EmptyBinder, Leaf, build, canonical, merkle_root

RELEASE = date(2026, 10, 9)
LEAVES = [
    Leaf("evidence_version", "v-1", "a" * 64),
    Leaf("evidence_version", "v-2", "b" * 64),
    Leaf("row", "workpaper:w-1", "c" * 64),
    Leaf("run_record", "r-4240", "d" * 64),
    Leaf("row", "workpaper:w-2", "e" * 64),
]


def _manifest(leaves: list[Leaf]) -> bytes:
    return build(
        tenant_id="t", engagement_id="e", work_item_id="wi", archive_id="a", release_id="r",
        release_date=RELEASE, retention_until=date(2033, 10, 9),
        compliance_retain_until=five_year_floor(RELEASE), leaves=leaves,
        audit_checkpoint_seq_to=18342, audit_checkpoint_root="f" * 64, checklist_sha256="9" * 64,
    ).body  # fmt: skip


def test_ac37_a_recomputed_seal_is_byte_identical_whatever_the_read_order() -> None:
    first = _manifest(LEAVES)
    again = _manifest(list(reversed(LEAVES)))
    assert first == again
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(again).hexdigest()


def test_ac37_any_changed_leaf_changes_the_seal() -> None:
    changed = [*LEAVES[:-1], Leaf("row", "workpaper:w-2", "0" * 64)]
    assert _manifest(changed) != _manifest(LEAVES)


def test_ac37_compliance_holds_to_oct_9_2031_and_the_manifest_says_so() -> None:
    assert five_year_floor(RELEASE) == date(2031, 10, 9)
    body = _manifest(LEAVES).decode()
    assert '"compliance_retain_until":"2031-10-09"' in body
    assert '"retention_until":"2033-10-09"' in body


def test_the_counts_and_the_root() -> None:
    found = build(
        tenant_id="t", engagement_id="e", work_item_id="wi", archive_id="a", release_id="r",
        release_date=RELEASE, retention_until=date(2033, 10, 9),
        compliance_retain_until=date(2031, 10, 9), leaves=LEAVES, audit_checkpoint_seq_to=None,
        audit_checkpoint_root=None, checklist_sha256="9" * 64,
    )  # fmt: skip
    assert (found.evidence_leaf_count, found.row_leaf_count, found.run_record_count) == (2, 2, 1)
    assert found.merkle_root == merkle_root(LEAVES)
    assert found.sha256 == hashlib.sha256(found.body).hexdigest()


def test_an_odd_node_is_carried_and_an_empty_binder_refused() -> None:
    one = [Leaf("row", "x", "1" * 64)]
    assert merkle_root(one) == hashlib.sha256(one[0].text().encode()).hexdigest()
    with pytest.raises(EmptyBinder):
        merkle_root([])


def test_the_canonical_form_sorts_keys_and_refuses_floats() -> None:
    assert canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
    with pytest.raises(TypeError):
        canonical({"amount": 1.5})


def test_one_lock_run_per_work_item() -> None:
    import uuid

    t, wi = uuid.uuid4(), uuid.uuid4()
    assert workflow_id(t, wi) == f"archive_lock:{t}:{wi}"
