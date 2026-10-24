# ac-test-author: ayushkbhatia
"""Q-03-T013 (D1, pen scope): hostile files through the real upload pipeline.

EICAR, zip bombs, polyglots, PDFs with JavaScript, password-protected PDFs (SHL-08 state D),
HEIC, files over 50 MB and types outside DEC-58 (c) are each refused with their catalogue code,
or stored and isolated: never extracted into content, never previewed (Q-03 §D1; SPEC-029 AC-1
to AC-3, AC-12; ADR-110 "a file that isn't scanned clean is never parsed or previewed"; ADR-052,
client content is hostile).

Boundary: `create_app()` over HTTP for the item upload and the inbox (`evidence.upload`), on the
migrated testcontainer Postgres and the compose S3 image with Object Lock; the stored version is
then taken through the upload-processing stages the `upload_processing` workflow runs (extract,
check, preview) as its activities, so what the worker would derive from the file is what the test
reads back. Refusals answer the catalogue's 422 codes (`file_refused`, `upload_too_large`,
`upload_type_not_allowed`, `upload_empty`; `docs/architecture/error-codes.yaml`) and store
nothing. Later decisions followed: DEC-58 (c) sets the limit at 50 MB and the types at PDF, JPG,
PNG, HEIC, XLSX, DOCX and CSV (SPEC-029 §7 said 25 MB "as today"); POR-03 and POR-04 say HEIC
is stored as-is with no preview until P-11-T25 renders it.
"""

from __future__ import annotations

import io
import time
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
import yaml
from testcontainers.core.container import DockerContainer
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, check_upload_content
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus_tools.synthetic.documents import bank_statement_pdf, encrypted_pdf

from .support import Net, Person, Seeder, Site

REPO: Final = Path(__file__).resolve().parents[3]
BUCKET: Final = "abacus-hostile-files"
MASTER: Final = b"hostile-files-test-master-key-0123456789ab"
MB: Final = 1024 * 1024
S3_ACCESS: Final = "abacus"  # the compose S3 image's fixed local credentials
S3_ROOT_KEY: Final = "abacuslocal"
PDF: Final = "application/pdf"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# The standard anti-malware test file (eicar.org): every scanner detects it; harmless by design.
EICAR: Final = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
ALLOWED: Final = frozenset({PDF, "image/jpeg", "image/png", "image/heic", XLSX, DOCX, "text/csv"})


# --- object storage, as the integration suite runs it (ADR-077) ----------------------------------


def _image(service: str) -> str:
    loaded = cast(dict[str, object], yaml.safe_load((REPO / "docker-compose.yml").read_text()))
    return str(cast(dict[str, dict[str, object]], loaded["services"])[service]["image"])


@pytest.fixture(scope="module")
def bucket() -> Iterator[S3Client]:
    container = (
        DockerContainer(_image("s3"))
        .with_env("ROOT_ACCESS_KEY", S3_ACCESS)
        .with_env("ROOT_SECRET_KEY", S3_ROOT_KEY)
        .with_command("--health /health posix --versioning-dir /versions /data")
        .with_tmpfs_mount("/data")
        .with_tmpfs_mount("/versions")
        .with_exposed_ports(7070)
    )
    with container:
        endpoint = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(7070)}"
        deadline = time.monotonic() + 60

        def healthy() -> bool:
            return httpx.get(f"{endpoint}/health", timeout=2).status_code == 200

        while True:
            try:
                if healthy():
                    break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    raise
            time.sleep(0.5)
        client = s3_client(
            endpoint_url=endpoint,
            access_key=S3_ACCESS,
            secret_key=S3_ROOT_KEY,
            region="us-east-1",
        )
        client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
        yield client


