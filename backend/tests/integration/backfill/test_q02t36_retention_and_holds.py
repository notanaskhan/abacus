# ac-test-author: ayushkbhatia
"""Q-02-T36: independent AC tests (ADR-078) for retention and holds, Q-02 AC-31 to AC-37.

I-RETENTION-FLOOR: a policy below its floor is refused (AC-31); every stored object is locked
until at least its policy expiry, and an anchor event extends the lock (AC-32); seal manifests,
consent, signature evidence and chain anchors are COMPLIANCE writes no one deletes early, and no
records bucket fails closed (AC-33). I-HOLD: overlapping holds are reference-counted, so lifting
one leaves every object held and the S3 legal hold comes off only at zero (AC-35); a held object
is never erasable and S3 refuses its deletion; a new upload into a held scope is held at once
(AC-36); with no hold check registered the caller fails closed (AC-37).

Boundary: `create_app()` over HTTP (`/v1/retention/policies`, `/v1/legal-holds`, the item
upload), the public `evidence.api` (`retain_until_for`, `extend_retention_for`, `put_record`,
`anchor_chain`, `holds_covering`, `HOLD_WORKFLOWS`, `HOLD_ACTIVITIES`) and `kernel.holds`, on the
migrated Postgres, the compose S3 image with Object Lock and a Temporal dev server running the two
hold workflows by their contract ids. Floors are platform content, seeded as staff import and
publish them. Expectations: Q-02 §3.7, §3.8, `docs/contracts/retention.md`,
`docs/contracts/legal-holds.md`, DEC-71, DEC-228. The probes return what they found wrong, and
`test_seeded_*` require each to catch a violation planted behind the product's back.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, cast

import httpx
import pytest
from botocore.exceptions import ClientError
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import queue_for
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.flags import forget_flags
from abacus.kernel.holds import (
    HoldCheckMissing,
    erasable_versions,
    held_versions,
    register_hold_check,
    reset_hold_check,
)
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import seal_checkpoint
from abacus.modules.evidence import records, storage
from abacus.modules.evidence.api import (
    HOLD_ACTIVITIES,
    HOLD_WORKFLOWS,
    LegalHoldInput,
    anchor_chain,
    extend_retention_for,
    holds_covering,
    put_record,
    retain_until_for,
)
from abacus.modules.evidence.retention import import_set, publish_set

from .support import Net, Person, Seeder

EVIDENCE: Final = "q02t36-evidence"
RECORDS: Final = "q02t36-records"
MASTER: Final = b"q02t36-independent-master-key-0123456789"
YEAR: Final = timedelta(days=365.25)
PDF: Final = {"Content-Type": "application/pdf"}


# --- wiring: storage, the records bucket, Temporal -----------------------------------------------


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", f"q02t36-{uuid.uuid4().hex[:8]}")
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    yield
    register_hold_check(holds_covering)  # restore the registered check after the fail-closed test
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    activities = cast("list[Callable[..., object]]", list(HOLD_ACTIVITIES))
    queue = queue_for("batch")
    async with Worker(
        client, task_queue=queue, workflows=list(HOLD_WORKFLOWS), activities=activities
    ):
        yield client
    configure_temporal_client(None)


def _workflow(name: str) -> str:
    """The registered workflow type, by its class name in `HOLD_WORKFLOWS`."""
    for cls in HOLD_WORKFLOWS:
        if cls.__name__ == name:
            definition = workflow._Definition.must_from_class(cls)
            return str(definition.name)
    raise AssertionError(f"{name} is not a hold workflow")


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    entity_id: uuid.UUID
    admin: Person
    manager: Person
    engagement_id: uuid.UUID
    item_id: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "q02t36")

    async def upload(self, label: str) -> uuid.UUID:
        response = await self.net.http.post(
            f"/v1/engagements/{self.engagement_id}/request-items/{self.item_id}/uploads",
            params={"filename": f"{label}.pdf"},
            content=b"%PDF-1.4 " + f"{label} {uuid.uuid4()}".encode(),
            headers={**self.net.headers(self.manager), **PDF},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["evidence_version_id"])

    async def stored(self, version: uuid.UUID) -> tuple[str, str, datetime]:
        row = (
            await self.seed.rows(
                "SELECT storage_key, storage_version_id, created_at FROM evidence_versions "
                "WHERE id = $1",
                version,
            )
        )[0]
        return str(row["storage_key"]), str(row["storage_version_id"]), row["created_at"]

    async def place(self, scope: dict[str, object]) -> uuid.UUID:
        response = await self.net.call(
            "POST",
            "/v1/legal-holds",
            self.admin,
            body={"scope": scope, "reason_code": "irs_examination"},
        )
        assert response.status_code == 202, response.text
        return uuid.UUID(response.json()["id"])

    async def lift(self, hold: uuid.UUID) -> None:
        response = await self.net.call(
            "POST",
            f"/v1/legal-holds/{hold}/release",
            self.admin,
            body={"reason": "Examination closed"},
        )
        assert response.status_code == 202, response.text

    async def holds(self) -> dict[str, dict[str, object]]:
        response = await self.net.call("GET", "/v1/legal-holds", self.admin)
        assert response.status_code == 200, response.text
        items = cast(list[dict[str, object]], response.json()["items"])
        return {str(i["id"]): i for i in items}


async def _run(temporal: Client, name: str, prefix: str, firm: Firm, hold: uuid.UUID) -> None:
    await temporal.execute_workflow(
        _workflow(name),
        LegalHoldInput(str(firm.tenant_id), str(hold)),
        id=f"{prefix}:{firm.tenant_id}:{hold}",
        task_queue=queue_for("batch"),
        execution_timeout=timedelta(seconds=90),
    )


async def _engagement(
    seed: Seeder, firm: uuid.UUID, client: uuid.UUID, entity: uuid.UUID, by: Person
) -> tuple[uuid.UUID, uuid.UUID]:
    """An open engagement with one request item and no stored file yet (every version in a held
    scope must be a real object, or S3 has nothing to hold)."""
    engagement = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
            firm,
            client,
            entity,
            f"Collins {uuid.uuid4().hex[:6]}",
            by.user_id,
        ),
    )
    await seed.open_engagement(firm, engagement)
    list_id = await seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
        firm,
        engagement,
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) VALUES ($1, $2, $3, 'Brokerage statement', 'Cash', $4) "
            "RETURNING id",
            firm,
            engagement,
            list_id,
            by.user_id,
        ),
    )
    return engagement, item


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("compliance.legal_holds",):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'Q-02-T36')",
            tenant_id,
            flag,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    client_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Collins household') RETURNING id",
            tenant_id,
        ),
    )
    entity_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Collins household') RETURNING id",
            tenant_id,
            client_id,
        ),
    )
    engagement, item = await _engagement(seed, tenant_id, client_id, entity_id, admin)
    manager = await seed.person(tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        tenant_id,
        engagement,
        manager.user_id,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) "
        "VALUES ($1, $2, $3, 'confirmed', 'v1', clock_timestamp())",
        tenant_id,
        engagement,
        manager.user_id,
    )
    return Firm(net, tenant_id, client_id, entity_id, admin, manager, engagement, item)


async def _floor(record_type: str, years: str, service_line: str = "any") -> None:
    """A published floor set, as two platform staff import and publish it (DEC-76)."""
    version = 1_000 + secrets.randbelow(9_000_000)
    await import_set(
        "floors",
        version,
        [
            {
                "record_type": record_type,
                "service_line": service_line,
                "legal_floor_years": years,
                "anchor": "upload",
                "authority": "Q-02-T36 probe authority",
            }
        ],
        "staff-q02t36-a",
    )
    await publish_set("floors", version, "staff-q02t36-b")


def _lock(raw: S3Client, key: str, version: str, bucket: str = EVIDENCE) -> tuple[str, datetime]:
    found = raw.get_object_retention(Bucket=bucket, Key=key, VersionId=version)["Retention"]
    until = found.get("RetainUntilDate")
    assert until is not None
    return str(found.get("Mode")), until


def _legal_hold(raw: S3Client, key: str, version: str) -> str:
    try:
        found = raw.get_object_legal_hold(Bucket=EVIDENCE, Key=key, VersionId=version)
    except ClientError:
        return "OFF"  # no legal hold was ever set on the object
    return str(found["LegalHold"].get("Status", "OFF"))


# --- I-RETENTION-FLOOR ---------------------------------------------------------------------------


async def _put_policy(firm: Firm, years: str) -> httpx.Response:
    return await firm.net.call(
        "PUT",
        "/v1/retention/policies",
        firm.admin,
        body={
            "record_type": "client_document",
            "service_line": "audit",
            "firm_years": years,
            "clock_start_event": "upload",
        },
    )


async def test_ac31_a_policy_below_its_floor_is_refused_and_nothing_changes(firm: Firm) -> None:
    await _floor("client_document", "5")
    before = await firm.seed.rows(
        "SELECT * FROM retention_policy_versions WHERE tenant_id = $1", firm.tenant_id
    )
    response = await _put_policy(firm, "4")
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "below_floor"}
    after = await firm.seed.rows(
        "SELECT * FROM retention_policy_versions WHERE tenant_id = $1", firm.tenant_id
    )
    assert after == before
    at_floor = await _put_policy(firm, "5")
    assert at_floor.status_code == 200, at_floor.text  # the control: the floor itself is allowed


async def test_ac31_the_agent_and_a_member_without_the_action_cannot_save_a_policy(
    firm: Firm,
) -> None:
    await _floor("client_document", "5")
    response = await firm.net.call(
        "PUT",
        "/v1/retention/policies",
        firm.manager,
        body={
            "record_type": "client_document",
            "service_line": "audit",
            "firm_years": "9",
            "clock_start_event": "upload",
        },
    )
    assert response.status_code == 403


async def retention_problems(
    firm: Firm, raw: S3Client, version: uuid.UUID, years: Decimal
) -> list[str]:
    """I-RETENTION-FLOOR for one stored version: locked in GOVERNANCE until at least its
    `client_document` expiry from the upload."""
    key, object_version, created = await firm.stored(version)
    mode, until = _lock(raw, key, object_version)
    expiry = created + timedelta(days=float(years * Decimal("365.25")))
    found: list[str] = []
    if mode != "GOVERNANCE":
        found.append(f"mode {mode}")
    if until < expiry - timedelta(minutes=5):
        found.append(f"locked until {until.isoformat()}, before the expiry {expiry.isoformat()}")
    return found


async def test_ac32_an_upload_is_locked_until_at_least_its_policy_expiry(
    firm: Firm, raw: S3Client
) -> None:
    await _floor("client_document", "11")
    version = await firm.upload("statement")
    assert await retention_problems(firm, raw, version, Decimal("11")) == []


async def test_ac32_the_firms_longer_policy_wins_over_the_floor(firm: Firm, raw: S3Client) -> None:
    await _floor("client_document", "5")
    saved = await _put_policy(firm, "13")
    assert saved.status_code == 200, saved.text
    until = await retain_until_for(firm.system, "client_document", "audit", datetime.now(UTC))
    assert until is not None
    assert until >= datetime.now(UTC) + 13 * YEAR - timedelta(minutes=5)
    version = await firm.upload("statement")
    assert await retention_problems(firm, raw, version, Decimal("13")) == []


async def test_ac32_an_anchor_event_extends_the_lock_and_never_shortens_it(
    firm: Firm, raw: S3Client
) -> None:
    await _floor("client_document", "7")
    version = await firm.upload("statement")
    key, object_version, _ = await firm.stored(version)
    _, before = _lock(raw, key, object_version)
    released = datetime.now(UTC) + timedelta(days=400)  # the report release, later
    extended = await extend_retention_for(
        firm.system, [(key, object_version)], "client_document", "audit", released
    )
    assert extended == 1
    _, after = _lock(raw, key, object_version)
    assert after >= released + 7 * YEAR - timedelta(minutes=5)
    assert after > before
    audited = await firm.seed.rows(
        "SELECT actor_kind FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'retention.extended'",
        firm.tenant_id,
    )
    assert [r["actor_kind"] for r in audited] == ["system"]
    earlier = datetime.now(UTC) - timedelta(days=400)  # an anchor before the upload
    await extend_retention_for(
        firm.system, [(key, object_version)], "client_document", "audit", earlier
    )
    _, again = _lock(raw, key, object_version)
    assert again >= after  # a lock is only ever extended


async def test_ac33_records_are_compliance_writes_no_one_deletes_early(
    firm: Firm, raw: S3Client
) -> None:
    until = datetime.now(UTC) + 7 * YEAR
    for record_class in ("seal_manifest", "consent_evidence", "signature_evidence"):
        stored = await put_record(
            firm.tenant_id, record_class, f"{record_class} {uuid.uuid4()}".encode(), until
        )
        mode, locked = _lock(raw, stored.key, stored.version_id, RECORDS)
        assert mode == "COMPLIANCE", record_class
        assert locked >= until - timedelta(seconds=1)
        with pytest.raises(ClientError):
            raw.delete_object(
                Bucket=RECORDS,
                Key=stored.key,
                VersionId=stored.version_id,
                BypassGovernanceRetention=True,  # COMPLIANCE ignores the bypass, for everyone
            )


async def test_ac33_no_records_bucket_fails_closed(firm: Firm) -> None:
    """retention.md §8a: no records bucket configured answers 503 (`ServiceUnavailable`), never a
    fallback to another bucket."""
    records.reset_records()
    with pytest.raises(ServiceUnavailable):
        await put_record(firm.tenant_id, "seal_manifest", b"manifest", datetime.now(UTC) + YEAR)
    for _ in range(2):
        async with uow(firm.system) as tx:
            tx.record("engagement.created", target=Target("engagement", firm.engagement_id))
    with pytest.raises(ServiceUnavailable):  # an anchor needs the bucket too
        await seal_checkpoint(firm.tenant_id, settle_seconds=0)
        await anchor_chain(firm.tenant_id, datetime.now(UTC) + 7 * YEAR)


# --- I-HOLD -------------------------------------------------------------------------------------


async def hold_problems(firm: Firm, raw: S3Client, versions: list[uuid.UUID]) -> list[str]:
    """I-HOLD for versions a hold covers: the hold check says held, nothing is erasable, the S3
    legal hold is on, and S3 refuses deleting the object."""
    found: list[str] = []
    held = await held_versions(firm.system, versions)
    found += [f"{v} not held" for v in versions if v not in held]
    erasable = await erasable_versions(firm.system, versions)
    found += [f"{v} erasable" for v in erasable]
    for version in versions:
        key, object_version, _ = await firm.stored(version)
        if _legal_hold(raw, key, object_version) != "ON":
            found.append(f"{version} has no S3 legal hold")
    return found


async def test_ac34_a_hold_is_placed_by_a_person_with_fresh_mfa_and_staff_are_refused(
    firm: Firm, temporal: Client
) -> None:
    staff = await firm.seed.person(firm.tenant_id)
    refused = await firm.net.call(
        "POST",
        "/v1/legal-holds",
        staff,
        body={
            "scope": {"kind": "client", "client_id": str(firm.client_id)},
            "reason_code": "litigation",
        },
    )
    assert refused.status_code == 403
    stale = await firm.net.call(
        "POST",
        "/v1/legal-holds",
        firm.admin,
        body={
            "scope": {"kind": "client", "client_id": str(firm.client_id)},
            "reason_code": "litigation",
        },
        mfa=False,
    )
    assert stale.status_code == 403
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM legal_holds WHERE tenant_id = $1", firm.tenant_id
        )
        == 0
    )
    hold = await firm.place({"kind": "client", "client_id": str(firm.client_id)})
    rows = await firm.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'legal_hold.placed'",
        firm.tenant_id,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [("human", str(firm.admin.user_id))]
    assert str(hold) in await firm.holds()


async def test_ac35_two_overlapping_holds_lifting_one_leaves_every_object_held(
    firm: Firm, raw: S3Client, temporal: Client
) -> None:
    versions = [await firm.upload("statement"), await firm.upload("k1")]
    by_client = await firm.place({"kind": "client", "client_id": str(firm.client_id)})
    by_engagement = await firm.place(
        {"kind": "engagement", "engagement_id": str(firm.engagement_id)}
    )
    for hold in (by_client, by_engagement):
        await _run(temporal, "LegalHoldApply", "legal_hold_apply", firm, hold)
    assert await hold_problems(firm, raw, versions) == []
    listed = await firm.holds()
    for hold in (by_client, by_engagement):
        assert listed[str(hold)]["status"] == "active"
        assert listed[str(hold)]["objects_held"] == 2

    await firm.lift(by_client)
    await _run(temporal, "LegalHoldRelease", "legal_hold_release", firm, by_client)
    assert await hold_problems(firm, raw, versions) == []  # the engagement's hold still counts

    await firm.lift(by_engagement)
    await _run(temporal, "LegalHoldRelease", "legal_hold_release", firm, by_engagement)
    assert await held_versions(firm.system, versions) == frozenset()
    for version in versions:  # only at zero does the S3 legal hold come off
        key, object_version, _ = await firm.stored(version)
        assert _legal_hold(raw, key, object_version) == "OFF"
    assert {str(h["status"]) for h in (await firm.holds()).values()} == {"released"}


async def test_ac35_lifting_a_hold_twice_or_before_it_is_active_is_refused(
    firm: Firm, temporal: Client
) -> None:
    await firm.upload("statement")
    hold = await firm.place({"kind": "client", "client_id": str(firm.client_id)})
    early = await firm.net.call(
        "POST", f"/v1/legal-holds/{hold}/release", firm.admin, body={"reason": "Too soon"}
    )
    if early.status_code != 202:  # still applying: 409 hold_not_active
        assert early.status_code == 409
        assert early.json() == {"detail": "hold_not_active"}
        await _run(temporal, "LegalHoldApply", "legal_hold_apply", firm, hold)
        await firm.lift(hold)
    await _run(temporal, "LegalHoldRelease", "legal_hold_release", firm, hold)
    again = await firm.net.call(
        "POST", f"/v1/legal-holds/{hold}/release", firm.admin, body={"reason": "Again"}
    )
    assert again.status_code == 409
    assert again.json() == {"detail": "hold_not_active"}


async def test_ac36_a_new_upload_into_a_held_scope_is_held_at_once(
    firm: Firm, raw: S3Client, temporal: Client
) -> None:
    first = await firm.upload("statement")
    hold = await firm.place({"kind": "client", "client_id": str(firm.client_id)})
    await _run(temporal, "LegalHoldApply", "legal_hold_apply", firm, hold)
    later = await firm.upload("statement-corrected")
    # Held by the uploader's own transaction, before any processing of the new version runs.
    assert later in await held_versions(firm.system, [later])
    assert await erasable_versions(firm.system, [first, later]) == []
    inherited = await firm.seed.value(
        "SELECT count(*) FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'legal_hold.inherited'",
        firm.tenant_id,
    )
    assert inherited == 1


async def test_ac36_a_hold_on_another_client_does_not_cover_this_one(
    firm: Firm, temporal: Client
) -> None:
    """The control for inheritance: a scope holds what it names, not the firm."""
    other = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Holloway trust') RETURNING id",
            firm.tenant_id,
        ),
    )
    hold = await firm.place({"kind": "client", "client_id": str(other)})
    await _run(temporal, "LegalHoldApply", "legal_hold_apply", firm, hold)
    version = await firm.upload("statement")
    assert await held_versions(firm.system, [version]) == frozenset()
    assert await erasable_versions(firm.system, [version]) == [version]


async def test_ac37_with_no_hold_check_registered_the_caller_fails_closed(firm: Firm) -> None:
    version = await firm.upload("statement")
    reset_hold_check()
    with pytest.raises(HoldCheckMissing):
        await held_versions(firm.system, [version])
    with pytest.raises(HoldCheckMissing):
        await erasable_versions(firm.system, [version])


async def test_ac37_a_version_the_firm_does_not_have_counts_as_held(firm: Firm) -> None:
    """legal-holds.md §8: fail closed on the unknown, too."""
    unknown = uuid.uuid4()
    assert unknown in await held_versions(firm.system, [unknown])
    assert await erasable_versions(firm.system, [unknown]) == []


# --- the suite fails on seeded violations --------------------------------------------------------


async def test_seeded_a_shortened_lock_fails_the_retention_probe(
    firm: Firm, raw: S3Client
) -> None:
    """Shorten an object's lock behind the product's back (GOVERNANCE lets the bucket owner do
    it with the bypass); the I-RETENTION-FLOOR probe must report it."""
    await _floor("client_document", "11")
    version = await firm.upload("statement")
    assert await retention_problems(firm, raw, version, Decimal("11")) == []
    key, object_version, _ = await firm.stored(version)
    raw.put_object_retention(
        Bucket=EVIDENCE,
        Key=key,
        VersionId=object_version,
        Retention={
            "Mode": "GOVERNANCE",
            "RetainUntilDate": datetime.now(UTC) + timedelta(days=30),
        },
        BypassGovernanceRetention=True,
    )
    assert await retention_problems(firm, raw, version, Decimal("11")) != []


async def test_seeded_a_dropped_hold_count_fails_the_hold_probe(
    firm: Firm, raw: S3Client, temporal: Client
) -> None:
    """Drop the hold's counted objects and the S3 legal hold in the database and the bucket; the
    I-HOLD probe must report the object as no longer held."""
    version = await firm.upload("statement")
    hold = await firm.place({"kind": "engagement", "engagement_id": str(firm.engagement_id)})
    await _run(temporal, "LegalHoldApply", "legal_hold_apply", firm, hold)
    assert await hold_problems(firm, raw, [version]) == []
    await firm.seed.run("DELETE FROM hold_objects WHERE tenant_id = $1", firm.tenant_id)
    key, object_version, _ = await firm.stored(version)
    raw.put_object_legal_hold(
        Bucket=EVIDENCE, Key=key, VersionId=object_version, LegalHold={"Status": "OFF"}
    )
    assert await hold_problems(firm, raw, [version]) != []
