"""The deterministic engagement export package (A-01-T19; SPEC-344 §7; ADR-036, ADR-042, ADR-052;
DEC-436). PROTECTED.

Pure: given the files (their bytes and roles) and the manifest's facts, write the ZIP. The same
inputs give the same bytes (AC-10):
- entries sorted by path, each with the timestamp `generated_at` (UTC), mode 0644, the Unix
  creator, `ZIP_DEFLATED` at level 9 and no extra fields;
- `manifest.json` canonical (sorted keys, UTF-8, no insignificant space) and validated by
  `EngagementExportManifest` before anything is written;
- `index.xlsx` rendered from `index.csv`'s rows with ADR-042's pattern (fixed properties, the
  workbook's own ZIP rebuilt with fixed timestamps), every cell a string with formula leads
  quoted;
- `checksums.sha256` lists every file but itself and `manifest.sha256`; `manifest.sha256` names
  `manifest.json`; both in `sha256sum` format, so `shasum -a 256 -c checksums.sha256` passes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import IO, Final, cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from abacus.modules.evidence.export_manifest import (
    AUDIT_TRAIL,
    CHECKSUMS,
    FORMAT,
    FORMAT_VERSION,
    INDEX_COLUMNS,
    INDEX_CSV,
    INDEX_XLSX,
    MANIFEST,
    MANIFEST_SHA256,
    README,
    EngagementExportManifest,
    FileRole,
    ManifestClient,
    ManifestCounts,
    ManifestEngagement,
    ManifestEvidence,
    ManifestFile,
    ManifestPerson,
    ManifestScope,
    ManifestSection,
)
from abacus.modules.evidence.render import (
    _normalised as normalised,  # pyright: ignore[reportPrivateUsage] -- the same determinism
)

_FORMULA_LEADS: Final = ("=", "+", "-", "@", "\t", "\r")
_MAX_CELL: Final = 32_767
_BOLD: Final = Font(bold=True)
README_TEXT: Final = """\
Accrued engagement export (format {format} {version})

This package holds an audit engagement's PBC binder as it stood when it was built:

  manifest.json       what the package holds: every file, its SHA-256 and its role
  manifest.sha256     the SHA-256 of manifest.json
  checksums.sha256    the SHA-256 of every other file
  index.csv           one row per request; index.xlsx holds the same rows
  evidence/           the accepted files, by category and request
  provenance/         fulfilments, review decisions, screening results and citations
  audit_trail/        the engagement's audit events, identifiers only (when included)

Verify the package from its folder:

  shasum -a 256 -c manifest.sha256
  shasum -a 256 -c checksums.sha256

Every cell in the index and provenance files is text. A cell that began with =, +, -, @, a tab
or a carriage return starts with an apostrophe so no spreadsheet reads it as a formula.
"""


class PackageInvalid(ValueError):
    """The files given would not make a valid v1 package (a builder or provider defect)."""


@dataclass(frozen=True)
class PackageFile:
    path: str
    content: bytes
    role: FileRole
    evidence: ManifestEvidence | None = None
    section: str | None = None


@dataclass(frozen=True)
class PackageFacts:
    """The manifest's facts that are not files."""

    export_id: UUID
    kind: str
    generated_at: datetime
    as_of_seq: int
    tenant_id: UUID
    firm_name: str
    client: ManifestClient
    engagement: ManifestEngagement
    requested_by: ManifestPerson
    requested_at: datetime
    scope: ManifestScope
    request_count: int
    requests_without_file: int
    sections: tuple[ManifestSection, ...] = ()


@dataclass(frozen=True)
class BuiltPackage:
    manifest_sha256: str
    bundle_sha256: str
    bytes: int
    file_count: int  # evidence files


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise PackageInvalid("generated_at must be timezone-aware")
    return moment.astimezone(UTC)


def _zip_time(moment: datetime) -> tuple[int, int, int, int, int, int]:
    at = _utc(moment)
    if at.year < 1980:
        raise PackageInvalid("a ZIP timestamp starts in 1980")
    return (at.year, at.month, at.day, at.hour, at.minute, at.second - at.second % 2)


def readme() -> bytes:
    return README_TEXT.format(format=FORMAT, version=FORMAT_VERSION).encode("utf-8")


def _cell(sheet: Worksheet, value: str, *, bold: bool = False) -> Cell:
    cell = WriteOnlyCell(sheet, value=value[:_MAX_CELL])
    cell.data_type = "s"  # always a string: a leading "=" never becomes a formula
    if value.startswith(_FORMULA_LEADS) or value.startswith("'"):
        cell.quotePrefix = True
    if bold:
        cell.font = _BOLD
    return cell


