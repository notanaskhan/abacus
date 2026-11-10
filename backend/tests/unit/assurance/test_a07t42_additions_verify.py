"""A-07-T42 (A-07 F7, F8; AC-37's sibling): post-lock additions and seal verification, as code.

The PI-02 memo's addition manifest names the original seal and never changes it; its hash is
fixed at creation and rebuilt byte for byte at approval; a tampered row changes the rebuilt
Merkle root, so verification reports `seal_mismatch`."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from uuid import UUID

import pytest

from abacus.modules.assurance import archive_additions as aa
from abacus.modules.assurance.archive_seal import Leaf, merkle_root
from abacus.modules.evidence.records import RECORD_CLASSES

ARCHIVE = aa.LockedArchive(
    UUID("00000000-0000-4000-8000-0000000006b1"),
    UUID("00000000-0000-4000-8000-0000000004e1"),
    UUID("00000000-0000-4000-8000-0000000004f1"),
    "7c41" + "0" * 56 + "a9e2",
    date(2033, 10, 9),
    date(2026, 10, 9),
)
ADDITION = UUID("00000000-0000-4000-8000-0000000000a2")
HANNAH = UUID("00000000-0000-4000-8000-00000000004c")
MEMO = UUID("00000000-0000-4000-8000-0000000000e2")


def _manifest(description: str = "PI-02 alternative procedure memo") -> bytes:
    return aa.addition_manifest(
        addition_id=ADDITION,
        archive=ARCHIVE,
        evidence_version_id=MEMO,
        evidence_sha256="e" * 64,
        reason_code="au_c_585_omitted_procedure",
        description=description,
        added_by=HANNAH,
    )


def test_the_addition_manifest_names_the_original_seal_and_is_canonical() -> None:
    body = _manifest()
    parsed = json.loads(body)
    assert parsed["original_seal_sha256"] == ARCHIVE.seal_sha256
    assert parsed["reason_code"] == "au_c_585_omitted_procedure"
    assert body == json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    # The description is carried by its hash only; the text stays sealed in the row.
    assert "PI-02" not in body.decode()


def test_the_addition_hash_is_stable_and_rebuilt_byte_for_byte() -> None:
    assert hashlib.sha256(_manifest()).hexdigest() == hashlib.sha256(_manifest()).hexdigest()
    assert _manifest() != _manifest("another memo")


def test_the_addition_manifest_has_its_own_records_class() -> None:
    assert aa.RECORD_CLASS in RECORD_CLASSES


def test_a_tampered_row_changes_the_merkle_root() -> None:
    leaves = [
        Leaf("evidence_version", "v1", "a" * 64),
        Leaf("row", "workpaper:w1", "b" * 64),
        Leaf("run_record", "r1", "c" * 64),
    ]
    sealed = merkle_root(leaves)
    tampered = [*leaves[:1], Leaf("row", "workpaper:w1", "d" * 64), *leaves[2:]]
    assert merkle_root(tampered) != sealed
    assert merkle_root(list(reversed(leaves))) == sealed  # order-free: the leaves are sorted


def test_only_a_live_person_adds_or_decides() -> None:
    from types import SimpleNamespace

    for kind in ("agent", "system", "support"):
        ctx = SimpleNamespace(tenant=SimpleNamespace(actor_kind=kind), client=None)
        with pytest.raises(Exception, match="role"):
            aa._person(ctx, "archive_addition.approve")  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage]


def test_the_monthly_sweep_is_declared() -> None:
    (job,) = aa.SCHEDULES
    assert job.id == aa.SWEEP_ID and job.workflow is aa.SealVerifySweepWorkflow
    assert job.every.days == 30


def test_the_error_codes() -> None:
    assert aa.ArchiveNotLocked.code == "archive_not_locked"
    assert aa.AdditionDecided.code == "addition_already_decided"
    assert aa.EvidenceNotFound.code == "evidence_version_invalid"
