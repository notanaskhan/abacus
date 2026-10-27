# ac-test-author: claude (main session, S12 build batch; ADR-078 note in TASK-1501)
"""A-01-T25 (TASK-1501): independent properties of the engagement export package, offline, from
SPEC-344 and `docs/contracts/engagement-export-v1.md` (AC-4 safe names, AC-10 byte-identical
builds, the manifest schema published in `docs/contracts/schemas/`).

- Any client file names, however hostile, become archive paths with no problem and no repeat.
- The same inputs give the same bytes, whatever the order the files arrive in.
- Every file the manifest lists is in the archive with the digest the checksums name.
- The published JSON schema is the one the code generates.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from abacus.modules.evidence.export_builder import PackageFacts, PackageFile, build_package
from abacus.modules.evidence.export_manifest import (
    INDEX_COLUMNS,
    PROVENANCE_FILES,
    SCHEMA_FILE,
    EngagementExportManifest,
    ManifestClient,
    ManifestEngagement,
    ManifestEvidence,
    ManifestPerson,
    ManifestScope,
    archive_path_problem,
    manifest_json_schema,
)
from abacus.modules.evidence.export_sections import section_csv
from abacus.modules.evidence.export_selection import deduplicated, file_segment, segment

REPO = Path(__file__).resolve().parents[4]
BINDER = uuid.UUID(int=7)
GENERATED = datetime(2026, 9, 14, 14, 40, tzinfo=UTC)

# Client file names are hostile (ADR-052): control characters, traversal, separators, drive
# letters, formulas, non-NFC forms, very long names.
hostile_names = st.one_of(
    st.text(min_size=0, max_size=300),
    st.sampled_from(
        [
            "../../etc/passwd",
            "..",
            ".",
            "C:\\boot.ini",
            "/abs/path.pdf",
            '=HYPERLINK("http://x","y").pdf',
            "e\u0301te\u0301.pdf",  # not NFC
            "tab\there\nnew.pdf",
            "zero\u200bwidth.pdf",
            "a" * 400 + ".pdf",
            "Same.PDF",
            "same.pdf",
        ]
    ),
)


def _facts() -> PackageFacts:
    return PackageFacts(
        export_id=uuid.UUID(int=1),
        kind="binder",
        generated_at=GENERATED,
        as_of_seq=1,
        tenant_id=uuid.UUID(int=2),
        firm_name="Brightwater Hale LLP",
        client=ManifestClient(client_id=uuid.UUID(int=3), display_name="Northwind Labs, Inc."),
        engagement=ManifestEngagement(
            engagement_id=uuid.UUID(int=4),
            work_item_id=uuid.UUID(int=5),
            display_name="Northwind FY2026 audit",
            period_end=date(2026, 6, 30),
        ),
        requested_by=ManifestPerson(user_id=uuid.UUID(int=6), display_name="Hannah Leclerc"),
        requested_at=GENERATED,
        scope=ManifestScope(
            binder_ids=[BINDER], include_unaccepted=True, include_audit_trail=False
        ),
        request_count=1,
        requests_without_file=0,
    )


def _paths(names: list[str]) -> list[str]:
    folder = f"evidence/01 {segment('Cash', 40)}/01 {segment('Statements', 40)}"
    return deduplicated([f"{folder}/{file_segment(n, i + 1)}" for i, n in enumerate(names)])


def _files(names: list[str], contents: list[bytes]) -> list[PackageFile]:
    index = section_csv(INDEX_COLUMNS, [])
    evidence = [
        PackageFile(
            path,
            content,
            "evidence",
            evidence=ManifestEvidence(
                evidence_version_id=uuid.uuid5(BINDER, path),
                request_item_id=uuid.UUID(int=9),
                binder_id=BINDER,
                version_no=1,
                review_state="accepted",
                media_type="application/pdf",
            ),
        )
        for path, content in zip(_paths(names), contents, strict=True)
    ]
    return [
        PackageFile("index.csv", index, "index"),
        *(PackageFile(p, b"h\r\n", "provenance") for p in PROVENANCE_FILES),
        *evidence,
    ]


def _build(files: list[PackageFile]) -> tuple[bytes, str, str]:
    out = io.BytesIO()
    built = build_package(_facts(), files, out)
    return out.getvalue(), built.bundle_sha256, built.manifest_sha256


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(hostile_names, min_size=1, max_size=8))
def test_ac4_any_client_names_become_safe_unique_archive_paths(names: list[str]) -> None:
    paths = _paths(names)
    assert len(paths) == len(names)
    assert len({p.casefold() for p in paths}) == len(paths)
    for path in paths:
        assert archive_path_problem(path) is None, path


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.tuples(hostile_names, st.binary(min_size=0, max_size=256)), min_size=1, max_size=6
    ),
    st.randoms(use_true_random=False),
)
def test_ac10_the_same_inputs_give_the_same_bytes_in_any_order(
    pairs: list[tuple[str, bytes]], order: object
) -> None:
    names = [n for n, _ in pairs]
    contents = [c for _, c in pairs]
    files = _files(names, contents)
    shuffled = list(files)
    order.shuffle(shuffled)  # type: ignore[attr-defined]  # hypothesis Random
    first = _build(files)
    second = _build(shuffled)
    assert first == second
    archive, bundle_sha, manifest_sha = first
    assert hashlib.sha256(archive).hexdigest() == bundle_sha
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        names_in = set(opened.namelist())
        manifest_bytes = opened.read("manifest.json")
        assert hashlib.sha256(manifest_bytes).hexdigest() == manifest_sha
        manifest = EngagementExportManifest.model_validate_json(manifest_bytes)
        for f in manifest.files:
            assert f.path in names_in
            assert hashlib.sha256(opened.read(f.path)).hexdigest() == f.sha256
        for line in opened.read("checksums.sha256").decode().splitlines():
            digest, path = line.split("  ", 1)
            assert hashlib.sha256(opened.read(path)).hexdigest() == digest
    for name in names_in:
        assert archive_path_problem(name) is None, name


def test_the_published_manifest_schema_is_the_generated_one() -> None:
    published = json.loads((REPO / "docs" / "contracts" / "schemas" / SCHEMA_FILE).read_text())
    assert published == manifest_json_schema()
