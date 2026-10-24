# ac-test-author: ayushkbhatia
"""Q-03-T014 and Q-03-T015: back-fills of TASK-035 (SPEC-020 AC-1, AC-8, AC-9: portal item
visibility and client uploads), TASK-056 (SPEC-029 AC-12: previews), TASK-054 and TASK-055
(SPEC-029 AC-1 to AC-5, AC-6 and AC-8: scanning, isolated extraction, document kinds and
mechanical checks).

A client principal reads only the items its grants reach (client admin: client-visible items of
its engagement; contributor: its assigned ones), and nothing of another engagement or firm; its
upload lands as `uploaded` ("Uploaded - needs review"), never `received`: DEC-09 migrated the
codes, so SPEC-020 AC-8's "the item shows received" is spec drift and the test follows the enum
(P-44, C5). A scan failure fails closed and stores nothing, so no unscanned version is ever
served. The size limit is SPEC-020 AC-9's 25 MB; DEC-58's 50 MB is held as ED-018.

Boundary: `create_app()` over HTTP as the firm's people and the client's (fake-identity tokens,
client memberships with engagement-scope grants), the compose S3 image with Object Lock, and the
`upload_processing` activities (`evidence.api.process_upload`, `check_upload_content`, and the
preview stage) run on the stored version. Expectations: SPEC-020 §5, SPEC-029 §5 and §7, DEC-09,
DEC-58, `error-codes.yaml`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast

import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.scanning import InjectedVerdict, forget_injected, inject_verdict
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, check_upload_content
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus_tools.synthetic.documents import aging_schedule_xlsx, bank_statement_pdf, scanned_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "backfill-client-uploads"
MASTER: Final = b"backfill-client-uploads-master-key-012345"
PDF: Final = "application/pdf"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    forget_injected()
    yield
    forget_injected()
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    manager: Person
    site: Site
    other: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    def base(self, site: Site | None = None) -> str:
        return f"/v1/engagements/{(site or self.site).engagement_id}"

    async def item(
        self, description: str, *, visible: bool = True, assignee: Person | None = None
    ) -> uuid.UUID:
        made = await self.seed.item(self.site, description, assignee=assignee)
        await self.seed.run(
            "UPDATE request_items SET client_visible = $2 WHERE id = $1", made, visible
        )
        return made

    async def requested(self, description: str) -> uuid.UUID:
        """A request created through the firm's route, so the description rules run (AC-5)."""
        response = await self.net.call(
            "POST",
            f"{self.base()}/request-items",
            self.manager,
            body={"description": description, "audit_area": "Cash"},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])

    async def upload(
        self, who: Person, item: uuid.UUID, content: bytes, media_type: str = PDF
    ) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base()}/request-items/{item}/uploads",
            params={"filename": "statement.pdf"},
            content=content,
            headers={**self.net.headers(who), "Content-Type": media_type},
        )

    async def versions(self) -> int:
        return int(
            cast(
                int,
                await self.seed.value(
                    "SELECT count(*) FROM evidence_versions WHERE engagement_id = $1",
                    self.site.engagement_id,
                ),
            )
        )

    async def status(self, item: uuid.UUID) -> str:
        return str(await self.seed.value("SELECT status FROM request_items WHERE id = $1", item))

    async def processed(self, version: uuid.UUID) -> tuple[str, str]:
        given = UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version))
        status = await extract_upload(given)
        await check_upload_content(given)
        preview = await preview_upload(given)
        return status, preview


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'uploads.processing', 'true', 'test-seed', 'Q-03-T014')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Feld")
    other = await seed.site(tenant_id, admin.user_id, "Granite")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    return Firm(net, tenant_id, manager, site, other)


def _ids(response: httpx.Response) -> set[str]:
    assert response.status_code == 200, response.text
    return {str(i["id"]) for i in cast(list[dict[str, object]], response.json())}


# --- Q-03-T014: SPEC-020 AC-1, item visibility ---------------------------------------------------


