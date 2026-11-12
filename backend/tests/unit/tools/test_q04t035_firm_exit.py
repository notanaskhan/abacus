"""Q-04-T035 (TASK-7800): the firm exit's archive check and its certificate.

AC: the rehearsal tenant exits end to end with a dual-approved export, verified checksums and a
certificate naming both dates. Here, offline: a firm export archive in the Q-02-T47 layout
verifies (outer manifest, index, each A-01 package), any tampering fails it, and the certificate
is refused unless the export verified, two different people stand behind it and the tenant key is
PendingDeletion after the export was built. The rehearsal against a real export is
`tests/integration/test_q04t035_firm_exit_rehearsal.py`.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from abacus_tools import firm_exit

EXPORT = "7d1b2c3e-0000-4000-8000-000000000001"
ENGAGEMENT = "7d1b2c3e-0000-4000-8000-0000000000e1"
REQUESTER = "7d1b2c3e-0000-4000-8000-0000000000a1"
APPROVER = "7d1b2c3e-0000-4000-8000-0000000000a2"
BUILT = "2026-11-12T10:00:00Z"
DELETION = {
    "KeyId": "arn:aws:kms:us-east-2:000000000000:key/mrk-0000",
    "KeyState": "PendingDeletion",
    "PendingWindowInDays": 30,
    "DeletionDate": "2026-12-12T10:00:00Z",
}


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _package() -> bytes:
    files = {"README.txt": b"readme", "evidence/Cash/bank.pdf": b"%PDF-1.7 x"}
    manifest = json.dumps(
        {"files": [{"path": p, "sha256": _sha(b)} for p, b in sorted(files.items())]}
    ).encode()
    listed = {**files, "manifest.json": manifest}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, body in listed.items():
            archive.writestr(name, body)
        archive.writestr("manifest.sha256", f"{_sha(manifest)}  manifest.json\n")
        archive.writestr(
            "checksums.sha256", "".join(f"{_sha(b)}  {p}\n" for p, b in sorted(listed.items()))
        )
    return out.getvalue()


def _archive(
    path: Path,
    *,
    package: bytes | None = None,
    approved_by: str = APPROVER,
    extra: dict[str, bytes] | None = None,
) -> tuple[Path, str]:
    inner = package if package is not None else _package()
    package_path = f"packages/{ENGAGEMENT}.zip"
    index = json.dumps(
        {
            "format": "accrued-firm-export",
            "format_version": "0.2",
            "export_id": EXPORT,
            "tenant_id": "7d1b2c3e-0000-4000-8000-0000000000f0",
            "scope": "firm",
            "requested_by": REQUESTER,
            "approved_by": approved_by,
            "requested_at": "2026-11-12T09:00:00Z",
            "built_at": BUILT,
            "packages": [
                {
                    "engagement_id": ENGAGEMENT,
                    "path": package_path,
                    "bundle_sha256": _sha(_package()),
                    "bytes": len(_package()),
                }
            ],
            "omitted": [{"engagement_id": "e2", "reason": "not_readable"}],
        }
    ).encode()
    listed = [
        {"path": "index.json", "bytes": len(index), "sha256": _sha(index)},
        {"path": package_path, "bytes": len(_package()), "sha256": _sha(_package())},
    ]
    manifest = json.dumps({"format_version": "0.2", "export_id": EXPORT, "files": listed}).encode()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("index.json", index)
        archive.writestr(package_path, inner)
        for name, body in (extra or {}).items():
            archive.writestr(name, body)
        archive.writestr("manifest.json", manifest)
    return path, _sha(manifest)


def _report(tmp_path: Path, **kwargs: object) -> firm_exit.Report:
    archive, manifest_sha = _archive(tmp_path / "export.zip", **kwargs)  # type: ignore[arg-type]
    return firm_exit.verify(
        archive,
        tmp_path / "out",
        bundle_sha256=_sha(archive.read_bytes()),
        manifest_sha256=manifest_sha,
    )


def test_ac_a_good_firm_export_verifies_with_every_package(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert report.ok, report.problems
    assert report.files == 2 and report.export_id == EXPORT
    assert report.packages == [{"engagement_id": ENGAGEMENT, "files": 5, "ok": True}]
    assert report.omitted == [{"engagement_id": "e2", "reason": "not_readable"}]


def test_a_wrong_bundle_digest_fails(tmp_path: Path) -> None:
    archive, _ = _archive(tmp_path / "export.zip")
    report = firm_exit.verify(archive, tmp_path / "out", bundle_sha256="0" * 64)
    assert not report.ok and "bundle_sha256" in report.problems[0]


def test_a_tampered_package_fails_the_manifest_and_its_own_check(tmp_path: Path) -> None:
    tampered = _package().replace(b"readme", b"README")
    report = _report(tmp_path, package=tampered)
    assert not report.ok
    assert any("differs from manifest.json" in p for p in report.problems)


def test_a_file_the_manifest_does_not_name_fails(tmp_path: Path) -> None:
    report = _report(tmp_path, extra={"stray.txt": b"x"})
    assert report.problems == ["stray.txt: in the archive but not in manifest.json"]


def test_the_folder_must_be_new(tmp_path: Path) -> None:
    archive, _ = _archive(tmp_path / "export.zip")
    (tmp_path / "out").mkdir()
    assert firm_exit.main(["verify", str(archive), "--into", str(tmp_path / "out")]) == 2


def test_ac_the_certificate_names_both_dates_and_both_people(tmp_path: Path) -> None:
    report = _report(tmp_path).as_json()
    made = firm_exit.certificate(
        report, DELETION, firm="PF-X1", issued_at=datetime(2026, 11, 12, 11, tzinfo=UTC)
    )
    assert made["dates"] == {"export_verified": BUILT, "key_deleted": "2026-12-12T10:00:00Z"}
    export = made["export"]
    assert isinstance(export, dict)
    assert (export["requested_by"], export["approved_by"]) == (REQUESTER, APPROVER)
    body = {k: v for k, v in made.items() if k != "sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    assert made["sha256"] == _sha(canonical)


def test_the_cli_writes_the_certificate_once(tmp_path: Path) -> None:
    (tmp_path / "report.json").write_text(json.dumps(_report(tmp_path).as_json()))
    (tmp_path / "kms.json").write_text(json.dumps({**DELETION, "DeletionDate": 1797069600}))
    args = [
        "certificate",
        "--verification",
        str(tmp_path / "report.json"),
        "--key-deletion",
        str(tmp_path / "kms.json"),
        "--firm",
        "PF-X1",
        "--out",
        str(tmp_path / "certificate.json"),
    ]
    assert firm_exit.main(args) == 0
    written = json.loads((tmp_path / "certificate.json").read_text())
    assert written["key"]["deletion_date"].startswith("2026-12-12")
    assert firm_exit.main(args) == 1  # never overwritten


@pytest.mark.parametrize(
    ("change", "deletion", "reason"),
    [
        ({"ok": False}, DELETION, "did not verify"),
        ({"approved_by": REQUESTER}, DELETION, "two different people"),
        ({"approved_by": None}, DELETION, "two different people"),
        ({}, {**DELETION, "KeyState": "Enabled"}, "not PendingDeletion"),
        ({}, {**DELETION, "DeletionDate": "2026-11-11T00:00:00Z"}, "not after"),
        ({}, {**DELETION, "KeyId": ""}, "no KeyId"),
    ],
)
def test_the_certificate_is_refused_without_its_facts(
    tmp_path: Path, change: dict[str, object], deletion: dict[str, object], reason: str
) -> None:
    report = {**_report(tmp_path).as_json(), **change}
    with pytest.raises(firm_exit.ExitRefused, match=reason):
        firm_exit.certificate(report, deletion, firm="PF-X1", issued_at=datetime.now(UTC))
