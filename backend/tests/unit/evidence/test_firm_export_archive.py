"""The firm export's archive bytes and its row checks, without a database or a worker (Q-02-T43,
Q-02-T47; DEC-508, DEC-640; Q-03-T147).

`test_q02t43_firm_export.py` and `test_q02t47_firm_export_packages.py` prove the build end to end;
these pin what a mutation run decides on the unit suites alone: the archive's files and their
order, `index.json` and `manifest.json` byte for byte, the fixed entry times and compression, the
digest the build reports, and who an export acts for.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

import pytest

from abacus.modules.evidence import firm_export_activities as fea
from abacus.modules.evidence.firm_export_models import FirmExport
from abacus.modules.evidence.firm_export_packages import EngagementPackage, FirmPackages, Omitted

fea_json = fea._json  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_iso = fea._iso  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_digest = fea._digest  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_entry = fea._entry  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_stored = fea._stored  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_system = fea._system  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_fields = fea._fields  # pyright: ignore[reportPrivateUsage] -- the helper under test
fea_approved = fea._approved  # pyright: ignore[reportPrivateUsage] -- the helper under test

TENANT = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
EXPORT = uuid.UUID("00000000-0000-4000-8000-0000000000e0")
REQUESTER = uuid.UUID("00000000-0000-4000-8000-000000000001")
APPROVER = uuid.UUID("00000000-0000-4000-8000-000000000002")
ENG_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
ENG_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
ENG_C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
WI = uuid.UUID("00000000-0000-4000-8000-0000000000f1")
REQUESTED = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
BUILT = datetime(2026, 9, 15, 9, 0, 5, tzinfo=UTC)


def _row(**over: object) -> FirmExport:
    fields: dict[str, Any] = {  # Any: the model's keyword arguments
        "id": EXPORT,
        "tenant_id": TENANT,
        "scope": "firm",
        "requested_by": REQUESTER,
        "requested_at": REQUESTED,
        "approver_id": APPROVER,
        "decided_by": APPROVER,
        "status": "building",
    }
    fields.update(over)
    return FirmExport(**fields)


def _package(engagement_id: uuid.UUID, body: bytes) -> EngagementPackage:
    return EngagementPackage(
        engagement_id=engagement_id,
        work_item_id=WI,
        path=f"packages/{engagement_id}.zip",
        handle=io.BytesIO(body),
        bundle_sha256=hashlib.sha256(body).hexdigest(),
        manifest_sha256="m" * 64,
        bytes=len(body),
        file_count=3,
        request_count=2,
    )


def _expected_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


# --- small helpers -------------------------------------------------------------------------------


def test_json_is_sorted_indented_ascii_with_a_newline() -> None:
    assert fea_json({"b": "é", "a": 1}) == b'{\n  "a": 1,\n  "b": "\\u00e9"\n}\n'


def test_iso_writes_utc_as_z() -> None:
    assert fea_iso(BUILT) == "2026-09-15T09:00:05Z"


def test_workflow_id_names_the_firm_and_export() -> None:
    assert fea.workflow_id(TENANT, EXPORT) == f"firm_export:{TENANT}:{EXPORT}"


def test_digest_reads_from_the_start_and_rewinds() -> None:
    body = b"x" * (1024 * 1024 + 5)
    handle = io.BytesIO(body)
    handle.seek(10)
    assert fea_digest(handle) == (hashlib.sha256(body).hexdigest(), len(body))
    assert handle.tell() == 0


def test_digest_of_nothing() -> None:
    assert fea_digest(io.BytesIO()) == (hashlib.sha256(b"").hexdigest(), 0)


def test_entry_is_deflated_at_the_fixed_time() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        fea_entry(archive, "a.txt", b"hello hello hello")
    with zipfile.ZipFile(out) as archive:
        info = archive.getinfo("a.txt")
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert archive.read("a.txt") == b"hello hello hello"


def test_stored_copies_the_whole_package_as_is() -> None:
    body = bytes(range(256)) * 8193  # more than one 1 MiB chunk
    source = io.BytesIO(body)
    source.seek(100)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", allowZip64=True) as archive:
        fea_stored(archive, "packages/x.zip", source)
    with zipfile.ZipFile(out) as archive:
        info = archive.getinfo("packages/x.zip")
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.compress_type == zipfile.ZIP_STORED
        assert archive.read("packages/x.zip") == body


# --- who an export acts for ----------------------------------------------------------------------


def test_system_context_acts_for_the_decider() -> None:
    ctx = fea_system(_row())
    assert ctx.tenant_id == TENANT
    assert ctx.actor_kind == "system"
    assert ctx.actor_id == f"firm_export:build:{EXPORT}"
    assert ctx.on_behalf_of_user_id == APPROVER


def test_system_context_falls_back_to_the_approver_and_names_its_purpose() -> None:
    other = uuid.UUID(int=77)
    ctx = fea_system(_row(decided_by=None, approver_id=other), "expire")
    assert ctx.actor_id == f"firm_export:expire:{EXPORT}"
    assert ctx.on_behalf_of_user_id == other


def test_fields_are_identifiers_only() -> None:
    assert fea_fields(_row()) == {
        "export_id": EXPORT,
        "requested_by": REQUESTER,
        "approver_user_id": APPROVER,
    }


def test_approved_needs_the_named_approver_and_two_people() -> None:
    assert fea_approved(_row()) is True
    assert fea_approved(None) is False
    assert fea_approved(_row(decided_by=None)) is False
    assert fea_approved(_row(decided_by=uuid.UUID(int=5))) is False  # not the named approver
    assert fea_approved(_row(approver_id=REQUESTER, decided_by=REQUESTER)) is False  # one person


# --- the archive ---------------------------------------------------------------------------------


def test_archive_without_packages() -> None:
    out = io.BytesIO()
    digest = fea.write_archive(out, _row(), BUILT)
    index = _expected_json(
        {
            "format": "accrued-firm-export",
            "format_version": "0.2",
            "export_id": str(EXPORT),
            "tenant_id": str(TENANT),
            "scope": "firm",
            "requested_by": str(REQUESTER),
            "approved_by": str(APPROVER),
            "requested_at": "2026-09-14T14:24:00Z",
            "built_at": "2026-09-15T09:00:05Z",
            "packages": [],
            "omitted": [],
        }
    )
    manifest = _expected_json(
        {
            "format_version": "0.2",
            "export_id": str(EXPORT),
            "files": [
                {
                    "path": "index.json",
                    "bytes": len(index),
                    "sha256": hashlib.sha256(index).hexdigest(),
                }
            ],
        }
    )
    assert digest == hashlib.sha256(manifest).hexdigest()
    with zipfile.ZipFile(out) as archive:
        assert archive.namelist() == ["index.json", "manifest.json"]
        assert archive.read("index.json") == index
        assert archive.read("manifest.json") == manifest
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_DEFLATED


def test_archive_with_packages_sorted_and_omitted_sorted() -> None:
    b_body, a_body = b"package b bytes", b"package a bytes!"
    found = FirmPackages(
        packages=[_package(ENG_B, b_body), _package(ENG_A, a_body)],
        omitted=[Omitted(ENG_C, "no_binders"), Omitted(uuid.UUID(int=1), "not_readable")],
    )
    out = io.BytesIO()
    digest = fea.write_archive(out, _row(scope="engagements"), BUILT, found)
    with zipfile.ZipFile(out) as archive:
        assert archive.namelist() == [
            "index.json",
            f"packages/{ENG_A}.zip",
            f"packages/{ENG_B}.zip",
            "manifest.json",
        ]
        assert archive.read(f"packages/{ENG_A}.zip") == a_body
        assert archive.read(f"packages/{ENG_B}.zip") == b_body
        assert archive.getinfo(f"packages/{ENG_A}.zip").compress_type == zipfile.ZIP_STORED
        index_bytes = archive.read("index.json")
        manifest_bytes = archive.read("manifest.json")
    index = json.loads(index_bytes)
    assert index["scope"] == "engagements"
    assert index["packages"] == [
        {
            "engagement_id": str(eng),
            "work_item_id": str(WI),
            "path": f"packages/{eng}.zip",
            "bundle_sha256": hashlib.sha256(body).hexdigest(),
            "manifest_sha256": "m" * 64,
            "bytes": len(body),
            "file_count": 3,
            "request_count": 2,
        }
        for eng, body in ((ENG_A, a_body), (ENG_B, b_body))
    ]
    assert index["omitted"] == [
        {"engagement_id": str(uuid.UUID(int=1)), "reason": "not_readable"},
        {"engagement_id": str(ENG_C), "reason": "no_binders"},
    ]
    manifest = json.loads(manifest_bytes)
    assert manifest == {
        "format_version": "0.2",
        "export_id": str(EXPORT),
        "files": [
            {
                "path": "index.json",
                "bytes": len(index_bytes),
                "sha256": hashlib.sha256(index_bytes).hexdigest(),
            },
            {
                "path": f"packages/{ENG_A}.zip",
                "bytes": len(a_body),
                "sha256": hashlib.sha256(a_body).hexdigest(),
            },
            {
                "path": f"packages/{ENG_B}.zip",
                "bytes": len(b_body),
                "sha256": hashlib.sha256(b_body).hexdigest(),
            },
        ],
    }
    assert digest == hashlib.sha256(manifest_bytes).hexdigest()


def test_archive_is_the_same_bytes_for_the_same_row() -> None:
    first, second = io.BytesIO(), io.BytesIO()
    assert fea.write_archive(first, _row(), BUILT) == fea.write_archive(second, _row(), BUILT)
    assert first.getvalue() == second.getvalue()


@pytest.mark.parametrize("found", [None, FirmPackages([], [])])
def test_archive_with_nothing_found_lists_nothing(found: FirmPackages | None) -> None:
    out = io.BytesIO()
    fea.write_archive(out, _row(), BUILT, found)
    with zipfile.ZipFile(out) as archive:
        index = json.loads(archive.read("index.json"))
    assert index["packages"] == []
    assert index["omitted"] == []
