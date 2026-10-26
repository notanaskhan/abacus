"""G-02-T08 and T09 (TASK-1329, TASK-1330): the audit log's live reads against the S9 security
review's bindings (SPEC-349 §4, §7, §9; DEC-420, DEC-434, DEC-435).

- Request context only for firm_admin, security_admin and quality_partner: a manager gets `ip`
  null, and the IP filter finds nothing for them (DEC-420).
- Events with no engagement are firm-level: invisible to engagement roles, list and detail
  (DEC-434), visible to the firm-level readers.
- Walls key on the client derived from the event's engagement, for scoped events and for history
  whose only engagement is its target (security review L4); a walled firm reader sees no
  unplaced history (fail closed).
- Values: withheld for the admins (`need_to_know`), resolved for the QM owner on a firm-level
  event, `not_enabled` with `audit_log.values` off; nothing is stored.
- `events_for_work_item` answers one work item's events as the reader may see them.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel import request_context
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.audit_trail.api import events_for_work_item
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

LIST: Final = "/v1/audit-events"
IP: Final = "198.51.100.57"
Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(
    seed: Seeder,
    tenant: uuid.UUID,
    name: str,
    *,
    firm_role: str | None,
    level: str | None = None,
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


async def _record(
    ctx: TenantContext,
    action: str,
    target: Target,
    scope: Scope | None = None,
    after: Ref | None = None,
) -> None:
    async with uow(ctx) as tx:
        tx.record(action, target=target, after=after or Ref(version=1), scope=scope)


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    felix: AuthContext  # security_admin
    grace: AuthContext  # firm_admin
    margaret: AuthContext  # quality_partner
    hannah: AuthContext  # manager on Copperleaf only
    ivan: AuthContext  # firm_admin walled from Ashford
    ashford: uuid.UUID
    copperleaf: uuid.UUID


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str, value: str) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, $3, 'g02t08', 'G-02-T08') ON CONFLICT (tenant_id, flag) "
        "DO UPDATE SET value = EXCLUDED.value",
        tenant,
        flag,
        value,
    )


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    for flag in ("audit_log.explorer", "audit_log.values"):
        await _flag(seed, tenant, flag, "true")
    felix = await _member(seed, tenant, "Felix Andersen", firm_role="security_admin")
    grace = await _member(seed, tenant, "Grace Holloway", firm_role="firm_admin")
    margaret = await _member(
        seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
    )
    hannah = await _member(seed, tenant, "Hannah Leclerc", firm_role=None, level="manager")
    ivan = await _member(seed, tenant, "Ivan Petrov", firm_role="firm_admin")
    ashford_entity = await seed.entity(tenant, "Ashford Manufacturing Co.")
    ashford = await seed.engagement(tenant, ashford_entity, grace.user_id)
    copperleaf = await seed.engagement(
        tenant, await seed.entity(tenant, "Copperleaf Coffee Roasters, Inc."), grace.user_id
    )
    await seed.member(copperleaf, Person(hannah.user_id, tenant), "manager")
    client = await seed.value(
        "SELECT client_id FROM client_entities WHERE id = $1", ashford_entity
    )
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        ivan.user_id,
        client,
        grace.user_id,
    )
    return World(tenant, felix, grace, margaret, hannah, ivan, ashford, copperleaf)


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


def _items(response: httpx.Response) -> list[dict[str, object]]:
    assert response.status_code == 200, response.text
    return cast(list[dict[str, object]], response.json()["items"])


def _target_ids(response: httpx.Response) -> list[str]:
    return [cast(str, cast(dict[str, object], r["target"])["id"]) for r in _items(response)]


async def _seq(seed: Seeder, world: World, action: str) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT max(seq) FROM audit_events WHERE tenant_id = $1 AND action = $2",
            world.tenant,
            action,
        ),
    )


# --- DEC-420: request context for three roles ---------------------------------------------------


async def test_ac9_dec420_a_manager_gets_ip_null_where_the_security_admin_sees_it(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    context = request_context.RequestContext(
        ip=IP, user_agent_family="Chrome", device_label="Chrome · macOS"
    )
    with request_context.bound(context):
        await _record(
            world.hannah.tenant,
            "engagement.updated",
            Target("engagement", world.copperleaf),
            Scope(engagement_id=world.copperleaf),
        )
    seq = await _seq(seed, world, "engagement.updated")
    felix = {cast(int, r["seq"]): r for r in _items(await as_(world.felix)("GET", LIST))}
    hannah = {cast(int, r["seq"]): r for r in _items(await as_(world.hannah)("GET", LIST))}
    assert felix[seq]["ip"] == IP
    assert hannah[seq]["ip"] is None
    detail = (await as_(world.hannah)("GET", f"{LIST}/{seq}")).json()
    assert detail["ip"] is None
    assert detail["device_label"] is None and detail["user_agent_family"] is None
    assert detail["session"] is None
    shown = (await as_(world.felix)("GET", f"{LIST}/{seq}")).json()
    assert shown["device_label"] == "Chrome · macOS"
    # The IP filter finds nothing for a reader who may not see addresses.
    assert _items(await as_(world.hannah)("GET", LIST, params={"ip": IP})) == []
    by_ip = _items(await as_(world.felix)("GET", LIST, params={"ip": IP}))
    assert [r["seq"] for r in by_ip] == [seq]


# --- DEC-434: firm-level events -----------------------------------------------------------------


async def test_dec434_firm_level_events_are_invisible_to_engagement_roles(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    session = uuid.uuid4()
    await _record(
        world.grace.tenant, "auth_session.signed_out_by_admin", Target("auth_session", session)
    )
    await _record(
        world.grace.tenant,
        "engagement.updated",
        Target("engagement", world.copperleaf),
        Scope(engagement_id=world.copperleaf),
    )
    seq = await _seq(seed, world, "auth_session.signed_out_by_admin")
    hannah = await as_(world.hannah)("GET", LIST)
    assert str(session) not in _target_ids(hannah)
    assert _target_ids(hannah) == [str(world.copperleaf)]
    assert hannah.json()["total"] == 1
    assert (await as_(world.hannah)("GET", f"{LIST}/{seq}")).status_code == 404
    for reader in (world.felix, world.grace, world.margaret):
        assert str(session) in _target_ids(await as_(reader)("GET", LIST))
        assert (await as_(reader)("GET", f"{LIST}/{seq}")).status_code == 200


# --- L4: walls key on the client derived from the engagement ------------------------------------


async def test_l4_walls_key_on_the_client_derived_from_the_engagement(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    # A scoped event, a history event whose only engagement is its target, unplaced history
    # about a record, and a firm-level event.
    await _record(
        world.grace.tenant,
        "engagement.updated",
        Target("engagement", world.ashford),
        Scope(engagement_id=world.ashford),
    )
    await _record(world.grace.tenant, "engagement.renamed", Target("engagement", world.ashford))
    item = uuid.uuid4()
    await _record(world.grace.tenant, "request_item.received", Target("request_item", item))
    await _record(world.grace.tenant, "user.updated", Target("user", world.hannah.user_id))
    ivan = await as_(world.ivan)("GET", LIST)
    assert str(world.ashford) not in _target_ids(ivan)
    assert str(item) not in _target_ids(ivan)  # unplaced history fails closed for a walled reader
    assert str(world.hannah.user_id) in _target_ids(ivan)
    assert ivan.json()["total"] == len(_items(ivan))
    grace = await as_(world.grace)("GET", LIST)
    assert _target_ids(grace).count(str(world.ashford)) == 2
    assert str(item) in _target_ids(grace)
    renamed = await _seq(seed, world, "engagement.renamed")
    assert (await as_(world.ivan)("GET", f"{LIST}/{renamed}")).status_code == 404
    row = next(r for r in _items(grace) if r["seq"] == renamed)
    assert cast(dict[str, object], row["target"])["engagement_id"] == str(world.ashford)


# --- DEC-60, DEC-435: values --------------------------------------------------------------------


async def test_ac5_values_resolve_for_the_qm_owner_and_are_withheld_from_the_admins(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    wall = uuid.uuid4()
    await _record(
        world.grace.tenant,
        "wall.created",
        Target("ethical_wall", wall),
        after=Ref(user_id=world.hannah.user_id, client_id=uuid.uuid4(), reason=1),
    )
    seq = await _seq(seed, world, "wall.created")
    margaret = (await as_(world.margaret)("GET", f"{LIST}/{seq}")).json()
    assert margaret["values"]["status"] == "resolved"
    assert margaret["values"]["rows"][0]["after"] == "Hannah Leclerc"
    assert margaret["detail_facts"]["user_id"] == str(world.hannah.user_id)
    assert margaret["labels"][str(world.hannah.user_id)] == "Hannah Leclerc"
    for admin in (world.felix, world.grace):
        values = (await as_(admin)("GET", f"{LIST}/{seq}")).json()["values"]
        assert values == {
            "status": "withheld",
            "reason": "need_to_know",
            "rows": [],
            "not_included": [],
        }
    await _flag(seed, world.tenant, "audit_log.values", "false")
    forget_flags()  # flags are cached per process for 30 seconds
    off = (await as_(world.margaret)("GET", f"{LIST}/{seq}")).json()["values"]
    assert (off["status"], off["reason"]) == ("withheld", "not_enabled")
    stored = await seed.rows(
        "SELECT after_ref::text AS a FROM audit_events WHERE tenant_id = $1 AND seq = $2",
        world.tenant,
        seq,
    )
    assert "Hannah" not in cast(str, stored[0]["a"])


async def test_ac10_content_hash_is_the_events_leaf(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    await _record(world.grace.tenant, "user.updated", Target("user", world.hannah.user_id))
    seq = await _seq(seed, world, "user.updated")
    first = (await as_(world.felix)("GET", f"{LIST}/{seq}")).json()["content_hash"]
    again = (await as_(world.grace)("GET", f"{LIST}/{seq}")).json()["content_hash"]
    assert first == again and len(first) == 64


# --- A-01's read -------------------------------------------------------------------------------


async def test_events_for_work_item_answers_the_readers_view(world: World) -> None:
    work_item = uuid.uuid4()
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", uuid.uuid4()),
        Scope(engagement_id=world.copperleaf, work_item_id=work_item),
    )
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", uuid.uuid4()),
        Scope(engagement_id=world.ashford, work_item_id=work_item),
    )
    hannah = await events_for_work_item(world.hannah, work_item)
    assert [r.target.engagement_id for r in hannah] == [world.copperleaf]
    grace = await events_for_work_item(world.grace, work_item)
    assert len(grace) == 2
    assert [r.seq for r in grace] == sorted(r.seq for r in grace)


# --- Security review M1: firm-level events that name a walled client -----------------------------


async def test_m1_a_walled_admin_never_sees_a_hold_on_the_walled_client(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    def client_of(engagement: uuid.UUID) -> Awaitable[object]:
        return seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)

    ashford_client = cast(uuid.UUID, await client_of(world.ashford))
    copperleaf_client = cast(uuid.UUID, await client_of(world.copperleaf))
    walled_hold, open_hold, link = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant,
        "legal_hold.placed",
        Target("legal_hold", walled_hold),
        after=Ref(client_id=ashford_client),
    )
    await _record(
        world.grace.tenant,
        "legal_hold.placed",
        Target("legal_hold", open_hold),
        after=Ref(client_id=copperleaf_client),
    )
    # A contact names a client the explorer cannot place: hidden from a walled reader.
    await _record(
        world.grace.tenant,
        "secure_link.issued",
        Target("secure_link", link),
        after=Ref(contact_id=uuid.uuid4()),
    )
    ivan = await as_(world.ivan)("GET", LIST)
    assert str(walled_hold) not in _target_ids(ivan)
    assert str(link) not in _target_ids(ivan)
    assert str(open_hold) in _target_ids(ivan)
    assert str(ashford_client) not in ivan.text
    assert ivan.json()["total"] == len(_items(ivan)) == ivan.json()["counts"]["all"]
    grace = await as_(world.grace)("GET", LIST)
    assert {str(walled_hold), str(open_hold), str(link)} <= set(_target_ids(grace))
    walled_seq = cast(
        int,
        await seed.value(
            "SELECT seq FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
            world.tenant,
            str(walled_hold),
        ),
    )
    assert (await as_(world.ivan)("GET", f"{LIST}/{walled_seq}")).status_code == 404
    searched = await as_(world.ivan)("GET", LIST, params={"q": "legal hold placed"})
    assert _target_ids(searched) == [str(open_hold)]
    assert searched.json()["total"] == 1
    by_grace = await as_(world.grace)("GET", LIST, params={"q": "legal hold placed"})
    assert set(_target_ids(by_grace)) == {str(walled_hold), str(open_hold)}


# --- Security review L7: an IPv6 zone is refused, never a 500 -----------------------------------


async def test_l7_an_ipv6_zone_in_the_ip_filter_answers_422(
    world: World, as_: Callable[[object], Call]
) -> None:
    refused = await as_(world.felix)("GET", LIST, params={"ip": "fe80::1%eth0"})
    assert refused.status_code == 422
    plain = await as_(world.felix)("GET", LIST, params={"ip": "fe80::1"})
    assert plain.status_code == 200


# --- Re-review 2: client-side targets and references, each side on its own ----------------------


async def test_m1_client_side_targets_and_refs_are_hidden_from_a_walled_reader(
    world: World, as_: Callable[[object], Call]
) -> None:
    draft, link = uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant, "engagement_draft.started", Target("engagement_draft", draft)
    )
    await _record(world.grace.tenant, "secure_link.revoked", Target("secure_link", link))
    # A conflict check names a client-side record: `check_id` is not firm-safe.
    checked = uuid.uuid4()
    await _record(
        world.grace.tenant,
        "user.updated",
        Target("user", checked),
        after=Ref(check_id=uuid.uuid4()),
    )
    # A before-side id must not be hidden by an after-side value under the same key.
    masked = uuid.uuid4()
    async with uow(world.grace.tenant) as tx:
        tx.record(
            "user.updated",
            target=Target("user", masked),
            before=Ref(contact_id=uuid.uuid4()),
            after=Ref(contact_id=1),
        )
    ivan = _target_ids(await as_(world.ivan)("GET", LIST))
    for hidden in (draft, link, checked, masked):
        assert str(hidden) not in ivan
    grace = _target_ids(await as_(world.grace)("GET", LIST))
    for shown in (draft, link, checked, masked):
        assert str(shown) in grace
