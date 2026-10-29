# ac-test-author: ayushkbhatia
"""N-01's S15 group B (TASK-2018 to TASK-2021; DEC-1058 to DEC-1061), written at the end review
(build-only pass): AttachmentTriage, the Inbox read APIs, portal intake and triage apply.

Acceptances (the task rows):
- N-01-T12: "A 1095-C intake object gets masked page previews" (the replay half is
  `tests/workflows/test_attachment_triage_replay.py`).
- N-01-T13: "Counts exclude walled clients without disclosing them and every content read writes
  an audit event."
- N-01-T14: "Claire Feld's upload reaches the firm Inbox and a withdrawn upload is hidden at once
  and unreadable after 30 days unless held."
- N-01-T18: "Superseding never deletes, an agent or system context is refused at all layers, Feld
  Intake goes from 2 to 1."

Boundary: `create_app()` over HTTP as each signed-in person; the upload steps and the purge as the
worker calls them; outcomes through SQL and the evidence bucket.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, cast

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.communications import triage_apply
from abacus.modules.communications.api import (
    Inbound,
    IntakePurgeInput,
    TriageInput,
    add_attachment,
    portal_intake,
    record_inbound_message,
)
from abacus.modules.communications.triage import attachment_triaged
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    INTAKE,
    UploadInput,
    masked_preview_upload,
    pii_scan_upload,
    words_upload,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.identity.api import AuthContext, Forbidden, member_context
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
EVIDENCE: Final = "n01b-evidence"
MASTER: Final = b"n01b-independent-master-key-0123456789ab"
F1095C: Final = positioned_pdf(
    [
        [
            (50, 740, "Form 1095-C Employer-Provided Health Insurance Offer and Coverage"),
            (50, 720, "Employee: Claire Feld"),
            (50, 700, "Employer: Mercer Hill Health"),
            (50, 680, "Tax year 2025"),
        ],
        [(50, 740, "Part III Covered Individuals"), (50, 720, "Claire Feld")],
    ]
)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    yield
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    grace: Person  # on the Intake team, a firm admin
    lena: Person  # a firm admin walled from Ashford
    feld: Site
    ashford: Site

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "test.n01b")

    async def call(
        self, method: str, path: str, who: Person, body: Body | None = None
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body)


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("inbox.firm_intake", "portal.intake_upload", "uploads.processing"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'N-01 group B')",
            tenant,
            flag,
        )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    lena = await seed.person(tenant, "firm_admin")
    feld = await seed.site(tenant, admin.user_id, "Feld")
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    team = await seed.value(
        "INSERT INTO teams (tenant_id, name, kind) VALUES ($1, 'Intake', 'intake') RETURNING id",
        tenant,
    )
    await seed.run(
        "INSERT INTO team_rosters (tenant_id, team_id, user_id) VALUES ($1, $2, $3)",
        tenant,
        team,
        grace.user_id,
    )
    await net.wall(admin, lena, ashford)
    return Firm(net, tenant, admin, grace, lena, feld, ashford)


async def _email(
    firm: Firm, site: Site | None, subject: str, files: int = 1
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """An email batch matched to `site`'s client (or unmatched), with `files` 1095-C copies."""
    made = await record_inbound_message(
        firm.system,
        Inbound(
            channel="email",
            sender_display="Claire Feld",
            subject=subject,
            received_at=datetime.now(UTC),
            body="Here are our health forms.",
            sender_address=f"claire+{uuid.uuid4().hex[:6]}@example.com",
            client_id=site.client_id if site is not None else None,
        ),
    )
    ids: list[uuid.UUID] = []
    for n in range(files):
        got = await add_attachment(
            firm.system,
            made.message_id,
            file_name=f"Feld_1095C_2025_{n}.pdf",
            content=F1095C + f"% copy {n}\n".encode(),
        )
        ids.append(got.attachment_id)
    return made.message_id, ids


# --- N-01-T12: AttachmentTriage ------------------------------------------------------------------


