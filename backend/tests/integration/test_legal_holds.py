"""Q-02-T29 against Postgres and S3-compatible Object Lock (migration 0126; Q-02 AC-34 to AC-37).

The row's acceptance: with two overlapping holds, lifting one leaves every object held; a new
upload into a held scope is held; and an unregistered hold check refuses the purge. The
workflows' steps are called here in the order `LegalHoldApply` and `LegalHoldRelease` call them
(their replay histories are in `tests/workflows/`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

import asyncpg
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.holds import (
    HoldCheckMissing,
    erasable_versions,
    held_versions,
    register_hold_check,
    reset_hold_check,
)
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.modules.evidence import holds, storage
from abacus.modules.evidence.holds import HoldNotActive, HoldScope, NotifyNotMember
from abacus.modules.evidence.service import NewItem, Provenance, add_version
from abacus.modules.evidence.storage import StoredObject
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

FirmRole = Literal["firm_admin", "practice_leader", "quality_partner", "security_admin"]
BUCKET = "legal-holds-evidence"
MASTER = bytes(range(32))


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
async def wired(migrated_db: MigratedDatabase, raw: S3Client) -> AsyncIterator[None]:
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    register_hold_check(holds.holds_covering)
    storage.reset_storage()
    reset_key_service()
    await dispose_engine()
    forget_flags()
    settings.cache_clear()


class Firm:
    def __init__(
        self, seed: Seeder, tenant: uuid.UUID, client: uuid.UUID, entity: uuid.UUID
    ) -> None:
        self.seed, self.tenant, self.client, self.entity = seed, tenant, client, entity

    async def person(
        self, *, firm_role: FirmRole | None = None, level: str | None = None, kind: str = "staff"
    ) -> AuthContext:
        user = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, 'Victor Hammond') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', $4, $5)",
            self.tenant,
            user,
            firm_role,
            level,
            kind,
        )
        return AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )

    async def engagement(self, by: AuthContext, start: str, end: str) -> uuid.UUID:
        engagement = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                self.tenant,
                self.client,
                self.entity,
                f"Collins {uuid.uuid4().hex[:6]}",
                date.fromisoformat(start),
                date.fromisoformat(end),
                by.user_id,
            ),
        )
        await Seeder.open(self.seed, self.tenant, engagement)
        return engagement

    async def upload(self, by: AuthContext, engagement: uuid.UUID, content: bytes) -> uuid.UUID:
        stored = await storage.put(self.tenant, content)
        async with uow(by.tenant) as tx:
            ref = await add_version(
                tx,
                engagement_id=engagement,
                item=NewItem("CP2000 notice"),
                stored=stored,
                media_type="application/pdf",
                provenance=Provenance(source="upload", method="uploaded"),
            )
        return ref.id


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> Firm:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    entity = await seed.entity(tenant, "Collins household")
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'compliance.legal_holds', 'true', 'test-seed', 'Q-02-T29')",
        tenant,
    )
    return Firm(seed, tenant, client, entity)


async def _stored(firm: Firm, version: uuid.UUID) -> StoredObject:
    row = (
        await firm.seed.rows(
            "SELECT storage_key, storage_version_id FROM evidence_versions WHERE id = $1",
            version,
        )
    )[0]
    return StoredObject(row["storage_key"], row["storage_version_id"], "", 0)


def _sys(firm: Firm) -> TenantContext:
    return TenantContext(firm.tenant, "system", "probe")


async def _s3_held(firm: Firm, version: uuid.UUID) -> bool:
    return await storage.legal_hold_on(await _stored(firm, version))


async def _apply(firm: Firm, hold: uuid.UUID) -> str:
    while await holds.apply_batch(firm.tenant, hold) > 0:
        pass
    return await holds.activate(firm.tenant, hold)


async def _release(firm: Firm, hold: uuid.UUID) -> str:
    while await holds.release_batch(firm.tenant, hold) > 0:
        pass
    return await holds.finish_release(firm.tenant, hold)


async def test_ac34_a_partner_holds_a_client_tax_year_and_every_version_in_it_is_held(
    firm: Firm,
) -> None:
    victor = await firm.person(level="partner")
    admin = await firm.person(firm_role="firm_admin")
    ty2023 = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    ty2024 = await firm.engagement(admin, "2024-01-01", "2024-12-31")
    held = [await firm.upload(admin, ty2023, f"notice {n}".encode()) for n in range(2)]
    other = await firm.upload(admin, ty2024, b"a 2024 return")

    view = await holds.place_hold(
        victor,
        HoldScope("client_tax_year", client_id=firm.client, tax_year=2023),
        "irs_examination",
        "CP2000 for TY2023",
        [admin.user_id],
    )
    assert view.status == "applying" and view.objects_held == 2 and view.objects_applied == 0
    # The database counts the hold before S3 is touched (R12).
    assert await holds.holds_covering(_sys(firm), [*held, other]) == frozenset(held)
    assert not await _s3_held(firm, held[0])

    assert await _apply(firm, view.id) == "active"
    assert all([await _s3_held(firm, v) for v in held])
    assert not await _s3_held(firm, other)
    events = await firm.seed.rows(
        "SELECT action, actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'legal_hold.%' ORDER BY seq",
        firm.tenant,
    )
    assert (events[0]["action"], events[0]["actor_kind"], events[0]["actor_id"]) == (
        "legal_hold.placed",
        "human",
        str(victor.user_id),
    )
    assert {"legal_hold.applied", "legal_hold.activated"} <= {e["action"] for e in events}
    assert {e["actor_kind"] for e in events[1:]} == {"system"}
    outbox = await firm.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'legal_hold.placed'",
        firm.tenant,
    )
    assert len(outbox) == 1


async def test_ac34_staff_stale_mfa_agentless_and_flag_off_are_refused(firm: Firm) -> None:
    staff = await firm.person()
    with pytest.raises(Forbidden):
        await holds.place_hold(
            staff, HoldScope("client", client_id=firm.client), "other", None, []
        )
    partner = await firm.person(level="partner")
    stale = AuthContext(
        tenant=partner.tenant,
        user_id=partner.user_id,
        membership_id=partner.membership_id,
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(days=1),
    )
    with pytest.raises(Forbidden):
        await holds.place_hold(
            stale, HoldScope("client", client_id=firm.client), "other", None, []
        )
    portal = await firm.person(kind="client")
    with pytest.raises(NotifyNotMember):
        await holds.place_hold(
            partner, HoldScope("client", client_id=firm.client), "other", None, [portal.user_id]
        )
    with pytest.raises(NotFound):
        await holds.place_hold(
            partner, HoldScope("client", client_id=uuid.uuid4()), "other", None, []
        )
    await firm.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1", firm.tenant
    )
    forget_flags()
    with pytest.raises(NotFound):
        await holds.list_holds(partner)


async def test_ac34_the_database_refuses_a_hold_not_placed_by_the_sessions_person(
    firm: Firm,
) -> None:
    partner = await firm.person(level="partner")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.as_actor(
            firm.tenant,
            ("system", "legal_holds"),
            "INSERT INTO legal_holds (tenant_id, scope_kind, client_id, reason_code, placed_by) "
            "VALUES ($1, 'client', $2, 'other', $3)",
            firm.tenant,
            firm.client,
            partner.user_id,
        )


async def test_ac35_with_two_overlapping_holds_lifting_one_leaves_every_object_held(
    firm: Firm,
) -> None:
    admin = await firm.person(firm_role="security_admin")
    engagement = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    versions = [await firm.upload(admin, engagement, f"statement {n}".encode()) for n in range(3)]
    client_hold = await holds.place_hold(
        admin, HoldScope("client", client_id=firm.client), "litigation", None, []
    )
    engagement_hold = await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=engagement), "subpoena", None, []
    )
    with pytest.raises(HoldNotActive):  # not yet applied
        await holds.lift_hold(admin, client_hold.id, "Matter closed")
    assert await _apply(firm, client_hold.id) == "active"
    assert await _apply(firm, engagement_hold.id) == "active"

    lifted = await holds.lift_hold(admin, client_hold.id, "Matter closed")
    assert lifted.status == "releasing" and lifted.released_by == admin.user_id
    assert await _release(firm, client_hold.id) == "released"
    assert all([await _s3_held(firm, v) for v in versions])
    assert await holds.holds_covering(_sys(firm), versions) == frozenset(versions)
    with pytest.raises(HoldNotActive):
        await holds.lift_hold(admin, client_hold.id, "Again")

    await holds.lift_hold(admin, engagement_hold.id, "Subpoena withdrawn")
    assert await _release(firm, engagement_hold.id) == "released"
    assert not any([await _s3_held(firm, v) for v in versions])
    assert await holds.holds_covering(_sys(firm), versions) == frozenset()
    counts = await firm.seed.rows(
        "SELECT active_hold_count(id) AS n FROM evidence_versions WHERE tenant_id = $1",
        firm.tenant,
    )
    assert {r["n"] for r in counts} == {0}


async def test_ac35_a_stored_object_shared_by_two_versions_stays_held_for_the_other(
    firm: Firm,
) -> None:
    admin = await firm.person(firm_role="firm_admin")
    held_engagement = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    free_engagement = await firm.engagement(admin, "2019-01-01", "2019-12-31")
    a = await firm.upload(admin, held_engagement, b"the same brokerage statement")
    b = await firm.upload(admin, free_engagement, b"the same brokerage statement")
    assert (await _stored(firm, a)).key == (await _stored(firm, b)).key
    one = await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=held_engagement), "other", None, []
    )
    two = await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=free_engagement), "other", None, []
    )
    await _apply(firm, one.id)
    await _apply(firm, two.id)
    await holds.lift_hold(admin, two.id, "Done")
    await _release(firm, two.id)
    assert await _s3_held(firm, a)  # the object is still named by the first hold


async def test_ac36_a_new_upload_into_a_held_scope_is_held_before_its_processing(
    firm: Firm,
) -> None:
    admin = await firm.person(firm_role="firm_admin")
    engagement = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    hold = await holds.place_hold(
        admin,
        HoldScope("client_tax_year", client_id=firm.client, tax_year=2023),
        "other",
        None,
        [],
    )
    await _apply(firm, hold.id)
    later = await firm.upload(admin, engagement, b"a late upload")
    # Held from its own creating transaction, before any consumer ran.
    assert await held_versions(admin.tenant, [later]) == frozenset({later})
    rows = await firm.seed.rows(
        "SELECT applied_at FROM hold_objects WHERE evidence_version_id = $1", later
    )
    assert len(rows) == 1 and rows[0]["applied_at"] is None
    assert await holds.apply_version_holds(firm.tenant, later) == 1  # the outbox consumer
    assert await _s3_held(firm, later)
    assert await holds.apply_version_holds(firm.tenant, later) == 0  # repeat-safe


async def test_ac36_a_version_written_while_a_hold_was_placed_is_held_by_scope(
    firm: Firm,
) -> None:
    admin = await firm.person(firm_role="firm_admin")
    engagement = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    hold = await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=engagement), "other", None, []
    )
    # A version whose transaction didn't see the hold (written around the trigger-free path).
    stored = await storage.put(firm.tenant, b"raced upload")
    item = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Raced', 'human', 'probe') RETURNING id",
            firm.tenant,
            engagement,
        ),
    )
    raced = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, $6, 1, 'application/pdf', "
            "'upload', 'uploaded') RETURNING id",
            firm.tenant,
            engagement,
            item,
            stored.fingerprint,
            stored.key,
            stored.version_id,
        ),
    )
    assert await holds.holds_covering(_sys(firm), [raced]) == frozenset({raced})
    assert await _apply(firm, hold.id) == "active"  # the workflow counts it too
    assert await _s3_held(firm, raced)


async def test_ac37_a_held_version_is_excluded_and_no_check_means_nothing_erased(
    firm: Firm,
) -> None:
    admin = await firm.person(firm_role="firm_admin")
    held_engagement = await firm.engagement(admin, "2023-01-01", "2023-12-31")
    free_engagement = await firm.engagement(admin, "2018-01-01", "2018-12-31")
    kept = await firm.upload(admin, held_engagement, b"held statement")
    gone = await firm.upload(admin, free_engagement, b"withdrawable upload")
    await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=held_engagement), "other", None, []
    )
    assert await erasable_versions(admin.tenant, [kept, gone]) == [gone]
    assert await erasable_versions(admin.tenant, [uuid.uuid4()]) == []  # unknown: held
    reset_hold_check()
    with pytest.raises(HoldCheckMissing):
        await erasable_versions(admin.tenant, [gone])
    with pytest.raises(HoldCheckMissing):
        await held_versions(admin.tenant, [])


async def test_the_list_shows_metadata_to_readers_and_hides_walled_clients(firm: Firm) -> None:
    admin = await firm.person(firm_role="firm_admin")
    quality = await firm.person(firm_role="quality_partner")
    staff = await firm.person()
    engagement = await firm.engagement(admin, "2024-01-01", "2024-12-31")
    await firm.upload(admin, engagement, b"Meridian IL-1120")
    hold = await holds.place_hold(
        admin, HoldScope("engagement", engagement_id=engagement), "regulatory_inquiry", "x", []
    )
    seen = await holds.list_holds(quality)
    assert [(h.id, h.objects_held, h.reason_code) for h in seen] == [
        (hold.id, 1, "regulatory_inquiry")
    ]
    assert not hasattr(seen[0], "details")
    assert await holds.list_holds(staff) == []
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, client_id, user_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        firm.client,
        quality.user_id,
        admin.user_id,
    )
    assert await holds.list_holds(quality) == []
