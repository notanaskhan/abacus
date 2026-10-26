"""G-02-T09 gap (TASK-1364; DEC-459): value resolvers for the five audit sources whose owners exist
(SPEC-349 AC-5, AC-10, AC-11; DEC-60, ADR-024, ADR-031).

- `evidence_version` and `pii_reveal` (evidence), `request_item` (requests), `membership` and
  `support_session` (identity, registered by platform) each answer a resolved section for a
  viewer with the content read (the engagement team on an engagement event, the QM owner on a
  firm-level one).
- A Restricted value only ever comes back masked: the reveal answers `•••-••-6081` and never the
  sealed value; no row of any resolver is Restricted in clear.
- Need to know (`firm_admin`) and the flag off still withhold, for every type.
- Facts the event pins only: a membership changed since the event, or a target outside the
  event's engagement, is "Values not available".
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from sqlalchemy import text

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

LIST: Final = "/v1/audit-events"
Call = Callable[..., Awaitable[httpx.Response]]
SSN_LAST4: Final = "6081"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, firm_role: str | None, level: str | None = None
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', $4, 'staff') RETURNING id",
            tenant,
            user,
            firm_role,
            level,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str, value: str) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, $3, 'g02t09', 'G-02-T09') ON CONFLICT (tenant_id, flag) "
        "DO UPDATE SET value = EXCLUDED.value",
        tenant,
        flag,
        value,
    )


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    grace: AuthContext  # firm_admin: metadata only
    margaret: AuthContext  # quality_partner: firm-level values
    hannah: AuthContext  # manager on Copperleaf: its values
    copperleaf: uuid.UUID
    ashford: uuid.UUID


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    for flag in ("audit_log.explorer", "audit_log.values"):
        await _flag(seed, tenant, flag, "true")
    grace = await _member(seed, tenant, "Grace Holloway", "firm_admin")
    margaret = await _member(seed, tenant, "Margaret Okonkwo", "quality_partner", "partner")
    hannah = await _member(seed, tenant, "Hannah Leclerc", None, "manager")
    copperleaf = await seed.engagement(
        tenant, await seed.entity(tenant, "Copperleaf Coffee Roasters, Inc."), grace.user_id
    )
    ashford = await seed.engagement(
        tenant, await seed.entity(tenant, "Ashford Manufacturing Co."), grace.user_id
    )
    await seed.member(copperleaf, Person(hannah.user_id, tenant), "manager")
    return World(tenant, grace, margaret, hannah, copperleaf, ashford)


@pytest.fixture
def as_() -> Callable[[object], Call]:
    def bind(ctx: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: ctx
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

        return call

    return bind


async def _record(
    world: World,
    action: str,
    target: Target,
    *,
    before: Ref | None = None,
    after: Ref | None = None,
    scope: Scope | None = None,
) -> int:
    async with uow(world.grace.tenant) as tx:
        tx.record(action, target=target, before=before, after=after, scope=scope)
    return await _last_seq(world)


async def _last_seq(world: World) -> int:
    async with tenant_session(world.grace.tenant) as session:
        return int((await session.execute(text("SELECT max(seq) FROM audit_events"))).scalar_one())


async def _values(call: Call, seq: int) -> dict[str, object]:
    response = await call("GET", f"{LIST}/{seq}")
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json()["values"])


def _rows(values: dict[str, object]) -> list[dict[str, object]]:
    assert values["status"] == "resolved", values
    return cast(list[dict[str, object]], values["rows"])


async def _version(seed: Seeder, world: World, engagement: uuid.UUID) -> uuid.UUID:
    item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, '2025 W-2 From Mercer Hill Health', 'human', 'seed') "
        "RETURNING id",
        world.tenant,
        engagement,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
            world.tenant,
            engagement,
            item,
            fingerprint,
            f"tenants/{world.tenant}/sha256/{fingerprint}",
        ),
    )


async def _reveal(seed: Seeder, world: World, version: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    region = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO pii_regions (tenant_id, evidence_version_id, page_no, bbox, kind, "
            "value_sealed, last4, label_anchored, detector_version) VALUES ($1, $2, 1, "
            "ARRAY[1, 1, 2, 2]::numeric[], 'ssn', '\\x00'::bytea, $3, true, 'd2') RETURNING id",
            world.tenant,
            version,
            SSN_LAST4,
        ),
    )
    reveal = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, $4, 'human', "
            "clock_timestamp() + interval '30 seconds') RETURNING id",
            world.tenant,
            region,
            version,
            world.hannah.user_id,
        ),
    )
    return region, reveal


def _no_restricted_in_clear(values: dict[str, object]) -> None:
    for row in _rows(values):
        after = str(row["after"] or "")
        assert SSN_LAST4 not in after or after.startswith("•")


# --- evidence_version and pii_reveal ------------------------------------------------------------


async def test_ac11_a_pii_reveal_answers_its_masked_token_only(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    version = await _version(seed, world, world.copperleaf)
    region, reveal = await _reveal(seed, world, version)
    seq = await _record(
        world,
        "pii.revealed",
        Target("evidence_version", version),
        after=Ref(reveal_id=reveal, region_id=region),
        scope=Scope(engagement_id=world.copperleaf),
    )
    rows = _rows(await _values(as_(world.hannah), seq))
    assert rows == [
        {
            "item_label": "2025 W-2 From Mercer Hill Health",
            "field": "ssn",
            "amount": None,
            "before": None,
            "after": f"•••-••-{SSN_LAST4}",
            "masked": True,
        }
    ]
    # The same reveal as its own target.
    own = await _record(
        world,
        "pii.revealed",
        Target("pii_reveal", reveal),
        scope=Scope(engagement_id=world.copperleaf),
    )
    assert _rows(await _values(as_(world.hannah), own))[0]["after"] == f"•••-••-{SSN_LAST4}"


async def test_an_evidence_event_resolves_its_people_and_fails_closed_elsewhere(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    version = await _version(seed, world, world.copperleaf)
    seq = await _record(
        world,
        "review.taken",
        Target("evidence_version", version),
        after=Ref(user_id=world.hannah.user_id),
        scope=Scope(engagement_id=world.copperleaf),
    )
    rows = _rows(await _values(as_(world.hannah), seq))
    assert [(r["field"], r["after"]) for r in rows] == [("user_id", "Hannah Leclerc")]
    # A version outside the event's engagement: nothing is said about it.
    elsewhere = await _version(seed, world, world.ashford)
    wrong = await _record(
        world,
        "review.taken",
        Target("evidence_version", elsewhere),
        after=Ref(user_id=world.hannah.user_id),
        scope=Scope(engagement_id=world.copperleaf),
    )
    assert (await _values(as_(world.hannah), wrong))["status"] == "unavailable"


# --- request_item -------------------------------------------------------------------------------


async def test_a_request_resolves_visibility_and_assignee_from_its_references(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    item = await seed.item(world.tenant, world.copperleaf, world.grace.user_id)
    await seed.run(
        "UPDATE request_items SET title = 'Fidelity bond declarations page (2025)' WHERE id = $1",
        item,
    )
    shown = await _record(
        world,
        "request_item.visibility_changed",
        Target("request_item", item),
        before=Ref(client_visible=0),
        after=Ref(client_visible=1),
        scope=Scope(engagement_id=world.copperleaf),
    )
    assigned = await _record(
        world,
        "request_item.assignee_changed",
        Target("request_item", item),
        after=Ref(user_id=world.hannah.user_id),
        scope=Scope(engagement_id=world.copperleaf),
    )
    visibility = _rows(await _values(as_(world.hannah), shown))
    assert [(r["item_label"], r["field"], r["before"], r["after"]) for r in visibility] == [
        ("Fidelity bond declarations page (2025)", "client_visible", "false", "true")
    ]
    assignee = _rows(await _values(as_(world.hannah), assigned))
    assert [(r["field"], r["after"]) for r in assignee] == [("client_assignee", "Hannah Leclerc")]
    plain = await _record(
        world,
        "request_item.received",
        Target("request_item", item),
        scope=Scope(engagement_id=world.copperleaf),
    )
    assert (await _values(as_(world.hannah), plain))["status"] == "unavailable"


# --- membership (user targets) ------------------------------------------------------------------


async def test_a_membership_change_resolves_only_while_the_membership_stands_at_its_version(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    await seed.run(
        "UPDATE memberships SET job_title = 'Audit Senior' WHERE id = $1",
        world.hannah.membership_id,
    )
    version = cast(
        int,
        await seed.value(
            "SELECT version FROM memberships WHERE id = $1", world.hannah.membership_id
        ),
    )
    seq = await _record(
        world,
        "membership.attributes_changed",
        Target("user", world.hannah.user_id),
        after=Ref(version=version, title=1),
    )
    rows = _rows(await _values(as_(world.margaret), seq))
    assert [(r["item_label"], r["field"], r["after"]) for r in rows] == [
        ("Hannah Leclerc", "job_title", "Audit Senior")
    ]
    role = await _record(
        world,
        "membership.security_role_changed",
        Target("user", world.hannah.user_id),
        after=Ref(security_admin=1),
    )
    assert [(r["field"], r["after"]) for r in _rows(await _values(as_(world.margaret), role))] == [
        ("security_admin", "true")
    ]
    # Changed since: its current values are no longer the event's.
    await seed.run(
        "UPDATE memberships SET job_title = 'Audit Manager', version = version + 1 WHERE id = $1",
        world.hannah.membership_id,
    )
    assert (await _values(as_(world.margaret), seq))["status"] == "unavailable"


# --- support_session ----------------------------------------------------------------------------


async def test_a_support_session_request_resolves_its_facts(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    session = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO support_sessions (tenant_id, staff_id, staff_subject, reason, scope, "
            "duration_minutes, emergency) VALUES ($1, $2, 'staff-sub', "
            "'Customer reported a failing export on the binder page', 'metadata', 30, false) "
            "RETURNING id",
            world.tenant,
            uuid.uuid4(),
        ),
    )
    seq = await _record(world, "support_session.requested", Target("support_session", session))
    rows = {r["field"]: r["after"] for r in _rows(await _values(as_(world.margaret), seq))}
    assert rows == {
        "scope": "metadata",
        "duration_minutes": "30",
        "emergency": "false",
        "reason": "Customer reported a failing export on the binder page",
    }
    ended = await _record(world, "support_session.ended", Target("support_session", session))
    assert [
        (r["field"], r["after"]) for r in _rows(await _values(as_(world.margaret), ended))
    ] == [("status", "ended")]


# --- need to know and the flag, for every type --------------------------------------------------


async def test_ac5_every_resolver_stays_behind_need_to_know_and_the_flag(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    version = await _version(seed, world, world.copperleaf)
    region, reveal = await _reveal(seed, world, version)
    item = await seed.item(world.tenant, world.copperleaf, world.grace.user_id)
    engagement_events = [
        await _record(
            world,
            "pii.revealed",
            Target("evidence_version", version),
            after=Ref(reveal_id=reveal, region_id=region),
            scope=Scope(engagement_id=world.copperleaf),
        ),
        await _record(
            world,
            "request_item.visibility_changed",
            Target("request_item", item),
            before=Ref(client_visible=0),
            after=Ref(client_visible=1),
            scope=Scope(engagement_id=world.copperleaf),
        ),
    ]
    firm_events = [
        await _record(
            world,
            "membership.security_role_changed",
            Target("user", world.hannah.user_id),
            after=Ref(security_admin=1),
        ),
        await _record(world, "support_session.ended", Target("support_session", uuid.uuid4())),
    ]
    for seq in engagement_events:
        _no_restricted_in_clear(await _values(as_(world.hannah), seq))
    for seq in [*engagement_events, *firm_events]:
        withheld = await _values(as_(world.grace), seq)
        assert (withheld["status"], withheld["reason"], withheld["rows"]) == (
            "withheld",
            "need_to_know",
            [],
        )
    for seq in firm_events:
        # An engagement role never reads a firm-level event at all.
        assert (await as_(world.hannah)("GET", f"{LIST}/{seq}")).status_code == 404
    await _flag(seed, world.tenant, "audit_log.values", "false")
    forget_flags()
    for reader, seqs in ((world.hannah, engagement_events), (world.margaret, firm_events)):
        for seq in seqs:
            off = await _values(as_(reader), seq)
            assert (off["status"], off["reason"], off["rows"]) == ("withheld", "not_enabled", [])
    stored = await seed.rows(
        "SELECT coalesce(after_ref::text, '') AS a FROM audit_events WHERE tenant_id = $1",
        world.tenant,
    )
    assert all(SSN_LAST4 not in cast(str, r["a"]) for r in stored)


# --- Security review M1: unscoped events on engagement content ---------------------------------


async def test_m1_an_unscoped_event_resolves_only_for_a_reader_of_its_targets_engagement(
    world: World, seed: Seeder, as_: Callable[[object], Call]
) -> None:
    # Most writers pass no Scope: the event reads as firm-level, so values.py lets the QM owner
    # through; the resolver must still require the target engagement's content read.
    quinn = await _member(seed, world.tenant, "Quinn Adeyemi", "quality_partner", "partner")
    await seed.member(world.copperleaf, Person(quinn.user_id, world.tenant), "engagement_partner")
    version = await _version(seed, world, world.copperleaf)
    item = await seed.item(world.tenant, world.copperleaf, world.grace.user_id)
    evidence = await _record(
        world,
        "review.taken",
        Target("evidence_version", version),
        after=Ref(user_id=world.hannah.user_id),
    )
    request = await _record(
        world,
        "request_item.assignee_changed",
        Target("request_item", item),
        after=Ref(user_id=world.hannah.user_id),
    )
    for seq in (evidence, request):
        # Margaret, the QM owner off the team: nothing about the engagement's content.
        off_team = await _values(as_(world.margaret), seq)
        assert (off_team["status"], off_team["rows"]) == ("unavailable", [])
        on_team = _rows(await _values(as_(quinn), seq))
        assert [r["after"] for r in on_team] == ["Hannah Leclerc"]
