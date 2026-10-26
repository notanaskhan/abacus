"""The engagement export format, manifest v1 (A-01-T17; SPEC-344; ADR-036). Contract:
`docs/contracts/engagement-export-v1.md`.

ADR-036 asks for an open, documented and versioned package. This module is the format's single
source: the package layout, the index columns, the provenance files and the Pydantic model of
`manifest.json`. The JSON schema
`docs/contracts/schemas/engagement-export-manifest-v1.schema.json` is generated from
`EngagementExportManifest` (`python -m abacus_tools.codegen.export_manifest_schema`) and never
edited by hand.

A package (a ZIP) holds, in sorted order with fixed timestamps:

    README.txt                     how to read and verify the package
    manifest.json                  this model, as canonical JSON
    manifest.sha256                the SHA-256 of manifest.json, `sha256sum` format
    checksums.sha256               every other file's SHA-256, `sha256sum` format
    index.csv, index.xlsx          one row per request (INDEX_COLUMNS)
    evidence/NN Category/NN Request title/vN__file
    provenance/fulfilments.csv, review_decisions.csv, screening.csv, citations.csv
    audit_trail/events.jsonl       identifiers and actor grammar only (DEC-60)
    sections/<name>/...            files from registered export sections (`export_package`)

`manifest.json` lists every file except itself, `manifest.sha256` and `checksums.sha256`;
`checksums.sha256` lists every file except itself and `manifest.sha256`, so
`shasum -a 256 -c checksums.sha256` checks the whole package. A change to this model that a v1
reader could not read is format v2 (a new `format_version` and a new schema file); additions a v1
reader can ignore are v1.x (SPEC-344 §8).
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified

FORMAT: Final = "accrued.binder-export"
FORMAT_VERSION: Final = "1.0"
SCHEMA_ID: Final = "urn:accrued:engagement-export:manifest:1.0"
SCHEMA_FILE: Final = "engagement-export-manifest-v1.schema.json"

README: Final = "README.txt"
MANIFEST: Final = "manifest.json"
MANIFEST_SHA256: Final = "manifest.sha256"
CHECKSUMS: Final = "checksums.sha256"
INDEX_CSV: Final = "index.csv"
INDEX_XLSX: Final = "index.xlsx"
AUDIT_TRAIL: Final = "audit_trail/events.jsonl"
EVIDENCE_DIR: Final = "evidence/"
PROVENANCE_DIR: Final = "provenance/"
SECTIONS_DIR: Final = "sections/"
PROVENANCE_FILES: Final = (
    "provenance/citations.csv",
    "provenance/fulfilments.csv",
    "provenance/review_decisions.csv",
    "provenance/screening.csv",
)
# Files that never list themselves (the module docstring).
UNLISTED: Final = frozenset({MANIFEST, MANIFEST_SHA256, CHECKSUMS})
# index.csv and index.xlsx: one row per request in the scope, in binder order. Machine names; the
# XLSX header row shows the same names. `status` is the request's registry label, with
# "Uploaded - needs review (not accepted)" for a file included by `include_unaccepted`.
INDEX_COLUMNS: Final = (
    "category_no",
    "category",
    "request_no",
    "request",
    "status",
    "owed_by",
    "requested_on",
    "due_on",
    "file_count",
    "file_paths",
    "reviewed_by",
    "reviewed_on",
)
MAX_PATH: Final = 180
_FORBIDDEN_SEGMENTS: Final = frozenset({"", ".", ".."})

ExportKind = Literal["binder", "final_binder"]
FileRole = Literal["readme", "index", "evidence", "provenance", "audit_trail", "section"]
# Default scope: accepted files only. `needs_review` appears only with `include_unaccepted`.
ReviewState = Literal["accepted", "needs_review"]


def archive_path_problem(path: str) -> str | None:
    """Why `path` is not a safe archive path, or None (ADR-052; SPEC-344 AC-4): NFC, relative,
    forward slashes, no empty, `.` or `..` segment, no control character, at most 180 characters.
    Client file names are hostile; the builder normalises them before they reach a manifest."""
    if not path or len(path) > MAX_PATH:
        return "length"
    if unicodedata.normalize("NFC", path) != path:
        return "not_nfc"
    if path.startswith("/") or "\\" in path or ":" in path.split("/", 1)[0]:
        return "absolute"
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in path):
        return "control_character"
    if any(segment in _FORBIDDEN_SEGMENTS for segment in path.split("/")):
        return "segment"
    return None


def _archive_path(path: str) -> str:
    problem = archive_path_problem(path)
    if problem is not None:
        raise ValueError(f"not a safe archive path ({problem})")
    return path


ArchivePath = Annotated[
    str, Field(min_length=1, max_length=MAX_PATH), AfterValidator(_archive_path)
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SectionName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


class ManifestPerson(BaseModel):
    """A named person: the requester (INV-5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]


class ManifestClient(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]


class ManifestEngagement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    period_end: Annotated[date | None, classified("internal")]