async def test_ac1_a_client_admin_reads_only_its_engagements_client_visible_items(
    firm: Firm,
) -> None:
    shown = await firm.item("December bank statement")
    hidden = await firm.item("Internal tickmark note", visible=False)
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    listed = _ids(await firm.net.call("GET", f"{firm.base()}/request-items", admin))
    assert str(shown) in listed
    assert str(hidden) not in listed
    other = await firm.net.call("GET", f"{firm.base(firm.other)}/request-items", admin)
    assert other.status_code == 404  # another engagement of the same firm: as if it didn't exist
    assert str(firm.other.item_id) not in other.text


async def test_ac1_a_contributor_reads_only_its_assigned_items(firm: Firm) -> None:
    contributor = await firm.seed.client_contact(firm.site, "client_contributor")
    mine = await firm.item("Payroll register", assignee=contributor)
    theirs = await firm.item("Loan agreement")
    listed = _ids(await firm.net.call("GET", f"{firm.base()}/request-items", contributor))
    assert str(mine) in listed
    assert str(theirs) not in listed


async def test_ac1_nothing_of_another_firm_reaches_a_client(firm: Firm, net: Net) -> None:
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    stranger_firm = await firm.seed.firm()
    stranger_admin = await firm.seed.person(stranger_firm, "firm_admin")
    stranger = await firm.seed.site(stranger_firm, stranger_admin.user_id, "Stranger")
    response = await net.call(
        "GET", f"/v1/engagements/{stranger.engagement_id}/request-items", admin
    )
    assert response.status_code == 404
    assert stranger.marker not in response.text


# --- Q-03-T014: SPEC-020 AC-8 and AC-9, client uploads -------------------------------------------


async def test_ac8_a_client_upload_lands_as_uploaded_never_received(firm: Firm) -> None:
    item = await firm.item("December bank statement")
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    before = await firm.versions()
    response = await firm.upload(admin, item, bank_statement_pdf())
    assert response.status_code == 201, response.text
    upload = cast(dict[str, object], response.json())
    assert upload["uploaded_by"] == str(admin.user_id)
    assert upload["media_type"] == PDF
    assert await firm.versions() == before + 1
    assert await firm.status(item) == "uploaded"  # DEC-09: "Uploaded - needs review"
    method = await firm.seed.value(
        "SELECT method FROM evidence_versions WHERE id = $1",
        uuid.UUID(str(upload["evidence_version_id"])),
    )
    assert method == "uploaded"  # upload provenance
    audited = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND actor_id = $2 "
        "AND action = 'evidence.uploaded'",
        firm.tenant_id,
        str(admin.user_id),
    )
    assert cast(int, audited) >= 1


async def test_ac8_a_contributor_cannot_upload_to_an_unassigned_item(firm: Firm) -> None:
    contributor = await firm.seed.client_contact(firm.site, "client_contributor")
    unassigned = await firm.item("Loan agreement")
    before = await firm.versions()
    response = await firm.upload(contributor, unassigned, bank_statement_pdf())
    assert response.status_code in (403, 404), response.text
    assert await firm.versions() == before
    assigned = await firm.item("Payroll register", assignee=contributor)
    allowed = await firm.upload(contributor, assigned, bank_statement_pdf(last4="5678"))
    assert allowed.status_code == 201, allowed.text  # the control


async def test_ac9_too_large_wrong_type_by_content_and_duplicate_are_refused(firm: Firm) -> None:
    item = await firm.item("December bank statement")
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    before = await firm.versions()
    too_large = await firm.upload(admin, item, b"%PDF-1.4\n" + bytes(25 * 1024 * 1024 + 1))
    assert too_large.status_code in (413, 422), too_large.text
    zipped = await firm.upload(admin, item, b"PK\x03\x04" + bytes(64), PDF)  # named a PDF
    assert zipped.status_code == 422 and zipped.json()["detail"] == "upload_type_not_allowed"
    assert await firm.versions() == before
    content = bank_statement_pdf()
    assert (await firm.upload(admin, item, content)).status_code == 201
    again = await firm.upload(admin, item, content)
    assert again.status_code == 409 and again.json()["detail"] == "duplicate_upload"
    assert await firm.versions() == before + 1