async def test_t12_a_1095c_intake_object_gets_masked_page_previews(firm: Firm) -> None:
    message, (attachment,) = await _email(firm, None, "Re: 2025 tax documents")
    given = UploadInput(str(firm.tenant_id), INTAKE, str(attachment))
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    kind = await masked_preview_upload(given)
    assert kind in ("pages", "image")
    seed = firm.net.seed
    preview = await seed.rows(
        "SELECT page_count, engagement_id, mask_version FROM upload_previews "
        "WHERE inbox_attachment_id = $1",
        attachment,
    )
    assert len(preview) == 1
    assert preview[0]["page_count"] == 2 and preview[0]["engagement_id"] is None
    assert preview[0]["mask_version"] is not None
    # Unmatched stays New; matched moves to Waiting after the steps.
    assert await attachment_triaged(TriageInput(str(firm.tenant_id), str(attachment))) == "new"
    del message


async def test_t12_a_withdrawn_attachment_derives_nothing(firm: Firm) -> None:
    _message, (attachment,) = await _email(firm, firm.feld, "Withdrawn later")
    await firm.net.seed.run(
        "UPDATE inbox_attachments SET status = 'withdrawn', withdrawn_at = now() WHERE id = $1",
        attachment,
    )
    with pytest.raises(Exception):  # noqa: B017 -- NotFound from the step, whatever its wrapper
        await extract_upload(UploadInput(str(firm.tenant_id), INTAKE, str(attachment)))


# --- N-01-T13: the read APIs ---------------------------------------------------------------------


async def test_t13_counts_exclude_walled_clients_and_content_reads_are_audited(firm: Firm) -> None:
    await _email(firm, firm.feld, "Feld documents", files=2)
    walled_message, _ = await _email(firm, firm.ashford, "Ashford documents", files=3)

    lena = await firm.call("GET", "/v1/inbox/summary", firm.lena)
    grace = await firm.call("GET", "/v1/inbox/summary", firm.grace)
    assert lena.status_code == grace.status_code == 200, lena.text
    assert lena.json()["waiting"] == 2
    assert grace.json()["waiting"] == 5
    threads = await firm.call("GET", "/v1/inbox/threads", firm.lena)
    assert threads.json()["total"] == 1
    assert "Ashford" not in threads.text

    walled_thread = await firm.net.seed.value(
        "SELECT thread_id FROM inbound_messages WHERE id = $1", walled_message
    )
    assert (
        await firm.call("GET", f"/v1/inbox/threads/{walled_thread}", firm.lena)
    ).status_code == 404

    feld_thread = (await firm.call("GET", "/v1/inbox/threads", firm.grace)).json()["items"]
    feld = next(t for t in feld_thread if t["subject_display"] == "Feld documents")
    detail = await firm.call("GET", f"/v1/inbox/threads/{feld['id']}", firm.grace)
    assert detail.status_code == 200, detail.text
    message = detail.json()["messages"][0]
    assert message["body"] == "Here are our health forms."
    attachment = message["attachments"][0]["id"]
    content = await firm.call("GET", f"/v1/inbox/attachments/{attachment}/content", firm.grace)
    assert content.status_code == 200 and content.headers["cache-control"] == "no-store"
    viewer = await firm.call("GET", f"/v1/inbox/attachments/{attachment}/viewer", firm.grace)
    assert viewer.status_code == 200, viewer.text
    zipped = await firm.call(
        "GET", f"/v1/inbox/messages/{message['id']}/attachments.zip", firm.grace
    )
    assert zipped.status_code == 200
    actions = await firm.net.seed.actions(firm.tenant_id)
    for audited in (
        "inbound_message.body_read",
        "inbox_attachment.downloaded",
        "inbox_attachment.viewed",
        "inbound_message.downloaded",
    ):
        assert audited in actions, audited


# --- N-01-T14: portal intake ---------------------------------------------------------------------


