# ac-test-author: ayushkbhatia
"""P-06-T19 (SPEC-319 AC-15; ADR-162 §1 to §4, §7; DEC-298): the client withdraws an upload the
firm never accepted.

"An accepted version answers 409 evidence_accepted and a withdrawn version is unreadable after 30
days unless held." The withdrawal voids and hides the version at once: no firm read, viewer read
or agent material returns it, its request goes back to `requested`, and the audit trail says a
client withdrew an upload without naming the file. A contributor withdraws only its own uploads;
no firm role may withdraw. The purge erases nothing before the window, nothing while held and
nothing without a registered hold check (fail closed), and after it the version opens for no one.

Boundary: `create_app()` over HTTP as the client's people and the firm's, the migrated Postgres,
the compose S3 image with Object Lock, the processing activities, and the purge activity's body
(`erase_withdrawn`) on the business clock (`kernel.clock.frozen`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel import holds as kernel_holds
from abacus.kernel.clock import frozen
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_VERSION,
    UploadInput,
    check_upload_content,
    holds_covering,
    review_material,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.withdrawals import erase_withdrawn
from abacus_tools.synthetic.documents import bank_statement_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "p06t19-withdrawal"
MASTER: Final = b"p06t19-withdrawal-master-key-0123456789ab"
PDF: Final = "application/pdf"
DAY: Final = 24 * 3600


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
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def hold_check() -> Iterator[list[uuid.UUID]]:
    """The registered hold check, swappable: versions listed here read as held."""
    held: list[uuid.UUID] = []

    async def check(tenant: TenantContext, ids: object) -> frozenset[uuid.UUID]:
        found = await holds_covering(tenant, cast(list[uuid.UUID], ids))
        return found | frozenset(held)

    kernel_holds.reset_hold_check()
    kernel_holds.register_hold_check(check)
    yield held
    kernel_holds.reset_hold_check()
    kernel_holds.register_hold_check(holds_covering)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    manager: Person
    admin: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def upload(
        self, who: Person, content: bytes, item: uuid.UUID | None = None
    ) -> uuid.UUID:
        response = await self.net.http.post(
            f"{self.base}/request-items/{item or self.site.item_id}/uploads",
            params={"filename": "statement.pdf"},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["evidence_version_id"])

    async def withdraw(
        self, who: Person, version: uuid.UUID, key: str | None = None
    ) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/evidence-versions/{version}/withdraw",
            headers={**self.net.headers(who), "Idempotency-Key": key or str(uuid.uuid4())},
        )

    async def status(self, item: uuid.UUID | None = None) -> str:
        return str(
            await self.seed.value(
                "SELECT status FROM request_items WHERE id = $1", item or self.site.item_id
            )
        )

    async def stored(self, version: uuid.UUID) -> storage.StoredObject:
        row = (
            await self.seed.rows(
                "SELECT storage_key, storage_version_id, fingerprint, size_bytes "
                "FROM evidence_versions WHERE id = $1",
                version,
            )
        )[0]
        return storage.StoredObject(
            str(row["storage_key"]),
            str(row["storage_version_id"]),
            str(row["fingerprint"]),
            int(row["size_bytes"]),
        )

    async def withdrawal(self, version: uuid.UUID) -> asyncpg.Record:
        return (
            await self.seed.rows(
                "SELECT * FROM evidence_withdrawals WHERE evidence_version_id = $1", version
            )
        )[0]


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("uploads.processing", "evidence.withdrawal", "evidence.viewer_v1"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-06-T19')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Feld")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    admin = await seed.client_contact(site, "client_admin")
    return Firm(net, tenant_id, manager, admin, site)


# --- withdraw: void and hide at once -------------------------------------------------------------


async def test_ac15_a_withdrawn_upload_is_void_and_hidden_from_every_firm_read(
    firm: Firm,
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7101"))
    given = UploadInput(str(firm.tenant_id), UPLOAD_VERSION, str(version))
    await extract_upload(given)
    await check_upload_content(given)
    await preview_upload(given)
    assert await firm.status() == "uploaded"
    response = await firm.withdraw(firm.admin, version)
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["evidence_version_id"] == str(version)
    assert out["request_item_id"] == str(firm.site.item_id)
    at = datetime.fromisoformat(out["withdrawn_at"])
    assert datetime.fromisoformat(out["erase_after"]) - at == timedelta(days=30)
    assert await firm.status() == "requested"  # it was the item's only fulfilment
    item = f"{firm.base}/request-items/{firm.site.item_id}"
    for who in (firm.manager, firm.admin):
        uploads = await firm.net.call("GET", f"{item}/uploads", who)
        assert uploads.status_code == 200, uploads.text
        assert str(version) not in uploads.text
    listed = await firm.net.call("GET", f"{firm.base}/evidence-versions", firm.manager)
    assert listed.status_code == 200 and str(version) not in listed.text
    queue = await firm.net.call("GET", f"{firm.base}/review-queue", firm.manager)
    assert queue.status_code == 200 and str(version) not in queue.text
    for path in (
        f"{item}/uploads/{version}/preview",
        f"{item}/uploads/{version}/checks",
        f"{firm.base}/evidence-versions/{version}/preview",
        f"{firm.base}/evidence-versions/{version}/content",
        f"/v1/evidence-versions/{version}/viewer",
        f"/v1/evidence-versions/{version}/pages/1",
    ):
        refused = await firm.net.call("GET", path, firm.manager)
        assert refused.status_code == 404, (path, refused.text)
    accept = await firm.net.call(
        "POST", f"{firm.base}/evidence-versions/{version}/decision/accept", firm.manager, body={}
    )
    assert accept.status_code == 404, accept.text
    # Agents never read it, and an in-flight processing run records nothing more.
    reader = TenantContext(firm.tenant_id, "system", "agents:evidence.upload_reviewer")
    assert await review_material(reader, version) is None
    assert await extract_upload(given) in ("extracted", "withdrawn")  # done before, or skipped
    assert await check_upload_content(given) == 0


async def test_ac15_the_audit_trail_names_the_withdrawal_never_the_file(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7202"))
    response = await firm.withdraw(firm.admin, version)
    assert response.status_code == 200, response.text
    rows = await firm.seed.rows(
        "SELECT action, actor_id, target_id, before_ref::text AS b, after_ref::text AS a "
        "FROM audit_events WHERE tenant_id = $1 AND action IN "
        "('evidence_version.withdrawn', 'request_item.upload_withdrawn', 'fulfilment.withdrawn')",
        firm.tenant_id,
    )
    assert {str(r["action"]) for r in rows} == {
        "evidence_version.withdrawn",
        "request_item.upload_withdrawn",
        "fulfilment.withdrawn",
    }
    assert all(str(r["actor_id"]) == str(firm.admin.user_id) for r in rows)
    assert not any("statement" in f"{r['b']}{r['a']}" for r in rows)
    events = await firm.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'evidence_version.withdrawn'",
        firm.tenant_id,
    )
    assert events == 1


async def test_ac15_the_same_file_may_be_uploaded_again_after_a_withdrawal(firm: Firm) -> None:
    content = bank_statement_pdf(last4="7303")
    version = await firm.upload(firm.admin, content)
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    again = await firm.upload(firm.admin, content)  # not a duplicate of a withdrawn version
    assert again != version
    assert await firm.status() == "uploaded"


async def test_ac15_a_retried_withdrawal_answers_the_first_answer_once(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7404"))
    key = str(uuid.uuid4())
    first = await firm.withdraw(firm.admin, version, key)
    second = await firm.withdraw(firm.admin, version, key)
    assert first.status_code == second.status_code == 200, second.text
    assert first.json() == second.json()
    count = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_version.withdrawn'",
        firm.tenant_id,
    )
    assert count == 1
    other_key = await firm.withdraw(firm.admin, version)
    assert other_key.status_code == 404  # withdrawn: as if it never arrived


# --- who may withdraw what -----------------------------------------------------------------------


async def test_ac15_an_ever_accepted_version_answers_409_evidence_accepted(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7505"))
    accepted = await firm.net.call(
        "POST", f"{firm.base}/evidence-versions/{version}/decision/accept", firm.manager, body={}
    )
    assert accepted.status_code == 201, accepted.text
    undone = await firm.net.call(
        "POST", f"{firm.base}/review-decisions/{accepted.json()['id']}/undo", firm.manager
    )
    assert undone.status_code in (200, 201), undone.text  # undone, but it was accepted
    refused = await firm.withdraw(firm.admin, version)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "evidence_accepted"
    withdrawn = await firm.seed.value(
        "SELECT count(*) FROM evidence_withdrawals WHERE evidence_version_id = $1", version
    )
    assert withdrawn == 0


async def test_ac15_a_contributor_withdraws_only_its_own_uploads(firm: Firm) -> None:
    contributor = await firm.seed.client_contact(firm.site, "client_contributor")
    assigned = await firm.seed.item(firm.site, "Payroll register", assignee=contributor)
    by_admin = await firm.upload(firm.admin, bank_statement_pdf(last4="7606"), assigned)
    refused = await firm.withdraw(contributor, by_admin)
    assert refused.status_code == 403, refused.text
    assert refused.json()["detail"] == "not_your_upload"
    own = await firm.upload(contributor, bank_statement_pdf(last4="7607"), assigned)
    assert (await firm.withdraw(contributor, own)).status_code == 200
    # The client admin of the scope may withdraw a contributor's unaccepted upload (OQ-5).
    again = await firm.upload(contributor, bank_statement_pdf(last4="7608"), assigned)
    assert (await firm.withdraw(firm.admin, again)).status_code == 200


async def test_ac15_no_firm_role_may_withdraw_and_a_firm_upload_is_not_withdrawable(
    firm: Firm,
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7709"))
    refused = await firm.withdraw(firm.manager, version)
    assert refused.status_code == 403, refused.text
    firm_upload = await firm.upload(firm.manager, bank_statement_pdf(last4="7710"))
    not_withdrawable = await firm.withdraw(firm.admin, firm_upload)
    assert not_withdrawable.status_code == 409, not_withdrawable.text
    assert not_withdrawable.json()["detail"] == "evidence_not_withdrawable"


async def test_ac15_the_route_is_404_with_the_flag_off(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7811"))
    await firm.seed.run(
        "UPDATE feature_flag_states SET value = 'false' "
        "WHERE tenant_id = $1 AND flag = 'evidence.withdrawal'",
        firm.tenant_id,
    )
    assert (await firm.withdraw(firm.admin, version)).status_code == 404
    assert await firm.status() == "uploaded"


# --- the purge -----------------------------------------------------------------------------------


async def test_ac15_nothing_is_erased_before_30_days(
    firm: Firm, hold_check: list[uuid.UUID]
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7912"))
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    row = await firm.withdrawal(version)
    with frozen(cast(datetime, row["erase_after"]) - timedelta(hours=1)):
        wait = await erase_withdrawn(firm.tenant_id, version)
    assert 0 < wait <= 3600
    assert (await firm.withdrawal(version))["erased_at"] is None
    assert await storage.get(firm.tenant_id, await firm.stored(version))  # still opens


async def test_ac15_after_30_days_the_key_is_destroyed_and_the_upload_opens_for_no_one(
    firm: Firm, hold_check: list[uuid.UUID]
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="8013"))
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    row = await firm.withdrawal(version)
    with frozen(cast(datetime, row["erase_after"]) + timedelta(minutes=1)):
        assert await erase_withdrawn(firm.tenant_id, version) == 0
        assert await erase_withdrawn(firm.tenant_id, version) == 0  # repeat-safe
    done = await firm.withdrawal(version)
    assert done["erased_at"] is not None
    key = await firm.seed.rows(
        "SELECT wrapped_key, destroyed_at FROM evidence_object_keys "
        "WHERE evidence_version_id = $1",
        version,
    )
    assert key[0]["wrapped_key"] is None and key[0]["destroyed_at"] is not None
    with pytest.raises(storage.KeyDestroyed):
        await storage.get(firm.tenant_id, await firm.stored(version))
    erased = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_withdrawal.erased'",
        firm.tenant_id,
    )
    assert erased == 1


async def test_ac15_a_legal_hold_blocks_the_erase_and_it_is_retried_daily(
    firm: Firm, hold_check: list[uuid.UUID]
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="8114"))
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    hold_check.append(version)
    row = await firm.withdrawal(version)
    with frozen(cast(datetime, row["erase_after"]) + timedelta(days=2)):
        assert await erase_withdrawn(firm.tenant_id, version) == DAY
    blocked = await firm.withdrawal(version)
    assert (blocked["erased_at"], blocked["block_reason"]) == (None, "legal_hold")
    assert await storage.get(firm.tenant_id, await firm.stored(version))  # still there, held
    hold_check.clear()
    with frozen(cast(datetime, row["erase_after"]) + timedelta(days=3)):
        assert await erase_withdrawn(firm.tenant_id, version) == 0
    assert (await firm.withdrawal(version))["erased_at"] is not None


async def test_ac15_without_a_registered_hold_check_nothing_is_erased(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="8215"))
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    row = await firm.withdrawal(version)
    kernel_holds.reset_hold_check()
    try:
        with frozen(cast(datetime, row["erase_after"]) + timedelta(days=1)):
            assert await erase_withdrawn(firm.tenant_id, version) == DAY
    finally:
        kernel_holds.register_hold_check(holds_covering)
    blocked = await firm.withdrawal(version)
    assert (blocked["erased_at"], blocked["block_reason"]) == (None, "no_hold_check")
    assert await storage.get(firm.tenant_id, await firm.stored(version))


async def test_ac15_only_the_purge_stamps_a_withdrawal(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="8316"))
    assert (await firm.withdraw(firm.admin, version)).status_code == 200
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.run(
            "UPDATE evidence_withdrawals SET erased_at = $2 WHERE evidence_version_id = $1",
            version,
            datetime.now(UTC),
        )
