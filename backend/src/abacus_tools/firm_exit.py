"""Firm exit: verify a firm export archive and write the exit certificate (Q-04-T035; ADR-034,
ADR-156, ADR-179; DEC-72; `docs/runbooks/firm-exit.md`, RB-13).

    python -m abacus_tools.firm_exit verify <firm-export.zip> --into <new empty folder> \
        [--bundle-sha256 <hex>] [--manifest-sha256 <hex>]
    python -m abacus_tools.firm_exit certificate --verification <verify report.json> \
        --key-deletion <ScheduleKeyDeletion response.json> --firm <pilot code or firm id> \
        --out <certificate.json>

A firm leaves by export, then crypto-shredding (ADR-034): it receives everything it holds as one
dual-approved firm export (DEC-72, Q-02-T43, one A-01 package per engagement, Q-02-T47), and after
the agreed grace period the key custodian schedules the deletion of its per-tenant KMS key
(ADR-156: only the `abacus-key-custodian` break-glass role may). This tool does the two checks the
runbook needs and nothing else; it calls no AWS API and reads no database.

**verify** proves the archive is complete and usable without Accrued:

- the archive's SHA-256 is the export row's `bundle_sha256` and `manifest.json`'s is its
  `manifest_sha256` (both shown on the firm's export history, ADM-06), when given;
- every file `manifest.json` lists exists with its size and digest, and nothing else is in the
  archive;
- `index.json` accounts for every package it names (digest and size), and each package unpacks
  into its own folder and passes `abacus_tools.package_check` (both checksum files, nothing
  unlisted, the manifest agrees).

The report is JSON of counts, ids, digests and dates (never content). Exit 0 when the archive
verifies, 1 when it does not, 2 when it was refused before unpacking.

**certificate** writes the exit certificate from a passing verify report and the custodian's
`ScheduleKeyDeletion` answer (`aws kms schedule-key-deletion … --output json`). It names both
dates: the day the export was built and verified, and the day the key is deleted. It refuses a
failing report, a key that is not `PendingDeletion`, a deletion date before the export was built,
and an export without two different people behind it. The certificate carries its own SHA-256 over
its canonical JSON, and states that COMPLIANCE-locked ciphertext persists until its floor date but
can no longer be opened (ADR-156).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final, cast

from abacus_tools import package_check

FORMAT: Final = "accrued-firm-export"
CERTIFICATE_FORMAT: Final = "accrued-firm-exit-certificate"
CERTIFICATE_VERSION: Final = "1"
_META: Final = frozenset({"manifest.json"})


class ExitRefused(ValueError):
    """The certificate would not be written: the facts do not support it."""


@dataclass
class Report:
    archive_sha256: str = ""
    manifest_sha256: str = ""
    export_id: str | None = None
    tenant_id: str | None = None
    requested_by: str | None = None
    approved_by: str | None = None
    requested_at: str | None = None
    built_at: str | None = None
    files: int = 0
    packages: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    omitted: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    problems: list[str] = field(default_factory=list[str])

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_json(self) -> dict[str, object]:
        return {"ok": self.ok, **self.__dict__}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(raw: bytes, name: str) -> dict[str, object]:
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise package_check.PackageRefused(f"{name} is not a JSON object")
    return cast(dict[str, object], loaded)


def _entries(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], e) for e in cast(list[object], value) if isinstance(e, dict)]


def _str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def verify(
    archive: Path,
    into: Path,
    *,
    bundle_sha256: str | None = None,
    manifest_sha256: str | None = None,
    max_bytes: int = package_check.DEFAULT_MAX_BYTES,
) -> Report:
    """Unpack the firm export into `into` (which must not exist) and verify it."""
    report = Report(archive_sha256=_sha256_file(archive))
    if bundle_sha256 is not None and report.archive_sha256 != bundle_sha256.lower():
        report.problems.append("archive: SHA-256 differs from the export's bundle_sha256")
    package_check.unpack(archive, into, max_bytes)
    manifest_path = into / "manifest.json"
    index_path = into / "index.json"
    if not manifest_path.is_file() or not index_path.is_file():
        report.problems.append("archive: manifest.json or index.json is missing")
        return report
    manifest_bytes = manifest_path.read_bytes()
    report.manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 is not None and report.manifest_sha256 != manifest_sha256.lower():
        report.problems.append("manifest.json: SHA-256 differs from the export's manifest_sha256")
    manifest = _json_object(manifest_bytes, "manifest.json")
    index = _json_object(index_path.read_bytes(), "index.json")
    if index.get("format") != FORMAT:
        report.problems.append(f"index.json: format is not {FORMAT}")
    if manifest.get("export_id") != index.get("export_id"):
        report.problems.append("manifest.json and index.json name different exports")
    report.export_id = _str(index.get("export_id"))
    report.tenant_id = _str(index.get("tenant_id"))
    report.requested_by = _str(index.get("requested_by"))
    report.approved_by = _str(index.get("approved_by"))
    report.requested_at = _str(index.get("requested_at"))
    report.built_at = _str(index.get("built_at"))

    listed: dict[str, dict[str, object]] = {}
    for entry in _entries(manifest.get("files")):
        path = _str(entry.get("path"))
        if path is None or path in listed:
            report.problems.append(f"manifest.json: a missing or repeated path: {path!r}")
            continue
        listed[path] = entry
        target = into / PurePosixPath(path)
        if not target.is_file():
            report.problems.append(f"{path}: listed but not in the archive")
            continue
        if entry.get("bytes") != target.stat().st_size or entry.get("sha256") != _sha256_file(
            target
        ):
            report.problems.append(f"{path}: size or SHA-256 differs from manifest.json")
    present = {p.relative_to(into).as_posix() for p in into.rglob("*") if p.is_file()} - _META
    for extra in sorted(present - set(listed)):
        report.problems.append(f"{extra}: in the archive but not in manifest.json")
    report.files = len(listed)

    for package in _entries(index.get("packages")):
        path = _str(package.get("path"))
        engagement = _str(package.get("engagement_id"))
        if path is None or path not in listed:
            report.problems.append(f"index.json: package {engagement} is not in manifest.json")
            continue
        if listed[path].get("sha256") != package.get("bundle_sha256") or listed[path].get(
            "bytes"
        ) != package.get("bytes"):
            report.problems.append(f"{path}: index.json and manifest.json disagree")
        folder = into.parent / f"{into.name}.packages" / (engagement or PurePosixPath(path).stem)
        try:
            package_check.unpack(into / PurePosixPath(path), folder, max_bytes)
        except (package_check.PackageRefused, zipfile.BadZipFile) as exc:
            report.problems.append(f"{path}: refused: {exc}")
            continue
        checked = package_check.verify(folder)
        if not checked.ok:
            report.problems.append(f"{path}: the engagement package does not verify")
        report.packages.append(
            {"engagement_id": engagement, "files": checked.files, "ok": checked.ok}
        )
    report.omitted = [
        {"engagement_id": o.get("engagement_id"), "reason": o.get("reason")}
        for o in _entries(index.get("omitted"))
    ]
    return report


def _when(value: object, name: str) -> datetime:
    if isinstance(value, (int, float)):  # the AWS CLI answers epoch seconds
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise ExitRefused(f"{name} is missing")


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def certificate(
    verification: Mapping[str, object],
    key_deletion: Mapping[str, object],
    *,
    firm: str,
    issued_at: datetime,
) -> dict[str, object]:
    """The exit certificate, with its own SHA-256 over the canonical JSON of the rest."""
    if verification.get("ok") is not True:
        raise ExitRefused("the firm export did not verify")
    requested_by, approved_by = verification.get("requested_by"), verification.get("approved_by")
    if not requested_by or not approved_by or requested_by == approved_by:
        raise ExitRefused("the export needs two different people: a requester and an approver")
    if key_deletion.get("KeyState") != "PendingDeletion":
        raise ExitRefused("the tenant key is not PendingDeletion")
    key_id = _str(key_deletion.get("KeyId"))
    if not key_id:
        raise ExitRefused("the key deletion answer names no KeyId")
    built = _when(verification.get("built_at"), "the export's built_at")
    deleted = _when(key_deletion.get("DeletionDate"), "the key's DeletionDate")
    if deleted <= built:
        raise ExitRefused("the key deletion date is not after the export was built")
    body: dict[str, object] = {
        "format": CERTIFICATE_FORMAT,
        "format_version": CERTIFICATE_VERSION,
        "firm": firm,
        "tenant_id": verification.get("tenant_id"),
        "export": {
            "export_id": verification.get("export_id"),
            "requested_by": requested_by,
            "approved_by": approved_by,
            "requested_at": verification.get("requested_at"),
            "built_at": _iso(built),
            "archive_sha256": verification.get("archive_sha256"),
            "manifest_sha256": verification.get("manifest_sha256"),
            "packages": len(_entries(verification.get("packages"))),
            "omitted": len(_entries(verification.get("omitted"))),
        },
        "key": {
            "key_id": key_id,
            "key_state": "PendingDeletion",
            "pending_window_days": key_deletion.get("PendingWindowInDays"),
            "deletion_date": _iso(deleted),
        },
        "dates": {"export_verified": _iso(built), "key_deleted": _iso(deleted)},
        "statement": (
            "The firm received a dual-approved export of everything it held, verified against "
            "its manifest. Its per-tenant key is scheduled for deletion on the key_deleted date; "
            "from then on its ciphertext cannot be opened. Objects under COMPLIANCE Object Lock "
            "persist as unreadable bytes until their retention floor date (ADR-156)."
        ),
        "issued_at": _iso(issued_at),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {**body, "sha256": hashlib.sha256(canonical).hexdigest()}


def _load(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ExitRefused(f"{path} is not a JSON object")
    return cast(dict[str, object], loaded)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.firm_exit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--into", type=Path, required=True, help="a folder that does not exist")
    check.add_argument("--bundle-sha256")
    check.add_argument("--manifest-sha256")
    check.add_argument("--max-bytes", type=int, default=package_check.DEFAULT_MAX_BYTES)
    cert = sub.add_parser("certificate")
    cert.add_argument("--verification", type=Path, required=True)
    cert.add_argument("--key-deletion", type=Path, required=True)
    cert.add_argument("--firm", required=True, help="the pilot code or firm id, never a name")
    cert.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        try:
            report = verify(
                args.archive,
                args.into,
                bundle_sha256=args.bundle_sha256,
                manifest_sha256=args.manifest_sha256,
                max_bytes=args.max_bytes,
            )
        except (package_check.PackageRefused, zipfile.BadZipFile, ValueError) as exc:
            print(json.dumps({"ok": False, "refused": str(exc)}), file=sys.stderr)
            return 2
        print(json.dumps(report.as_json(), indent=2))
        return 0 if report.ok else 1
    try:
        made = certificate(
            _load(args.verification),
            _load(args.key_deletion),
            firm=args.firm,
            issued_at=datetime.now(UTC),
        )
    except (ExitRefused, ValueError) as exc:
        print(json.dumps({"ok": False, "refused": str(exc)}), file=sys.stderr)
        return 1
    if args.out.exists():
        print(json.dumps({"ok": False, "refused": f"{args.out} exists"}), file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(made, indent=2) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out), "sha256": made["sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ExitRefused", "Report", "certificate", "main", "verify"]
