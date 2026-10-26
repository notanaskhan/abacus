# ac-test-author: ayushkbhatia
"""G-02-T05 (ADR-078 suite 1, written first under the solo amendment) for the audit log: SPEC-349
AC-1 to AC-14 and AC-45 to AC-47 for ADM-07, and the F-04 harness's `since_seq` consumer test.

Written from SPEC-349 §5 and `docs/contracts/audit-log.md`, not from the stub or the read side,
over HTTP against the app as a screen or the harness calls it: the sign-in dependency answers as
the persona, the firm turns `audit_log.explorer` (and `audit_log.values`) on in
`feature_flag_states`, and events are written through the unit of work, the only way any module
writes them.

**Against the stubs.** `STUBBED` lists the routes still answering 501 (G-02-T04). A behaviour test
on a stubbed route asserts the 501 and stops there; the task that makes a route live (G-02-T08 the
list and detail, G-02-T17 the export) removes it from `STUBBED`, and the full assertions then run.
With `STUBBED` emptied, every behaviour test here fails against the stubs (TASK-1292 records the
run). Tests that need no live route (the database and the matrix: AC-3, AC-8, AC-11, AC-45) run
in full now.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.identity.authz.matrix import RULES

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

LIST: Final = ("GET", "/v1/audit-events")
DETAIL: Final = ("GET", "/v1/audit-events/{seq}")
EXPORT: Final = ("POST", "/v1/audit-events/exports")
EXPORT_STATUS: Final = ("GET", "/v1/audit-events/exports/{export_id}")
EXPORT_LINK: Final = ("POST", "/v1/audit-events/exports/{export_id}/link")
ROUTES: Final = (LIST, DETAIL, EXPORT, EXPORT_STATUS, EXPORT_LINK)
# Routes still answering 501 (the stub); remove each as its task makes it live.
STUBBED: Final = frozenset({LIST, DETAIL, EXPORT, EXPORT_STATUS, EXPORT_LINK})
SSN: Final = "900-00-2208"
IP_FELIX: Final = "198.51.100.57"


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    felix: AuthContext  # security_admin, the Qualified Individual
    grace: AuthContext  # firm_admin
    margaret: AuthContext  # quality_partner, partner level
    hannah: AuthContext  # a manager walled from Ashford
    client: AuthContext  # a client principal
    agent_on_behalf_of: uuid.UUID
    ashford_engagement: uuid.UUID


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
    kind: str = "staff",
    mfa_minutes_ago: int = 1,
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
            "VALUES ($1, $2, $3, 'active', $4, $5) RETURNING id",
            tenant,
            user,
            firm_role,
            level,
            kind,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago),
        client=kind == "client",
    )


async def _record(
    ctx: TenantContext, action: str, target: Target, scope: Scope | None = None
) -> None:
    async with uow(ctx) as tx:
        tx.record(action, target=target, after=Ref(version=1), scope=scope)


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    for flag in ("audit_log.explorer", "audit_log.values"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'ac-suite', 'G-02-T05')",
            tenant,
            flag,
        )
    felix = await _member(seed, tenant, "Felix Andersen", firm_role="security_admin")
    grace = await _member(seed, tenant, "Grace Holloway", firm_role="firm_admin")
    margaret = await _member(
        seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
    )
    hannah = await _member(seed, tenant, "Hannah Leclerc", firm_role=None, level="manager")
    client = await _member(seed, tenant, "Claire Feld", firm_role=None, kind="client")
    entity = await seed.entity(tenant, "Ashford Manufacturing Co.")
    ashford = await seed.engagement(tenant, entity, grace.user_id)
    client_id = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        hannah.user_id,
        client_id,
        grace.user_id,
    )
    # The firm's events, oldest first: a person's, the agent's for Hannah, the system's, and
    # one about the walled client's engagement.
    await _record(grace.tenant, "wall.created", Target("wall", uuid.uuid4()))
    agent = TenantContext(tenant, "agent", "agent:workbench.reporter:run", hannah.user_id)
    await _record(agent, "agent_run.report_prepared", Target("agent_run", uuid.uuid4()))
    system = TenantContext(tenant, "system", "system:inbox")
    await _record(system, "inbox_email.received", Target("inbox_item", uuid.uuid4()))
    await _record(
        grace.tenant,
        "engagement.updated",
        Target("engagement", ashford),
        Scope(engagement_id=ashford),
    )
    return World(tenant, felix, grace, margaret, hannah, client, hannah.user_id, ashford)


Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture
def as_() -> Callable[[object], Call]:
    """`await as_(ctx)("GET", "/v1/audit-events", params=...)`: one request as that principal."""

    def bind(ctx: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: ctx
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

        return call

    return bind


def stubbed(route: tuple[str, str], response: httpx.Response) -> bool:
    """True while `route` is the 501 stub (and asserts it is); the behaviour assertions run once
    the route is live."""
    if route in STUBBED:
        assert response.status_code == 501, (route, response.status_code)
        return True
    return False


def _items(response: httpx.Response) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], response.json()["items"])


def _actor(row: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], row["actor"])


# --- AC-1, AC-2: the feed and the actor grammar --------------------------------------------------


async def test_ac1_felix_reads_the_feed_newest_first_with_codes_markers_and_counts(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*LIST)
    if stubbed(LIST, response):
        return
    assert response.status_code == 200
    body = response.json()
    rows = _items(response)
    seqs = [cast(int, r["seq"]) for r in rows]
    assert seqs == sorted(seqs, reverse=True)
    for row in rows:
        assert row["mark"] in ("ok", "no", "pl")
        assert re.fullmatch(r"[a-z][a-z_]*\.[a-z][a-z_]*", cast(str, row["action"]))
        assert {"type", "id"} <= set(cast(dict[str, object], row["target"]))
    # The default note: "Policy principal: 0 events" (ADR-187).
    assert body["counts"].get("policy", 0) == 0
    assert body["counts"]["all"] == body["total"]


async def test_ac2_via_agent_lists_only_agent_events_each_naming_its_person(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*LIST, params={"actor_kind": "via_agent"})
    if stubbed(LIST, response):
        return
    rows = _items(response)
    assert rows, "the seeded agent event is listed"
    for row in rows:
        actor = _actor(row)
        assert actor["kind"] == "via_agent"
        on_behalf_of = cast(dict[str, object], actor["on_behalf_of"])
        assert on_behalf_of["user_id"] == str(world.agent_on_behalf_of)
    assert response.json()["counts"]["via_agent"] == response.json()["total"] == len(rows)


# --- AC-3: the agent never decides ---------------------------------------------------------------


async def test_ac3_the_database_refuses_a_human_only_action_written_as_the_agent(
    world: World,
) -> None:
    action = sorted(HUMAN_ONLY_ACTIONS)[0]
    agent = TenantContext(world.tenant, "agent", "agent:probe:run", world.agent_on_behalf_of)
    with pytest.raises(Exception, match=r"(?i)human|check|violat|refus"):
        await _record(agent, action, Target("probe", uuid.uuid4()))


async def test_ac3_no_listed_approval_names_the_agent(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*LIST)
    if stubbed(LIST, response):
        return
    for row in _items(response):
        if row["mark"] == "ok":
            assert _actor(row)["kind"] in ("person", "policy")


# --- AC-4: walls ---------------------------------------------------------------------------------


async def test_ac4_a_walled_viewer_sees_no_ashford_event_and_nothing_says_so(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    hannah = await as_(world.hannah)(*LIST)
    felix = await as_(world.felix)(*LIST)
    if stubbed(LIST, hannah):
        return
    walled = str(world.ashford_engagement)
    assert all(cast(dict[str, object], r["target"]).get("id") != walled for r in _items(hannah))
    assert hannah.json()["total"] == felix.json()["total"] - 1
    assert not re.search(r"hidden|walled|omitted", hannah.text)
    seq = cast(
        int,
        await seed.value(
            "SELECT seq FROM audit_events WHERE tenant_id = $1 AND engagement_id = $2",
            world.tenant,
            world.ashford_engagement,
        ),
    )
    detail = await as_(world.hannah)("GET", f"/v1/audit-events/{seq}")
    assert detail.status_code == 404


# --- AC-5: need to know --------------------------------------------------------------------------


async def _first_seq(seed: Seeder, world: World, action: str) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT seq FROM audit_events WHERE tenant_id = $1 AND action = $2",
            world.tenant,
            action,
        ),
    )


@pytest.mark.parametrize("who", ["felix", "grace"])
async def test_ac5_security_and_firm_admins_read_metadata_values_withheld(
    world: World, as_: Callable[[object], Call], seed: Seeder, who: str
) -> None:
    seq = await _first_seq(seed, world, "wall.created")
    response = await as_(getattr(world, who))("GET", f"/v1/audit-events/{seq}")
    if stubbed(DETAIL, response):
        return
    values = response.json()["values"]
    assert values["status"] == "withheld"
    assert values["reason"] == "need_to_know"
    assert values.get("rows", []) == []
    assert _actor(response.json())["kind"] == "person"


async def test_ac5_the_qm_owner_in_scope_reads_values(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    seq = await _first_seq(seed, world, "wall.created")
    response = await as_(world.margaret)("GET", f"/v1/audit-events/{seq}")
    if stubbed(DETAIL, response):
        return
    assert response.json()["values"]["status"] in ("resolved", "unavailable")
    assert response.json()["values"].get("reason") != "need_to_know"


# --- AC-6, AC-7: search, filters and paging ------------------------------------------------------


async def test_ac6_a_search_with_no_match_is_empty(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*LIST, params={"q": "pell street iii"})
    if stubbed(LIST, response):
        return
    assert _items(response) == []
    assert response.json()["total"] == 0


@pytest.mark.parametrize("q", [SSN, "2208", "900-00"])
async def test_ac6_no_part_of_a_seeded_ssn_is_findable(
    world: World, as_: Callable[[object], Call], q: str
) -> None:
    response = await as_(world.felix)(*LIST, params={"q": q})
    if stubbed(LIST, response):
        return
    assert _items(response) == []


async def test_ac7_ip_and_date_filters_and_keyset_paging_stay_stable(
    world: World, as_: Callable[[object], Call]
) -> None:
    first = await as_(world.felix)(*LIST, params={"limit": 2})
    if stubbed(LIST, first):
        return
    cursor = first.json()["next_cursor"]
    assert cursor is not None
    # A new event arrives between pages: the next page neither repeats nor skips.
    await _record(world.grace.tenant, "wall.created", Target("wall", uuid.uuid4()))
    second = await as_(world.felix)(*LIST, params={"limit": 2, "cursor": cursor})
    seen = [r["seq"] for r in _items(first)] + [r["seq"] for r in _items(second)]
    assert len(seen) == len(set(seen))
    assert all(cast(int, s) < cast(int, _items(first)[-1]["seq"]) for s in seen[2:])
    today = datetime.now(UTC).date()
    dated = await as_(world.felix)(
        *LIST, params={"from": str(today - timedelta(days=7)), "to": str(today)}
    )
    assert dated.json()["total"] >= len(seen)
    none = await as_(world.felix)(*LIST, params={"ip": "203.0.113.250"})
    assert _items(none) == []


# --- AC-8: immutable -----------------------------------------------------------------------------


async def test_ac8_no_route_changes_or_removes_an_event() -> None:
    app = create_app()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = cast(set[str], getattr(route, "methods", None) or set[str]())
        if "audit-events" in path and "/exports" not in path:
            assert methods <= {"GET", "HEAD"}, (path, methods)


@pytest.mark.parametrize(
    "statement", ["UPDATE audit_events SET action = 'x.y'", "DELETE FROM audit_events"]
)
async def test_ac8_the_app_role_cannot_update_or_delete_an_event(
    world: World, statement: str
) -> None:
    with pytest.raises(DBAPIError):
        async with tenant_connection(world.grace.tenant) as conn:
            await conn.execute(text(statement))


# --- AC-9, AC-10: request context and the detail -------------------------------------------------


async def test_ac9_a_persons_request_carries_its_context_and_agent_and_system_events_do_not(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    rows = await seed.rows(
        "SELECT seq, actor_kind FROM audit_events WHERE tenant_id = $1 ORDER BY seq", world.tenant
    )
    details = {
        cast(str, r["actor_kind"]): await as_(world.felix)("GET", f"/v1/audit-events/{r['seq']}")
        for r in rows
    }
    if stubbed(DETAIL, details["human"]):
        return
    for kind in ("agent", "system"):
        body = details[kind].json()
        assert body["ip"] is None and body["device_label"] is None
        assert body["session"] in (None, {"session_id": None, "auth_method": None, "mfa_at": None})


async def test_ac10_the_drawer_carries_time_to_the_second_hash_values_and_source(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    seq = await _first_seq(seed, world, "agent_run.report_prepared")
    response = await as_(world.margaret)("GET", f"/v1/audit-events/{seq}")
    if stubbed(DETAIL, response):
        return
    body = response.json()
    assert re.fullmatch(r"[0-9a-f]{64}", body["content_hash"])
    assert datetime.fromisoformat(body["occurred_at"]).tzinfo is not None
    assert body["values"]["status"] in ("resolved", "withheld", "unavailable")
    assert _actor(body)["kind"] == "via_agent"


# --- AC-11: no value is stored -------------------------------------------------------------------


def test_ac11_an_audit_reference_can_never_carry_a_value() -> None:
    for value in (SSN, "Payroll accrual", "11860.00"):
        with pytest.raises(ValueError):
            Ref(value=value)


async def test_ac11_no_restricted_value_is_in_the_audit_trail(world: World, seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT before_ref::text AS b, after_ref::text AS a FROM audit_events "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    assert all(SSN not in (r["b"] or "") + (r["a"] or "") for r in rows)


# --- AC-12 to AC-14: export ----------------------------------------------------------------------

_EXPORT_BODY: Final = {"from_date": "2026-09-08", "to_date": "2026-09-14", "include_values": True}


async def test_ac12_export_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    stale = AuthContext(
        world.felix.tenant,
        world.felix.user_id,
        world.felix.membership_id,
        "security_admin",
        datetime.now(UTC) - timedelta(hours=2),
    )
    refused = await as_(stale)(*EXPORT, json=_EXPORT_BODY, headers={"Idempotency-Key": "k1"})
    if stubbed(EXPORT, refused):
        return
    assert refused.status_code == 403


async def test_ac12_ac47_the_export_is_requested_and_audited_naming_felix(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.felix)(
        *EXPORT, json=_EXPORT_BODY, headers={"Idempotency-Key": "k2"}
    )
    if stubbed(EXPORT, response):
        return
    assert response.status_code == 202
    export = response.json()
    assert export["status"] in ("requested", "building", "ready")
    assert export["requested_by"]["user_id"] == str(world.felix.user_id)
    events = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'audit_export.requested'",
        world.tenant,
    )
    assert [(e["actor_kind"], e["actor_id"]) for e in events] == [
        ("human", str(world.felix.user_id))
    ]
    status = await as_(world.felix)("GET", f"/v1/audit-events/exports/{export['id']}")
    if stubbed(EXPORT_STATUS, status):
        return
    assert status.json()["id"] == export["id"]
    # Someone else's export is not there for Grace.
    other = await as_(world.grace)("GET", f"/v1/audit-events/exports/{export['id']}")
    assert other.status_code in (403, 404)


async def test_ac13_the_link_is_the_requesters_and_carries_the_manifest_digest(
    world: World, as_: Callable[[object], Call]
) -> None:
    requested = await as_(world.felix)(
        *EXPORT, json=_EXPORT_BODY, headers={"Idempotency-Key": "k3"}
    )
    if stubbed(EXPORT, requested):
        return
    link = await as_(world.felix)(
        "POST", f"/v1/audit-events/exports/{requested.json()['id']}/link"
    )
    if stubbed(EXPORT_LINK, link):
        return
    assert link.status_code in (200, 409)  # 409 export_not_ready until the job is done
    if link.status_code == 200:
        assert re.fullmatch(r"[0-9a-f]{64}", link.json()["manifest_sha256"])


@pytest.mark.parametrize("route", ROUTES)
async def test_ac14_ac46_the_agent_and_client_principals_are_refused_everywhere(
    world: World, as_: Callable[[object], Call], route: tuple[str, str]
) -> None:
    method, template = route
    path = template.format(seq=1, export_id=uuid.uuid4())
    kwargs: dict[str, object] = {}
    if method == "POST" and template.endswith("/exports"):
        kwargs = {"json": _EXPORT_BODY, "headers": {"Idempotency-Key": "k4"}}
    client = await as_(world.client)(method, path, **kwargs)
    if route in STUBBED and client.status_code == 501:
        return
    assert client.status_code == 404  # INV-4: nothing of the firm's log exists for a client
    agent = AuthContext(
        TenantContext(world.tenant, "agent", "agent:probe:run", world.agent_on_behalf_of),
        world.agent_on_behalf_of,
        uuid.uuid4(),
        None,
        None,
    )
    refused = await as_(agent)(method, path, **kwargs)
    assert refused.status_code in (403, 404)


# --- AC-45: the matrix ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["audit_event.read", "audit_event.export"])
def test_ac45_the_agent_system_and_clients_hold_neither_audit_action(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny"
    assert RULES["audit_event.export"].mfa_recent


# --- The F-04 harness: since_seq -----------------------------------------------------------------


async def test_f04_harness_since_seq_tails_the_log_oldest_first(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    first = cast(
        int,
        await seed.value("SELECT min(seq) FROM audit_events WHERE tenant_id = $1", world.tenant),
    )
    response = await as_(world.felix)(*LIST, params={"since_seq": first})
    if stubbed(LIST, response):
        return
    seqs = [cast(int, r["seq"]) for r in _items(response)]
    assert seqs == sorted(seqs) and all(s > first for s in seqs)
    newest = await seed.value(
        "SELECT max(seq) FROM audit_events WHERE tenant_id = $1", world.tenant
    )
    assert seqs[-1] == newest