def index_rows(index_csv: bytes) -> list[list[str]]:
    """`index.csv`'s data rows, checked against format 1.0's columns."""
    rows = list(csv.reader(io.StringIO(index_csv.decode("utf-8"), newline="")))
    if not rows or tuple(rows[0]) != INDEX_COLUMNS:
        raise PackageInvalid("index.csv must start with format 1.0's columns")
    if any(len(r) != len(INDEX_COLUMNS) for r in rows[1:]):
        raise PackageInvalid("every index row has format 1.0's columns")
    return rows[1:]


def index_xlsx(index_csv: bytes, generated_at: datetime) -> bytes:
    """`index.xlsx` from `index.csv`'s rows (ADR-042: identical rows, identical bytes)."""
    moment = _utc(generated_at)
    workbook = Workbook(write_only=True)
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = moment.replace(tzinfo=None)
    properties.modified = moment.replace(tzinfo=None)
    sheet = cast(Worksheet, workbook.create_sheet("Index"))
    sheet.append([_cell(sheet, name, bold=True) for name in INDEX_COLUMNS])
    for row in index_rows(index_csv):
        sheet.append([_cell(sheet, value) for value in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return normalised(buffer.getvalue(), moment)


def _manifest(facts: PackageFacts, files: Sequence[PackageFile]) -> bytes:
    listed = sorted(files, key=lambda f: f.path)
    evidence = sum(1 for f in listed if f.role == "evidence")
    manifest = EngagementExportManifest(
        format=FORMAT,
        format_version=FORMAT_VERSION,
        export_id=facts.export_id,
        kind=facts.kind,  # pyright: ignore[reportArgumentType] -- validated by the model
        generated_at=_utc(facts.generated_at),
        as_of_seq=facts.as_of_seq,
        tenant_id=facts.tenant_id,
        firm_name=facts.firm_name,
        client=facts.client,
        engagement=facts.engagement,
        requested_by=facts.requested_by,
        requested_at=_utc(facts.requested_at),
        scope=facts.scope,
        counts=ManifestCounts(
            request_count=facts.request_count,
            file_count=evidence,
            requests_without_file=facts.requests_without_file,
        ),
        index_columns=list(INDEX_COLUMNS),
        sections=list(facts.sections),
        files=[
            ManifestFile(
                path=f.path,
                sha256=_sha(f.content),
                bytes=len(f.content),
                role=f.role,
                evidence=f.evidence,
                section=f.section,
            )
            for f in listed
        ],
    )
    return json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def build_package(
    facts: PackageFacts, files: Sequence[PackageFile], out: IO[bytes]
) -> BuiltPackage:
    """Write the package to `out` (from its current position) and return its digests. `files`
    holds every file but the README, index.xlsx, the manifest and the checksum files, which are
    made here; index.csv must be among them."""
    by_path = {f.path: f for f in files}
    if len(by_path) != len(files):
        raise PackageInvalid("two files share a path")
    reserved = {README, INDEX_XLSX, MANIFEST, MANIFEST_SHA256, CHECKSUMS}
    if reserved & set(by_path):
        raise PackageInvalid("the builder writes the README, index.xlsx, manifest and checksums")
    if INDEX_CSV not in by_path:
        raise PackageInvalid("a package has an index")
    if (AUDIT_TRAIL in by_path) != facts.scope.include_audit_trail:
        raise PackageInvalid("the audit trail is in the package exactly when the scope asks")
    made = [
        PackageFile(README, readme(), "readme"),
        PackageFile(
            INDEX_XLSX, index_xlsx(by_path[INDEX_CSV].content, facts.generated_at), "index"
        ),
    ]
    listed = [*files, *made]
    try:
        manifest = _manifest(facts, listed)
    except ValueError as exc:  # pydantic's ValidationError included: never a partial package
        raise PackageInvalid(str(exc)) from exc
    manifest_sha = _sha(manifest)
    contents = {f.path: f.content for f in listed} | {MANIFEST: manifest}
    checksums = "".join(f"{_sha(contents[p])}  {p}\n" for p in sorted(contents)).encode()
    contents |= {CHECKSUMS: checksums, MANIFEST_SHA256: f"{manifest_sha}  {MANIFEST}\n".encode()}
    stamp = _zip_time(facts.generated_at)
    start = out.tell()
    digest = hashlib.sha256()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(contents):
            entry = zipfile.ZipInfo(path, date_time=stamp)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3  # the same on every platform
            archive.writestr(entry, contents[path], compresslevel=9)
    end = out.tell()
    out.seek(start)
    remaining = end - start
    while remaining > 0:
        chunk = out.read(min(remaining, 1 << 20))
        if not chunk:
            break
        digest.update(chunk)
        remaining -= len(chunk)
    out.seek(start)
    return BuiltPackage(
        manifest_sha256=manifest_sha,
        bundle_sha256=digest.hexdigest(),
        bytes=end - start,
        file_count=sum(1 for f in listed if f.role == "evidence"),
    )
