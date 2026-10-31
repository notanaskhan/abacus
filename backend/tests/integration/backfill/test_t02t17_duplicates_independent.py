# ac-test-author: ayushkbhatia
"""T-02-T17 (ADR-078; TASK-2433; DEC-58 g; DEC-1371): the independent suite for the
duplicate-upload policy, written from the row and DEC-1371, not from the builder's tests.

The row's acceptance: "A discarded duplicate is voided and hidden but never deleted and an
accepted version can never be discarded." With `evidence.duplicate_review` on, a client person's
second upload of the same bytes on a request is accepted and flagged `duplicate_hash` for the
firm; the firm's own upload of the same bytes keeps the 409. A person on the request resolves it:
Discard duplicate voids the copy's fulfilment (the request no longer lists it; the version, its
bytes and its audit stay; no erasure is scheduled), Keep newer voids the older one instead; a
version that was ever accepted is never the one voided (409 `evidence_accepted`); a version is
resolved once (409 `duplicate_resolved`). A client principal and a non-person never resolve, and
the route is 404 with the flag off. The database refuses deleting the version or rewriting the
decision.

Boundary: `create_app()` over HTTP as the client's people and the firm's, the migrated Postgres,
the compose S3 image with Object Lock (P-06-T19's harness).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

import asyncpg
import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.duplicates import resolve
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus_tools.synthetic.documents import bank_statement_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = f"t02t17-duplicates-{uuid.uuid4().hex[:12]}"
MASTER: Final = b"t02t17-duplicates-master-key-0123456789ab"
PDF: Final = "application/pdf"


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

    @property
    def item(self) -> str:
        return f"{self.base}/request-items/{self.site.item_id}"

    async def post(self, who: Person, content: bytes) -> httpx.Response:
        return await self.net.http.post(
            f"{self.item}/uploads",
            params={"filename": "statement.pdf"},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )

    async def upload(self, who: Person, content: bytes) -> uuid.UUID:
        response = await self.post(who, content)
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["evidence_version_id"])

    async def resolve(self, who: Person, version: uuid.UUID, decision: str) -> httpx.Response:
        return await self.net.call(
            "POST",
            f"{self.item}/evidence-versions/{version}/duplicate-resolution",
            who,
            body={"decision": decision},
        )

    async def accept(self, version: uuid.UUID) -> uuid.UUID:
        accepted = await self.net.call(
            "POST",
            f"{self.base}/evidence-versions/{version}/decision/accept",
            self.manager,
            body={},
        )
        assert accepted.status_code == 201, accepted.text
        return uuid.UUID(accepted.json()["id"])

    async def listed(self, who: Person) -> str:
        uploads = await self.net.call("GET", f"{self.item}/uploads", who)
        assert uploads.status_code == 200, uploads.text
        return uploads.text

    async def flags(self, version: uuid.UUID) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT check_code, outcome, audience FROM upload_checks "
            "WHERE evidence_version_id = $1 AND check_code = 'duplicate_hash'",
            version,
        )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("uploads.processing", "evidence.duplicate_review"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-02-T17')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Feld")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    admin = await seed.client_contact(site, "client_admin")
    return Firm(net, tenant_id, manager, admin, site)


async def _pair(firm: Firm, last4: str) -> tuple[uuid.UUID, uuid.UUID]:
    """The client's upload and its second, byte-identical upload on the same request."""
    content = bank_statement_pdf(last4=last4)
    first = await firm.upload(firm.admin, content)
    again = await firm.upload(firm.admin, content)
    assert again != first
    return first, again


# --- the client's repeat is accepted and flagged; the firm's keeps the 409 ----------------------


async def test_ac_a_clients_repeat_upload_is_accepted_and_flagged_for_the_firm(
    firm: Firm,
) -> None:
    first, again = await _pair(firm, "8101")
    assert await firm.flags(first) == []
    assert [(r["outcome"], r["audience"]) for r in await firm.flags(again)] == [
        ("problem", "firm")
    ]
    listed = await firm.listed(firm.manager)
    assert str(first) in listed and str(again) in listed


async def test_ac_the_firms_upload_of_the_same_bytes_keeps_the_409(firm: Firm) -> None:
    content = bank_statement_pdf(last4="8202")
    await firm.upload(firm.admin, content)
    refused = await firm.post(firm.manager, content)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "duplicate_upload"


# --- discard: voided and hidden, never deleted --------------------------------------------------