@pytest.fixture(autouse=True)
def evidence_storage(bucket: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    manager: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def upload(self, name: str, content: bytes, media_type: str) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/request-items/{self.site.item_id}/uploads",
            params={"filename": name},
            content=content,
            headers={**self.net.headers(self.manager), "Content-Type": media_type},
        )

    async def inbox(self, name: str, content: bytes, media_type: str) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/inbox",
            params={"filename": name},
            content=content,
            headers={**self.net.headers(self.manager), "Content-Type": media_type},
        )

    async def stored(self) -> tuple[int, int]:
        """Evidence versions and inbox files the engagement holds (the seed's version is one)."""
        rows = await self.seed.rows(
            "SELECT (SELECT count(*) FROM evidence_versions WHERE engagement_id = $1) AS v, "
            "(SELECT count(*) FROM inbox_files WHERE engagement_id = $1) AS i",
            self.site.engagement_id,
        )
        return int(rows[0]["v"]), int(rows[0]["i"])

    async def audit_count(self) -> int:
        return int(
            cast(
                int,
                await self.seed.value(
                    "SELECT count(*) FROM audit_events WHERE tenant_id = $1", self.tenant_id
                ),
            )
        )

    async def processed(self, version_id: uuid.UUID) -> tuple[list[str], list[str]]:
        """Run the workflow's stages on the version; return its extraction and preview kinds."""
        given = UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version_id))
        await extract_upload(given)
        await check_upload_content(given)
        await preview_upload(given)
        rows = await self.seed.rows(
            "SELECT status FROM upload_extractions WHERE evidence_version_id = $1", version_id
        )
        previews = await self.seed.rows(
            "SELECT kind FROM upload_previews WHERE evidence_version_id = $1", version_id
        )
        return [str(r["status"]) for r in rows], [str(r["kind"]) for r in previews]


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for name in ("uploads.processing", "evidence.viewer_v1"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'Q-03-T013')",
            tenant_id,
            name,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "hostile")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    return Firm(net, tenant_id, manager, site)


# --- samples -------------------------------------------------------------------------------------


def _pdf(objects: list[bytes]) -> bytes:
    """A well-formed PDF from numbered object bodies (1 is the catalog), with a true xref."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def javascript_pdf() -> bytes:
    """One readable page, and JavaScript that runs on open and from the names tree."""
    stream = b"BT /F1 12 Tf 72 720 Td (Statement of account) Tj ET"
    return _pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R /OpenAction 5 0 R "
            b"/Names << /JavaScript << /Names [(boot) 5 0 R] >> >> >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 6 0 R >> >> /AA << /O 5 0 R >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /S /JavaScript /JS (app.launchURL\\('http://attacker.invalid/x'\\);) >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
    )


def _zip(entries: list[tuple[str, bytes]], *, method: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=method) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()


def _xlsx_shell(extra: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    return [
        ("[Content_Types].xml", b'<?xml version="1.0"?><Types/>'),
        ("xl/workbook.xml", b'<?xml version="1.0"?><workbook/>'),
        *extra,
    ]


def _docx_shell() -> list[tuple[str, bytes]]:
    return [
        ("[Content_Types].xml", b'<?xml version="1.0"?><Types/>'),
        ("word/document.xml", b'<?xml version="1.0"?><w:document/>'),
    ]


def ratio_bomb() -> bytes:
    """An XLSX whose one sheet inflates 8 MB of zeros from a few kilobytes (ratio above 100)."""
    return _zip(_xlsx_shell([("xl/worksheets/sheet1.xml", bytes(8 * MB))]))


def size_bomb() -> bytes:
    """An XLSX whose sheets expand to 240 MB in all (past any expanded-size limit)."""
    buffer = io.BytesIO()
    zero = bytes(MB)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in _xlsx_shell([]):
            archive.writestr(name, data)
        for sheet in range(3):
            with archive.open(f"xl/worksheets/sheet{sheet + 1}.xml", "w", force_zip64=True) as f:
                for _ in range(80):
                    f.write(zero)
    return buffer.getvalue()


def entries_bomb() -> bytes:
    """A DOCX of 20,000 tiny entries (a central directory bomb)."""
    parts = [(f"word/media/{n}.xml", b"x") for n in range(20_000)]
    return _zip([*_docx_shell(), *parts])


def nested_bomb() -> bytes:
    """A DOCX that stores an inflating archive inside it, uncompressed (42.zip's shape)."""
    inner = _zip([("payload.bin", bytes(8 * MB))])
    return _zip([*_docx_shell(), ("word/embeddings/x.zip", inner)])


def eicar_in_xlsx() -> bytes:
    return _zip(_xlsx_shell([("xl/media/readme.txt", EICAR)]), method=zipfile.ZIP_STORED)


def png_with_zip() -> bytes:
    """A PNG signature and header, then a whole ZIP holding EICAR (a GIFAR-style polyglot)."""
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    )
    return png + _zip([("x.txt", EICAR)], method=zipfile.ZIP_STORED)