# --- Q-03-T014: SPEC-029 AC-12, previews ---------------------------------------------------------


async def test_ac12_the_client_and_the_firm_see_server_made_pages_never_the_raw_file(
    firm: Firm,
) -> None:
    item = await firm.item("December bank statement")
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    response = await firm.upload(admin, item, bank_statement_pdf())
    version = uuid.UUID(response.json()["evidence_version_id"])
    assert await firm.processed(version) == ("extracted", "pages")
    path = f"{firm.base()}/request-items/{item}/uploads/{version}/preview"
    for who in (admin, firm.manager):
        listing = await firm.net.call("GET", path, who)
        assert listing.status_code == 200, listing.text
        assert listing.json()["kind"] == "pages" and listing.json()["page_count"] >= 1
        page = await firm.net.http.get(f"{path}/pages/1", headers=firm.net.headers(who))
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("image/png")
        assert page.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"%PDF" not in page.content
    outsider = await firm.seed.client_contact(firm.other, "client_admin")
    refused = await firm.net.call("GET", path, outsider)
    assert refused.status_code == 404


# --- Q-03-T015: SPEC-029 AC-1, a scan failure fails closed ---------------------------------------


VERDICTS: Final[tuple[InjectedVerdict, ...]] = ("error", "timeout", "infected")


@pytest.mark.parametrize("verdict", VERDICTS)
async def test_ac1_a_scan_that_fails_stores_nothing_for_an_item_or_the_inbox(
    firm: Firm, verdict: InjectedVerdict
) -> None:
    import hashlib

    content = bank_statement_pdf(last4="4321")
    inject_verdict(hashlib.sha256(content).hexdigest(), verdict)
    item = await firm.item("December bank statement")
    admin = await firm.seed.client_contact(firm.site, "client_admin")
    before = await firm.versions()
    refused = await firm.upload(admin, item, content)
    assert refused.status_code == 422 and refused.json()["detail"] == "file_refused"
    inbox = await firm.net.http.post(
        f"{firm.base()}/inbox",
        params={"filename": "statement.pdf"},
        content=content,
        headers={**firm.net.headers(firm.manager), "Content-Type": PDF},
    )
    assert inbox.status_code == 422 and inbox.json()["detail"] == "file_refused"
    assert await firm.versions() == before
    waiting = await firm.seed.value(
        "SELECT count(*) FROM inbox_files WHERE engagement_id = $1", firm.site.engagement_id
    )
    assert waiting == 0
    assert await firm.status(item) == "requested"  # nothing to serve, to anyone


# --- Q-03-T015: SPEC-029 AC-3, AC-4, AC-5, AC-6, AC-8 --------------------------------------------


async def test_ac3_a_scanned_pdf_waits_for_ocr_and_the_client_is_not_asked_again(
    firm: Firm,
) -> None:
    """Spec drift: SPEC-029 AC-3 called a scanned PDF `unreadable` with guidance to upload the
    digital statement; SPEC-312 (statement intake, later) keeps it as `not_extracted` /
    `needs_ocr`, does not ask the client to re-upload, and the firm sees no readable text yet.
    An encrypted PDF stays `unreadable` (tests/security/test_upload_hostile_files.py)."""
    item = await firm.requested("December bank statement")
    response = await firm.upload(firm.manager, item, scanned_pdf())
    assert response.status_code == 201, response.text
    version = uuid.UUID(response.json()["evidence_version_id"])
    status, _preview = await firm.processed(version)
    assert status == "not_extracted"
    reason = await firm.seed.value(
        "SELECT reason FROM upload_extractions WHERE evidence_version_id = $1", version
    )
    assert reason == "needs_ocr"
    checks = await _checks(firm, item, version)
    assert all(c["outcome"] != "problem" for c in checks.values() if c["audience"] == "client")