async def test_ac_a_discarded_duplicate_is_voided_and_hidden_but_never_deleted(
    firm: Firm,
) -> None:
    first, again = await _pair(firm, "8303")
    resolved = await firm.resolve(firm.manager, again, "discard_duplicate")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json() == {
        "evidence_version_id": str(again),
        "kept_version_id": str(first),
        "decision": "discard_duplicate",
    }
    for who in (firm.manager, firm.admin):
        listed = await firm.listed(who)
        assert str(again) not in listed and str(first) in listed
    # Never deleted: the version and its bytes stay, and no erasure is scheduled for it.
    kept = await firm.seed.rows(
        "SELECT storage_key, storage_version_id, fingerprint, size_bytes FROM evidence_versions "
        "WHERE id = $1",
        again,
    )
    assert len(kept) == 1
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM evidence_withdrawals WHERE evidence_version_id = $1", again
        )
        == 0
    )
    actions = await firm.seed.rows(
        "SELECT action, actor_id FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "AND action LIKE 'evidence_version.duplicate_%'",
        firm.tenant_id,
        str(again),
    )
    assert [(r["action"], r["actor_id"]) for r in actions] == [
        ("evidence_version.duplicate_discarded", str(firm.manager.user_id))
    ]
    hidden = await firm.resolve(firm.manager, again, "keep_newer")  # off the request now
    assert hidden.status_code == 404, hidden.text
    with pytest.raises(asyncpg.PostgresError):
        await firm.seed.run("DELETE FROM evidence_versions WHERE id = $1", again)
    for statement in (
        "UPDATE duplicate_resolutions SET decision = 'keep_newer' WHERE version_id = $1",
        "DELETE FROM duplicate_resolutions WHERE version_id = $1",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await firm.seed.run(statement, again)


async def test_ac_keep_newer_voids_the_older_copy_instead(firm: Firm) -> None:
    first, again = await _pair(firm, "8404")
    resolved = await firm.resolve(firm.manager, again, "keep_newer")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["kept_version_id"] == str(again)
    listed = await firm.listed(firm.manager)
    assert str(first) not in listed and str(again) in listed
    assert (
        await firm.seed.value("SELECT count(*) FROM evidence_versions WHERE id = $1", first) == 1
    )
    twice = await firm.resolve(firm.manager, again, "discard_duplicate")
    assert twice.status_code == 409, twice.text
    assert twice.json()["detail"] == "duplicate_resolved"


# --- an accepted version is never the one voided ------------------------------------------------


async def test_ac_an_accepted_version_can_never_be_discarded(firm: Firm) -> None:
    first, again = await _pair(firm, "8505")
    # The copy once accepted, then undone: it is never the one discarded.
    decision = await firm.accept(again)
    undone = await firm.net.call(
        "POST", f"{firm.base}/review-decisions/{decision}/undo", firm.manager
    )
    assert undone.status_code in (200, 201), undone.text
    copy = await firm.resolve(firm.manager, again, "discard_duplicate")
    assert copy.status_code == 409, copy.text
    assert copy.json()["detail"] == "evidence_accepted"
    listed = await firm.listed(firm.manager)
    assert str(first) in listed and str(again) in listed
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM duplicate_resolutions WHERE version_id = $1", again
        )
        == 0
    )


# --- who resolves -------------------------------------------------------------------------------


async def test_inv_a_client_a_non_person_and_the_flag_off_never_resolve(firm: Firm) -> None:
    _, again = await _pair(firm, "8606")
    by_client = await firm.resolve(firm.admin, again, "discard_duplicate")
    assert by_client.status_code == 404, by_client.text
    planted_tenants = (
        TenantContext(firm.tenant_id, "agent", f"agent:x:{uuid.uuid4()}"),
        TenantContext(firm.tenant_id, "system", "evidence:planted"),
    )
    for tenant in planted_tenants:
        planted = AuthContext(
            tenant,
            firm.manager.user_id,
            uuid.uuid4(),
            None,
            datetime.now(UTC),
        )
        with pytest.raises(Forbidden):
            await resolve(
                planted,
                firm.site.engagement_id,
                firm.site.item_id,
                again,
                "discard_duplicate",
            )
    await firm.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'evidence.duplicate_review'",
        firm.tenant_id,
    )
    forget_flags()
    off = await firm.resolve(firm.manager, again, "discard_duplicate")
    assert off.status_code == 404, off.text
    assert (
        cast(
            int,
            await firm.seed.value(
                "SELECT count(*) FROM duplicate_resolutions WHERE version_id = $1", again
            ),
        )
        == 0
    )