def heic() -> bytes:
    """An ISO-BMFF `ftyp heic` box and no decodable image after it (a phone photo's header)."""
    return b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + bytes(2048)


# --- AC-1: what the scanner refuses is never stored ----------------------------------------------

REFUSED: Final = {
    "eicar": ("statement.pdf", EICAR, PDF),
    "eicar_in_an_xlsx": ("aging.xlsx", eicar_in_xlsx(), XLSX),
    "png_and_zip_polyglot": ("photo.png", png_with_zip(), "image/png"),
    "ratio_bomb": ("aging.xlsx", ratio_bomb(), XLSX),
    "entries_bomb": ("letter.docx", entries_bomb(), DOCX),
}


@pytest.mark.parametrize("sample", list(REFUSED))
async def test_ac1_the_scanner_refuses_the_item_upload_and_nothing_is_stored(
    firm: Firm, sample: str
) -> None:
    name, content, media_type = REFUSED[sample]
    before, audits = await firm.stored(), await firm.audit_count()
    response = await firm.upload(name, content, media_type)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "file_refused"
    assert await firm.stored() == before  # nothing stored, so nothing can be parsed
    assert await firm.audit_count() > audits  # the refusal is audited
    rows = await firm.seed.rows(
        "SELECT before_ref::text AS b, after_ref::text AS a FROM audit_events "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert not any("EICAR" in f"{r['b']}{r['a']}" for r in rows)  # no file content recorded


async def test_ac1_a_size_bomb_is_refused(firm: Firm) -> None:
    before = await firm.stored()
    response = await firm.upload("aging.xlsx", size_bomb(), XLSX)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "file_refused"
    assert await firm.stored() == before


@pytest.mark.parametrize("sample", ["eicar", "ratio_bomb"])
async def test_ac1_the_scanner_refuses_the_inbox_file_too(firm: Firm, sample: str) -> None:
    name, content, media_type = REFUSED[sample]
    before = await firm.stored()
    response = await firm.inbox(name, content, media_type)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "file_refused"
    assert await firm.stored() == before


async def test_ac1_a_nested_bomb_is_refused_or_never_parsed(firm: Firm) -> None:
    """An archive inside the archive: refused, or stored and never extracted or previewed."""
    response = await firm.upload("letter.docx", nested_bomb(), DOCX)
    if response.status_code == 422:
        assert response.json()["detail"] == "file_refused"
        return
    assert response.status_code == 201, response.text
    extractions, previews = await firm.processed(uuid.UUID(response.json()["evidence_version_id"]))
    assert "extracted" not in extractions
    assert set(previews) <= {"none"}


# --- DEC-58 (c): 50 MB and seven types -----------------------------------------------------------


def _too_large(response: httpx.Response) -> bool:
    """The route's 422 `upload_too_large`, or the edge's 413 when the body passes the request
    limit first (ADR-152, Q-01-T16): either way refused before anything is read into storage."""
    return (response.status_code, response.json()["detail"]) in (
        (422, "upload_too_large"),
        (413, "payload too large"),
    )


async def test_dec58_a_file_over_50_mb_is_refused_before_it_is_stored(firm: Firm) -> None:
    before = await firm.stored()
    big = b"%PDF-1.4\n" + bytes(50 * MB)
    response = await firm.upload("statement.pdf", big, PDF)
    assert _too_large(response), response.text
    response = await firm.inbox("statement.pdf", big, PDF)
    assert _too_large(response), response.text
    assert await firm.stored() == before


async def test_dec58_a_30_mb_pdf_is_within_the_limit(firm: Firm) -> None:
    content = bank_statement_pdf() + b"\n%" + bytes(30 * MB)
    response = await firm.upload("statement.pdf", content, PDF)
    assert response.status_code == 201, response.text


OUTSIDE: Final = {
    "html": ("statement.html", b"<html><script>alert(1)</script></html>", "text/html"),
    "svg": (
        "logo.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        "image/svg+xml",
    ),
    "exe": ("setup.exe", b"MZ\x90\x00" + bytes(256), "application/x-msdownload"),
    "javascript": ("run.js", b"alert(1)", "text/javascript"),
    "zip": ("bundle.zip", _zip([("a.txt", b"a")]), "application/zip"),
    "macro_workbook": (
        "aging.xlsm",
        _zip(_xlsx_shell([("xl/vbaProject.bin", b"\xd0\xcf\x11\xe0" + bytes(64))])),
        "application/vnd.ms-excel.sheet.macroEnabled.12",
    ),
    "legacy_word": (
        "letter.doc",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(512),
        "application/msword",
    ),
}


@pytest.mark.parametrize("sample", list(OUTSIDE))
async def test_dec58_a_type_outside_the_seven_is_refused(firm: Firm, sample: str) -> None:
    name, content, media_type = OUTSIDE[sample]
    before = await firm.stored()
    response = await firm.upload(name, content, media_type)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "upload_type_not_allowed"
    response = await firm.inbox(name, content, media_type)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "upload_type_not_allowed"
    assert await firm.stored() == before


async def test_dec58_an_empty_file_is_refused(firm: Firm) -> None:
    before = await firm.stored()
    response = await firm.upload("statement.pdf", b"", PDF)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "upload_empty"
    assert await firm.stored() == before


# --- polyglots: a declared type the bytes are not ------------------------------------------------

POLYGLOTS: Final = {
    "exe_named_pdf": ("statement.pdf", b"MZ\x90\x00\x03" + bytes(512), PDF),
    "html_named_pdf": ("statement.pdf", b"<!doctype html><script>alert(1)</script>", PDF),
    "html_named_png": ("photo.png", b"<html><body onload=alert(1)></body></html>", "image/png"),
    "pdf_with_html_tail": (
        "statement.pdf",
        bank_statement_pdf() + b"\n<html><script>alert(document.cookie)</script></html>",
        PDF,
    ),
}


@pytest.mark.parametrize("sample", list(POLYGLOTS))
async def test_polyglots_are_refused_or_stored_only_as_an_allowed_type_and_never_rendered_raw(
    firm: Firm, sample: str
) -> None:
    """ADR-110 and SPEC-029 AC-12: whatever a file claims to be, it is refused, or kept as one of
    DEC-58's types and shown only through server-made previews, never as markup."""
    name, content, media_type = POLYGLOTS[sample]
    response = await firm.upload(name, content, media_type)
    if response.status_code == 422:
        assert response.json()["detail"] in ("upload_type_not_allowed", "file_refused")
        return
    assert response.status_code == 201, response.text
    upload = cast(dict[str, object], response.json())
    assert upload["media_type"] in ALLOWED
    version = uuid.UUID(str(upload["evidence_version_id"]))
    extractions, previews = await firm.processed(version)
    if not content.startswith(b"%PDF"):  # not the file it claims: nothing derived from it
        assert "extracted" not in extractions
        assert set(previews) <= {"none"}
    listing = await firm.net.call(
        "GET",
        f"{firm.base}/request-items/{firm.site.item_id}/uploads/{version}/preview",
        firm.manager,
    )
    assert "<script" not in listing.text
    assert listing.headers.get("content-type", "").startswith("application/json") or (
        listing.status_code >= 400
    )


# --- quarantined, not refused: encrypted and active PDFs, HEIC ----------------------------------


async def test_ac3_a_password_protected_pdf_is_stored_locked_and_never_extracted_or_previewed(
    firm: Firm,
) -> None:
    """SPEC-029 AC-3 and SHL-08 state D: the version is kept (it can be unlocked), its result is
    `unreadable`, and no page is rendered from it."""
    response = await firm.upload("statement.pdf", encrypted_pdf(), PDF)
    assert response.status_code == 201, response.text
    version = uuid.UUID(response.json()["evidence_version_id"])
    extractions, previews = await firm.processed(version)
    assert extractions == ["unreadable"]
    assert "pages" not in previews


async def test_q03_a_pdf_with_javascript_is_quarantined_not_previewed(firm: Firm) -> None:
    """Q-03 §D1: a PDF carrying JavaScript (OpenAction, page open, names tree) is refused, or
    kept and never extracted into content or previewed."""
    response = await firm.upload("statement.pdf", javascript_pdf(), PDF)
    if response.status_code == 422:
        assert response.json()["detail"] == "file_refused"
        return
    assert response.status_code == 201, response.text
    version = uuid.UUID(response.json()["evidence_version_id"])
    extractions, previews = await firm.processed(version)
    assert "extracted" not in extractions
    assert "pages" not in previews


async def test_dec296_an_active_pdf_is_flagged_for_the_team_audited_and_refused_by_the_viewer(
    firm: Firm,
) -> None:
    """DEC-296: the active PDF is kept; the upload is audited as flagged, the team sees a firm
    `active_content` problem, and every viewer read answers 409 `active_content`."""
    response = await firm.upload("statement.pdf", javascript_pdf(), PDF)
    assert response.status_code == 201, response.text
    version = uuid.UUID(response.json()["evidence_version_id"])
    flagged = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "AND action = 'evidence_version.flagged'",
        firm.tenant_id,
        str(version),
    )
    assert flagged == 1
    await firm.processed(version)
    checks = await firm.net.call(
        "GET",
        f"{firm.base}/request-items/{firm.site.item_id}/uploads/{version}/checks",
        firm.manager,
    )
    assert checks.status_code == 200, checks.text
    found = {c["code"]: c for c in checks.json()}
    assert (found["active_content"]["outcome"], found["active_content"]["audience"]) == (
        "problem",
        "firm",
    )
    for path in ("viewer", "pages/1", "regions", "search?q=statement"):
        refused = await firm.net.call(
            "GET", f"/v1/evidence-versions/{version}/{path}", firm.manager
        )
        assert refused.status_code == 409, (path, refused.text)
        assert refused.json()["detail"] == "active_content"