async def test_ac4_formulas_are_never_evaluated(firm: Firm) -> None:
    rows = [("Acme", [1, 2, 3, 4, 5]), ("Birch", [10, 0, 0, 0, 0])]
    decimal_rows = [(name, [Decimal(v) for v in values]) for name, values in rows]
    totals: dict[bool, object] = {}
    for formulas in (False, True):
        item = await firm.requested(f"Accounts receivable aging, {formulas}")
        sheet = aging_schedule_xlsx(decimal_rows, formulas=formulas)
        response = await firm.upload(firm.manager, item, sheet, XLSX)
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["evidence_version_id"])
        await firm.processed(version)
        totals[formulas] = await firm.seed.value(
            "SELECT grand_total FROM upload_extractions WHERE evidence_version_id = $1", version
        )
    assert totals[False] is not None  # the control: cached totals are read
    assert totals[True] is None  # a formula with no cached value is never computed


async def test_ac5_a_document_kind_is_set_by_rule_and_the_team_may_change_it(firm: Firm) -> None:
    item = await firm.requested("December bank statement for the operating account")
    listed = await firm.net.call("GET", f"{firm.base()}/request-items", firm.manager)
    row = next(i for i in listed.json() if i["id"] == str(item))
    assert (row["document_kind"], row["document_kind_source"]) == ("bank_statement", "rule")
    before = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
        firm.tenant_id,
        str(item),
    )
    changed = await firm.net.call(
        "PUT",
        f"{firm.base()}/request-items/{item}/document-kind",
        firm.manager,
        body={"document_kind": "schedule"},
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["document_kind"], changed.json()["document_kind_source"]) == (
        "schedule",
        "override",
    )
    after = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
        firm.tenant_id,
        str(item),
    )
    assert cast(int, after) == cast(int, before) + 1  # the change is audited
    client = await firm.seed.client_contact(firm.site, "client_admin")
    refused = await firm.net.call(
        "PUT",
        f"{firm.base()}/request-items/{item}/document-kind",
        client,
        body={"document_kind": "bank_statement"},
    )
    assert refused.status_code in (403, 404)


async def _checks(firm: Firm, item: uuid.UUID, version: uuid.UUID) -> dict[str, dict[str, object]]:
    response = await firm.net.call(
        "GET", f"{firm.base()}/request-items/{item}/uploads/{version}/checks", firm.manager
    )
    assert response.status_code == 200, response.text
    return {str(c["code"]): c for c in cast(list[dict[str, object]], response.json())}


async def test_ac6_a_statement_for_another_period_is_wrong_period_by_code(firm: Firm) -> None:
    """The engagement's year ends 2025-12-31; a December 2026 statement is the wrong period, and
    a December 2025 one is not (the control)."""
    found: dict[int, dict[str, object]] = {}
    for year in (2025, 2026):
        item = await firm.requested(f"December {year} bank statement")
        content = bank_statement_pdf(
            start=date(year, 12, 1), end=date(year, 12, 31), last4=f"{year}"[-4:]
        )
        response = await firm.upload(firm.manager, item, content)
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["evidence_version_id"])
        await firm.processed(version)
        found[year] = (await _checks(firm, item, version))["wrong_period"]
    assert found[2026]["outcome"] == "problem"
    assert found[2025]["outcome"] == "passed"


async def test_ac8_the_same_file_twice_in_an_engagement_names_the_first_item(firm: Firm) -> None:
    first = await firm.requested("December bank statement")
    second = await firm.requested("Year-end bank statement")
    content = bank_statement_pdf(last4="9999")
    one = await firm.upload(firm.manager, first, content)
    assert one.status_code == 201, one.text
    two = await firm.upload(firm.manager, second, content)
    assert two.status_code == 201, two.text  # another item: kept, and flagged
    version = uuid.UUID(two.json()["evidence_version_id"])
    await firm.processed(version)
    duplicate = (await _checks(firm, second, version))["duplicate"]
    assert duplicate["outcome"] == "problem"
    assert duplicate["ref_item_id"] == str(first)