class ManifestScope(BaseModel):
    """What the person chose on the export sheet (`engagement_exports.scope`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binder_ids: Annotated[list[UUID], Field(min_length=1), classified("internal")]
    include_unaccepted: Annotated[bool, classified("internal")]
    include_audit_trail: Annotated[bool, classified("internal")]


class ManifestCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_count: Annotated[int, Field(ge=0), classified("internal")]
    file_count: Annotated[int, Field(ge=0), classified("internal")]  # evidence files only
    requests_without_file: Annotated[int, Field(ge=0), classified("internal")]


class ManifestEvidence(BaseModel):
    """Where an evidence file came from. Its `sha256` equals the version's stored fingerprint
    (the builder refuses `integrity_mismatch` otherwise)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    review_state: Annotated[ReviewState, classified("internal")]
    media_type: Annotated[str, Field(min_length=3, max_length=127), classified("internal")]


class ManifestFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Annotated[ArchivePath, classified("confidential")]  # request titles and file names
    sha256: Annotated[Sha256, classified("internal")]
    bytes: Annotated[int, Field(ge=0), classified("internal")]
    role: Annotated[FileRole, classified("internal")]
    evidence: Annotated[ManifestEvidence | None, classified("internal")] = None
    section: Annotated[SectionName | None, classified("internal")] = None

    @model_validator(mode="after")
    def _role_fits_path(self) -> Self:
        expected = {
            "readme": self.path == README,
            "index": self.path in (INDEX_CSV, INDEX_XLSX),
            "evidence": self.path.startswith(EVIDENCE_DIR),
            "provenance": self.path in PROVENANCE_FILES,
            "audit_trail": self.path == AUDIT_TRAIL,
            "section": self.section is not None
            and self.path.startswith(f"{SECTIONS_DIR}{self.section}/"),
        }[self.role]
        if not expected:
            raise ValueError(f"{self.path}: does not fit role {self.role}")
        if (self.role == "evidence") != (self.evidence is not None):
            raise ValueError(f"{self.path}: evidence facts belong to evidence files only")
        if (self.role == "section") != (self.section is not None):
            raise ValueError(f"{self.path}: a section name belongs to section files only")
        return self


class ManifestSection(BaseModel):
    """A registered export section that contributed files (`register_export_section`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[SectionName, classified("internal")]
    section_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$"), classified("internal")]
    file_count: Annotated[int, Field(ge=0), classified("internal")]


class EngagementExportManifest(BaseModel):
    """`manifest.json`, format `accrued.binder-export` version 1.0 (SPEC-344 §5)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        title="EngagementExportManifest",
        json_schema_extra={"$id": SCHEMA_ID},
    )

    format: Annotated[Literal["accrued.binder-export"], classified("public")]
    format_version: Annotated[Literal["1.0"], classified("public")]
    export_id: Annotated[UUID, classified("internal")]
    kind: Annotated[ExportKind, classified("internal")]
    generated_at: Annotated[datetime, classified("internal")]
    # The audit sequence the selection was read at: one consistent snapshot (A-01 §4.5).
    as_of_seq: Annotated[int, Field(ge=0), classified("internal")]
    tenant_id: Annotated[UUID, classified("internal")]
    firm_name: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    client: Annotated[ManifestClient, classified("confidential")]
    engagement: Annotated[ManifestEngagement, classified("confidential")]
    requested_by: Annotated[ManifestPerson, classified("confidential")]
    requested_at: Annotated[datetime, classified("internal")]
    scope: Annotated[ManifestScope, classified("internal")]
    counts: Annotated[ManifestCounts, classified("internal")]
    index_columns: Annotated[list[str], classified("public")]
    sections: Annotated[list[ManifestSection], classified("internal")] = []
    files: Annotated[list[ManifestFile], classified("confidential")]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if tuple(self.index_columns) != INDEX_COLUMNS:
            raise ValueError("index_columns are format 1.0's")
        paths = [f.path for f in self.files]
        if paths != sorted(paths) or len(set(paths)) != len(paths):
            raise ValueError("files are sorted by path and unique")
        if UNLISTED & set(paths):
            raise ValueError("the manifest and the checksum files never list themselves")
        evidence = [f for f in self.files if f.role == "evidence"]
        if len(evidence) != self.counts.file_count:
            raise ValueError("counts.file_count is the number of evidence files")
        if not self.scope.include_unaccepted and any(
            f.evidence is not None and f.evidence.review_state == "needs_review" for f in evidence
        ):
            raise ValueError("files awaiting review need include_unaccepted")
        if not self.scope.include_audit_trail and AUDIT_TRAIL in paths:
            raise ValueError("the audit trail needs include_audit_trail")
        names = [s.name for s in self.sections]
        if names != sorted(set(names)):
            raise ValueError("sections are sorted by name and unique")
        for section in self.sections:
            count = sum(1 for f in self.files if f.section == section.name)
            if count != section.file_count:
                raise ValueError(f"section {section.name}: file_count disagrees with files")
        if {f.section for f in self.files if f.section is not None} - set(names):
            raise ValueError("every section file belongs to a listed section")
        return self


def manifest_json_schema() -> dict[str, object]:
    """The generated JSON schema of manifest v1 (draft 2020-12)."""
    schema = EngagementExportManifest.model_json_schema(mode="validation")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