async def test_t14_claires_upload_reaches_the_inbox_and_a_withdrawal_hides_then_erases(
    firm: Firm, raw: S3Client
) -> None:
    claire = await firm.net.seed.client_contact(firm.feld, "client_admin")
    batch = await firm.net.http.post(
        "/v1/portal/intake-uploads",
        json={
            "scope_ref": {"kind": "engagement", "id": str(firm.feld.engagement_id)},
            "note": None,
        },
        headers={**firm.net.headers(claire), "Idempotency-Key": "n01b-batch"},
    )
    assert batch.status_code == 201, batch.text
    upload = batch.json()["id"]
    sent = await firm.net.http.post(
        f"/v1/portal/intake-uploads/{upload}/files",
        params={"filename": "Feld_1095C_2025.pdf"},
        content=F1095C,
        headers={
            **firm.net.headers(claire),
            "Idempotency-Key": "n01b-file",
            "Content-Type": "application/octet-stream",
        },
    )
    assert sent.status_code == 201, sent.text
    attachment = uuid.UUID(sent.json()["id"])
    seed = firm.net.seed
    assert (
        await seed.value("SELECT key_mode FROM inbox_attachments WHERE id = $1", attachment)
        == "detached"
    )
    summary = await firm.call("GET", "/v1/inbox/summary", firm.grace)
    assert summary.json()["waiting"] == 1  # it reached the firm Inbox

    withdrawn = await firm.net.http.post(
        f"/v1/portal/intake-uploads/{upload}/withdraw",
        headers={**firm.net.headers(claire), "Idempotency-Key": "n01b-withdraw"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "withdrawn"
    after = await firm.call("GET", "/v1/inbox/summary", firm.grace)
    assert after.json()["waiting"] == 0  # hidden at once
    assert (
        await firm.call("GET", f"/v1/inbox/attachments/{attachment}/content", firm.grace)
    ).status_code == 404

    # Thirty days on, unless held: the key goes and the object can no longer be read.
    await seed.run_untriggered(
        "UPDATE inbox_attachments SET withdrawn_at = now() - interval '31 days' WHERE id = $1",
        attachment,
    )
    wait = await portal_intake.erase_withdrawn_intake(
        IntakePurgeInput(str(firm.tenant_id), upload)
    )
    assert wait == 0
    destroyed = await seed.value(
        "SELECT destroyed_at IS NOT NULL FROM evidence_intake_object_keys "
        "WHERE inbox_attachment_id = $1",
        attachment,
    )
    assert destroyed is True


async def test_t14_a_filed_upload_cannot_be_withdrawn(firm: Firm) -> None:
    claire = await firm.net.seed.client_contact(firm.feld, "client_admin")
    made = await portal_intake.create_upload(
        await _client_ctx(firm, claire), "engagement", firm.feld.engagement_id, None
    )
    await firm.net.seed.run_untriggered(
        "INSERT INTO inbox_attachments (tenant_id, message_id, thread_id, client_id, file_name, "
        "media_type, size_bytes, fingerprint, storage_key, key_mode, status, "
        "filed_evidence_version_id) SELECT m.tenant_id, m.id, m.thread_id, $2, 'filed.pdf', "
        "'application/pdf', 1, repeat('a', 64), 'k', 'content', 'filed', $3 "
        "FROM inbound_messages m WHERE m.id = $1",
        made.id,
        firm.feld.client_id,
        firm.feld.version_id,
    )
    refused = await firm.net.http.post(
        f"/v1/portal/intake-uploads/{made.id}/withdraw",
        headers={**firm.net.headers(claire), "Idempotency-Key": "n01b-withdraw-filed"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "attachment_filed"


async def _client_ctx(firm: Firm, who: Person) -> AuthContext:
    ctx = await member_context(firm.tenant_id, who.user_id)
    assert ctx is not None
    return ctx


# --- N-01-T18: triage apply ----------------------------------------------------------------------


async def test_t18_filing_fulfils_the_request_and_superseding_never_deletes(firm: Firm) -> None:
    seed = firm.net.seed
    first = await seed.item(firm.feld, "Form 1095-C From Mercer Hill Health")
    second = await seed.item(firm.feld, "Form 1098 From Hudson Mutual")
    open_before = int(
        str(
            await seed.value(
                "SELECT count(*) FROM request_items WHERE id = ANY($1) AND status = 'requested'",
                [first, second],
            )
        )
    )
    assert open_before == 2
    message, (a1, a2) = await _email(firm, firm.feld, "Feld intake", files=2)

    applied = await firm.net.http.post(
        f"/v1/inbox/messages/{message}/triage/apply",
        json={
            "decisions": [
                {
                    "attachment_id": str(a1),
                    "decision": "file",
                    "destination": {"kind": "request", "id": str(first)},
                },
                {
                    "attachment_id": str(a2),
                    "decision": "ignore",
                    "reason_codes": ["duplicate"],
                },
            ]
        },
        headers={**firm.net.headers(firm.grace), "Idempotency-Key": "n01b-apply"},
    )
    assert applied.status_code == 200, applied.text
    assert (applied.json()["filed"], applied.json()["ignored"]) == (1, 1)
    open_after = int(
        str(
            await seed.value(
                "SELECT count(*) FROM request_items WHERE id = ANY($1) AND status = 'requested'",
                [first, second],
            )
        )
    )
    assert open_after == 1  # Feld Intake 2 -> 1

    filed = cast(
        uuid.UUID,
        await seed.value(
            "SELECT filed_evidence_version_id FROM inbox_attachments WHERE id = $1", a1
        ),
    )
    versions_before = int(
        str(
            await seed.value(
                "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant_id
            )
        )
    )
    message2, (a3,) = await _email(firm, firm.feld, "Corrected 1095-C")
    superseded = await firm.net.http.post(
        f"/v1/inbox/messages/{message2}/triage/apply",
        json={
            "decisions": [
                {
                    "attachment_id": str(a3),
                    "decision": "file",
                    "destination": {"kind": "permanent_file", "id": str(firm.feld.client_id)},
                    "version_mode": "new_version_supersede",
                    "supersede_version_id": str(filed),
                }
            ]
        },
        headers={**firm.net.headers(firm.grace), "Idempotency-Key": "n01b-supersede"},
    )
    assert superseded.status_code == 200, superseded.text
    versions_after = int(
        str(
            await seed.value(
                "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant_id
            )
        )
    )
    assert versions_after == versions_before + 1  # added, nothing removed
    still = await seed.value("SELECT count(*) FROM evidence_versions WHERE id = $1", filed)
    assert still == 1
    link = await seed.value(
        "SELECT supersedes_version_id FROM evidence_versions WHERE supersedes_version_id = $1",
        filed,
    )
    assert link == filed


async def test_t18_an_agent_or_system_context_is_refused(firm: Firm) -> None:
    message, (attachment,) = await _email(firm, firm.feld, "Agent tries")
    decision = triage_apply.Decision(attachment, "ignore", reason_codes=("spam",))
    with pytest.raises((Forbidden, Exception)):
        await triage_apply.apply(
            cast(Any, TenantContext(firm.tenant_id, "system", "test")),  # Any: not a person
            message,
            [decision],
        )
    rows = await firm.net.seed.value(
        "SELECT count(*) FROM triage_decisions WHERE attachment_id = $1", attachment
    )
    assert rows == 0
    # The table refuses a non-human row even with the service bypassed.
    with pytest.raises(Exception):  # noqa: B017 -- the CHECK names the actor
        await firm.net.seed.run(
            "WITH s AS (SELECT set_config('app.actor_kind', 'agent', true), "
            "set_config('app.actor_id', 'agent:x', true)) "
            "INSERT INTO triage_decisions (tenant_id, attachment_id, thread_id, decision, "
            "reason_codes) SELECT $1, a.id, a.thread_id, 'ignore', ARRAY['spam'] "
            "FROM inbox_attachments a, s WHERE a.id = $2",
            firm.tenant_id,
            attachment,
        )