async def test_dec58_heic_is_kept_as_is_with_no_preview_yet(firm: Firm) -> None:
    """DEC-58 (c) accepts HEIC; POR-03 and POR-04: stored as-is, "Preview not available yet"
    until P-11-T25 renders it. A hostile HEIC never fails the worker."""
    response = await firm.upload("IMG_0412.HEIC", heic(), "image/heic")
    assert response.status_code == 201, response.text
    assert response.json()["media_type"] == "image/heic"
    version = uuid.UUID(response.json()["evidence_version_id"])
    extractions, previews = await firm.processed(version)
    assert "extracted" not in extractions
    assert set(previews) <= {"none"}


async def test_ac2_a_malformed_pdf_ends_unreadable_never_as_a_worker_failure(firm: Firm) -> None:
    """SPEC-029 AC-2: a crash or a limit inside the isolated parser records `unreadable`."""
    broken = b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n" + bytes(4096)
    broken += b"trailer << /Root 1 0 R /Size 99999999 >>\nstartxref\n999999999\n%%EOF"
    response = await firm.upload("statement.pdf", broken, PDF)
    if response.status_code == 422:
        assert response.json()["detail"] in ("file_refused", "upload_type_not_allowed")
        return
    assert response.status_code == 201, response.text
    extractions, previews = await firm.processed(uuid.UUID(response.json()["evidence_version_id"]))
    assert extractions == ["unreadable"]
    assert "pages" not in previews


async def test_the_control_a_plain_statement_is_extracted_and_previewed(firm: Firm) -> None:
    """The control: the same pipeline extracts and previews an ordinary statement, so the
    refusals above are about the files, not a pipeline that derives nothing."""
    response = await firm.upload("statement.pdf", bank_statement_pdf(), PDF)
    assert response.status_code == 201, response.text
    extractions, previews = await firm.processed(uuid.UUID(response.json()["evidence_version_id"]))
    assert extractions == ["extracted"]
    assert previews == ["pages"]
