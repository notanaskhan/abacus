"""AC-4 to AC-8: engagements and request items over HTTP against a real Postgres (TASK-008
interface contract, "HTTP" and "AC-5").

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test, so tests
never need cleanup. HTTP goes through `httpx.ASGITransport(app=create_app())` with tokens from
`FakeIdentityProvider`. Expectations come from the contract, not from the implementation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

import asyncpg
import httpx
import pytest
from sqlalchemy import text

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.modules.engagements.repository import get_engagement, list_engagements
from abacus.modules.identity.api import AuthContext, configure_verifier, reset_verifier
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

Json = dict[str, object]
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
DISTINCT_INPUT = "ZX-DISTINCTIVE-9137-input"
PERIOD = {"fiscal_period_start": "2025-01-01", "fiscal_period_end": "2025-12-31"}
CREATE_ITEM = {"description": "Bank confirmations", "audit_area": "Cash"}
ENGAGEMENT_KEYS = {
    "id",
    "name",
    "type",
    "status",
    "client_name",
    "client_entity_name",
    "fiscal_period_start",
    "fiscal_period_end",
    "created_at",
    "team",
}
ITEM_KEYS = {
    "id",
    "engagement_id",
    "description",
    "audit_area",
    "status",
    "created_at",
    "evidence_version_id",
    "retrievability_tier",  # SPEC-008
    "client_visible",  # SPEC-020
    "client_assignee_user_id",
}
ALL_ROLES = ["engagement_partner", "manager", "senior", "staff", "reviewer"]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    identity_url: str
    superuser_dsn: str


# --- seeding (superuser) -------------------------------------------------------------------------

COUNT_SQL = {
    "clients": "SELECT count(*) FROM clients WHERE tenant_id = $1",
    "client_entities": "SELECT count(*) FROM client_entities WHERE tenant_id = $1",
    "engagements": "SELECT count(*) FROM engagements WHERE tenant_id = $1",
    "engagement_members": "SELECT count(*) FROM engagement_members WHERE tenant_id = $1",
    "request_lists": "SELECT count(*) FROM request_lists WHERE tenant_id = $1",
    "request_items": "SELECT count(*) FROM request_items WHERE tenant_id = $1",
    "audit_events": "SELECT count(*) FROM audit_events WHERE tenant_id = $1",
    "outbox": "SELECT count(*) FROM outbox WHERE tenant_id = $1",
}


class Seeder:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def engagement(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID, name: str | None = None
    ) -> uuid.UUID:
        client_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                tenant_id,
                "Seeded client",
            ),
        )
        entity_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                tenant_id,
                client_id,
                "Seeded entity",
            ),
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
                tenant_id,
                client_id,
                entity_id,
                name or f"Seeded {uuid.uuid4().hex[:6]}",
                created_by,
            ),
        )

    async def counts(self, tenant_id: uuid.UUID) -> dict[str, int]:
        return {
            table: cast(int, await self.value(sql, tenant_id)) for table, sql in COUNT_SQL.items()
        }


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    subject: str
    tenant_id: uuid.UUID
    display_name: str


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    seed: Seeder

    async def person(self, firm_role: str | None = None) -> Person:
        subject = f"sub-{uuid.uuid4().hex}"
        display_name = f"Person {uuid.uuid4().hex[:8]}"
        user_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
                display_name,
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, $3, 'active')",
            self.tenant_id,
            user_id,
            firm_role,
        )
        return Person(user_id, subject, self.tenant_id, display_name)

    async def member(self, engagement_id: uuid.UUID, role: str) -> Person:
        who = await self.person(None)
        await self.add_member(engagement_id, who, role)
        return who

    async def add_member(self, engagement_id: uuid.UUID, who: Person, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant_id,
            engagement_id,
            who.user_id,
            role,
        )


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return Firm(await seed.firm(), seed)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Each test has its own event loop: rebuild the engines for it, from the test database."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def client(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def lenient_client(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    """Server errors come back as a 500 response instead of raising in the test."""
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


# --- helpers -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Api:
    http: httpx.AsyncClient
    idp: FakeIdentityProvider

    def _headers(self, who: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.idp.token(who.subject)}"}

    async def post_engagement(self, who: Person, body: Json) -> httpx.Response:
        return await self.http.post("/v1/engagements", json=body, headers=self._headers(who))

    async def create(self, who: Person, **overrides: object) -> httpx.Response:
        body: Json = {
            "name": f"Audit {uuid.uuid4().hex[:6]}",
            "client_name": "Acme Corp",
            "client_entity_name": "Acme Holdings LLC",
            **PERIOD,
        }
        body.update(overrides)
        return await self.post_engagement(who, body)

    async def create_ok(self, who: Person, **overrides: object) -> Json:
        response = await self.create(who, **overrides)
        assert response.status_code == 201, response.text
        return cast(Json, response.json())

    async def list(self, who: Person) -> httpx.Response:
        return await self.http.get("/v1/engagements", headers=self._headers(who))

    async def get(self, who: Person, engagement_id: object) -> httpx.Response:
        return await self.http.get(f"/v1/engagements/{engagement_id}", headers=self._headers(who))

    async def add_item(
        self, who: Person, engagement_id: object, body: Json | None = None
    ) -> httpx.Response:
        return await self.http.post(
            f"/v1/engagements/{engagement_id}/request-items",
            json=body if body is not None else CREATE_ITEM,
            headers=self._headers(who),
        )

    async def items(self, who: Person, engagement_id: object) -> httpx.Response:
        return await self.http.get(
            f"/v1/engagements/{engagement_id}/request-items", headers=self._headers(who)
        )


@pytest.fixture
def api(client: httpx.AsyncClient, idp: FakeIdentityProvider) -> Api:
    return Api(client, idp)


def _assert_forbidden(response: httpx.Response) -> None:
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}
    assert "WWW-Authenticate" not in response.headers


def _assert_not_found(response: httpx.Response) -> None:
    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}


def _ids(response: httpx.Response) -> list[str]:
    assert response.status_code == 200, response.text
    return [cast(str, row["id"]) for row in cast(list[Json], response.json())]


def _assert_validation_error(response: httpx.Response) -> None:
    assert response.status_code == 422
    assert DISTINCT_INPUT not in response.text
    detail = cast(list[Json], response.json()["detail"])
    assert detail
    for problem in detail:
        assert set(problem) <= {"loc", "msg", "type"}
        assert {"loc", "msg", "type"} <= set(problem)
        assert "input" not in problem
        assert "ctx" not in problem
    assert '"input"' not in response.text
    assert '"ctx"' not in response.text


async def _audit(seed: Seeder, tenant_id: uuid.UUID) -> list[asyncpg.Record]:
    return await seed.rows(
        "SELECT action, actor_kind, actor_id, target_type, target_id FROM audit_events "
        "WHERE tenant_id = $1 ORDER BY seq",
        tenant_id,
    )


async def _outbox(seed: Seeder, tenant_id: uuid.UUID, event_type: str) -> list[Json]:
    rows = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY seq",
        tenant_id,
        event_type,
    )
    return [cast(Json, json.loads(cast(str, row["payload"]))) for row in rows]


EMPTY = dict.fromkeys(COUNT_SQL, 0)


# --- AC-4: create an engagement ------------------------------------------------------------------


@pytest.mark.parametrize("firm_role", ["firm_admin", "practice_leader"])
async def test_ac4_firm_admin_and_practice_leader_create_an_engagement(
    api: Api, firm: Firm, firm_role: str
) -> None:
    who = await firm.person(firm_role)
    response = await api.create(
        who,
        name="FY2025 audit",
        client_name="Acme Corp",
        client_entity_name="Acme Holdings LLC",
    )
    assert response.status_code == 201
    body = cast(Json, response.json())
    assert set(body) == ENGAGEMENT_KEYS
    assert uuid.UUID(cast(str, body["id"]))
    assert body["name"] == "FY2025 audit"
    assert body["type"] == "audit"
    assert body["status"] == "active"
    assert body["client_name"] == "Acme Corp"
    assert body["client_entity_name"] == "Acme Holdings LLC"
    assert body["fiscal_period_start"] == "2025-01-01"
    assert body["fiscal_period_end"] == "2025-12-31"
    assert datetime.fromisoformat(cast(str, body["created_at"])).tzinfo is not None
    assert body["team"] == [
        {
            "user_id": str(who.user_id),
            "display_name": who.display_name,
            "role": "engagement_partner",
        }
    ]


async def test_ac4_one_transaction_writes_the_rows_audit_events_and_outbox_event(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    who = await firm.person("firm_admin")
    body = await api.create_ok(who)
    engagement_id = uuid.UUID(cast(str, body["id"]))

    engagements = await seed.rows(
        "SELECT tenant_id, created_by, client_id, client_entity_id, name FROM engagements "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    [engagement] = engagements
    assert engagement["tenant_id"] == firm.tenant_id
    assert engagement["created_by"] == who.user_id
    clients = await seed.rows("SELECT id, name FROM clients WHERE tenant_id = $1", firm.tenant_id)
    [client_row] = clients
    assert client_row["id"] == engagement["client_id"]
    assert client_row["name"] == "Acme Corp"
    entities = await seed.rows(
        "SELECT id, client_id, name FROM client_entities WHERE tenant_id = $1", firm.tenant_id
    )
    [entity] = entities
    assert entity["id"] == engagement["client_entity_id"]
    assert entity["client_id"] == client_row["id"]
    assert entity["name"] == "Acme Holdings LLC"
    members = await seed.rows(
        "SELECT engagement_id, user_id, role FROM engagement_members WHERE tenant_id = $1",
        firm.tenant_id,
    )
    [member] = members
    assert (member["engagement_id"], member["user_id"], member["role"]) == (
        engagement_id,
        who.user_id,
        "engagement_partner",
    )

    audit = await _audit(seed, firm.tenant_id)
    assert sorted(row["action"] for row in audit) == [
        "client.created",
        "client_entity.created",
        "engagement.created",
        "engagement_member.added",
    ]
    for row in audit:
        assert row["actor_kind"] == "human"
        assert row["actor_id"] == str(who.user_id)

    payloads = await _outbox(seed, firm.tenant_id, "engagement.created")
    [payload] = payloads
    assert payload["engagement_id"] == str(engagement_id)
    assert (await seed.counts(firm.tenant_id))["outbox"] == 1


@pytest.mark.parametrize(
    "failing_statement",
    [
        pytest.param(
            "ALTER TABLE engagement_members ADD CONSTRAINT zz_ac4_fail CHECK (false) NOT VALID",
            id="member-insert-fails",
        ),
        pytest.param(
            "ALTER TABLE audit_events ADD CONSTRAINT zz_ac4_fail "
            "CHECK (action <> 'engagement_member.added') NOT VALID",
            id="audit-insert-fails",
        ),
        pytest.param(
            "ALTER TABLE outbox ADD CONSTRAINT zz_ac4_fail "
            "CHECK (event_type <> 'engagement.created') NOT VALID",
            id="outbox-insert-fails",
        ),
        pytest.param(
            "ALTER TABLE engagements ADD CONSTRAINT zz_ac4_fail CHECK (false) NOT VALID",
            id="engagement-insert-fails",
        ),
    ],
)
async def test_ac4_none_of_it_happens_when_any_step_fails(
    lenient_client: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    firm: Firm,
    seed: Seeder,
    failing_statement: str,
) -> None:
    api = Api(lenient_client, idp)
    who = await firm.person("firm_admin")
    table = failing_statement.split()[2]
    await seed.run(failing_statement)
    try:
        response = await api.create(who)
    finally:
        await seed.run(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS zz_ac4_fail")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    assert await seed.counts(firm.tenant_id) == EMPTY
    # With the failure removed, the same caller can create it: nothing was half-done.
    await api.create_ok(who)
    after = await seed.counts(firm.tenant_id)
    assert (after["engagements"], after["clients"], after["client_entities"]) == (1, 1, 1)
    assert after["engagement_members"] == 1
    assert after["audit_events"] == 4
    assert after["outbox"] == 1


@pytest.mark.parametrize("firm_role", ["quality_partner", None])
async def test_ac4_other_firm_roles_get_403_and_nothing_is_written(
    api: Api, firm: Firm, seed: Seeder, firm_role: str | None
) -> None:
    who = await firm.person(firm_role)
    _assert_forbidden(await api.create(who))
    assert await seed.counts(firm.tenant_id) == EMPTY


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac4_an_engagement_member_without_a_firm_role_cannot_create(
    api: Api, firm: Firm, seed: Seeder, role: str
) -> None:
    owner = await firm.person("firm_admin")
    engagement_id = await seed.engagement(firm.tenant_id, owner.user_id)
    who = await firm.member(engagement_id, role)
    before = await seed.counts(firm.tenant_id)
    _assert_forbidden(await api.create(who))
    assert await seed.counts(firm.tenant_id) == before


async def test_ac4_names_are_trimmed(api: Api, firm: Firm) -> None:
    who = await firm.person("firm_admin")
    body = await api.create_ok(
        who, name="  Padded  ", client_name="\tClient\n", client_entity_name=" Entity "
    )
    assert body["name"] == "Padded"
    assert body["client_name"] == "Client"
    assert body["client_entity_name"] == "Entity"


@pytest.mark.parametrize("field", ["name", "client_name", "client_entity_name"])
async def test_ac4_names_of_exactly_200_characters_are_accepted(
    api: Api, firm: Firm, field: str
) -> None:
    who = await firm.person("firm_admin")
    body = await api.create_ok(who, **{field: "x" * 200})
    assert body[field] == "x" * 200


@pytest.mark.parametrize("field", ["name", "client_name", "client_entity_name"])
@pytest.mark.parametrize("value", ["", "   ", "x" * 201, f" {'x' * 201} "])
async def test_ac4_names_outside_1_to_200_characters_are_422_and_write_nothing(
    api: Api, firm: Firm, seed: Seeder, field: str, value: str
) -> None:
    who = await firm.person("firm_admin")
    response = await api.create(who, **{field: value})
    _assert_validation_error(response)
    assert await seed.counts(firm.tenant_id) == EMPTY


@pytest.mark.parametrize(
    "period",
    [
        {"fiscal_period_start": "2025-12-31", "fiscal_period_end": "2025-01-01"},
        {"fiscal_period_start": "2025-06-30", "fiscal_period_end": "2025-06-30"},
    ],
)
async def test_ac4_end_must_be_after_start(
    api: Api, firm: Firm, seed: Seeder, period: dict[str, str]
) -> None:
    who = await firm.person("firm_admin")
    _assert_validation_error(await api.create(who, **period))
    assert await seed.counts(firm.tenant_id) == EMPTY


@pytest.mark.parametrize("bad", ["not-a-date", "2025-13-01", "", 20250101, None])
@pytest.mark.parametrize("field", ["fiscal_period_start", "fiscal_period_end"])
async def test_ac4_dates_must_be_iso_dates(
    api: Api, firm: Firm, seed: Seeder, field: str, bad: object
) -> None:
    who = await firm.person("firm_admin")
    _assert_validation_error(await api.create(who, **{field: bad}))
    assert await seed.counts(firm.tenant_id) == EMPTY


async def test_ac4_unknown_fields_are_rejected(api: Api, firm: Firm, seed: Seeder) -> None:
    who = await firm.person("firm_admin")
    _assert_validation_error(await api.create(who, status="archived", extra=DISTINCT_INPUT))
    assert await seed.counts(firm.tenant_id) == EMPTY


@pytest.mark.parametrize("field", ["name", "client_name", "client_entity_name"])
async def test_ac4_a_missing_field_is_422(api: Api, firm: Firm, field: str) -> None:
    who = await firm.person("firm_admin")
    body: Json = {
        "name": "n",
        "client_name": "c",
        "client_entity_name": "e",
        **PERIOD,
    }
    del body[field]
    _assert_validation_error(await api.post_engagement(who, body))


async def test_ac4_validation_errors_never_echo_the_submitted_input(api: Api, firm: Firm) -> None:
    who = await firm.person("firm_admin")
    for response in (
        await api.create(who, name=DISTINCT_INPUT * 100),
        await api.create(who, fiscal_period_start=DISTINCT_INPUT),
        await api.create(who, client_name={"nested": DISTINCT_INPUT}),
        await api.create(who, client_entity_name=[DISTINCT_INPUT]),
        await api.create(who, **{DISTINCT_INPUT[:5]: DISTINCT_INPUT}),
    ):
        _assert_validation_error(response)


async def test_ac4_creator_sees_the_engagement_in_the_list_and_can_get_it(
    api: Api, firm: Firm
) -> None:
    who = await firm.person("firm_admin")
    body = await api.create_ok(who)
    assert _ids(await api.list(who)) == [body["id"]]
    fetched = await api.get(who, body["id"])
    assert fetched.status_code == 200
    assert cast(Json, fetched.json())["team"] == body["team"]


# --- AC-5: list and get respect firm boundaries; 404 vs 403 --------------------------------------


async def test_ac5_list_is_newest_first(api: Api, firm: Firm) -> None:
    who = await firm.person("firm_admin")
    created = [cast(str, (await api.create_ok(who))["id"]) for _ in range(3)]
    assert _ids(await api.list(who)) == list(reversed(created))


async def test_ac5_list_rows_are_summaries_without_team(api: Api, firm: Firm) -> None:
    who = await firm.person("firm_admin")
    created = await api.create_ok(who)
    [row] = cast(list[Json], (await api.list(who)).json())
    assert set(row) == ENGAGEMENT_KEYS - {"team"}
    assert row == {key: value for key, value in created.items() if key != "team"}


async def test_ac5_get_returns_metadata_and_team(api: Api, firm: Firm, seed: Seeder) -> None:
    admin = await firm.person("firm_admin")
    created = await api.create_ok(admin)
    engagement_id = uuid.UUID(cast(str, created["id"]))
    manager = await firm.member(engagement_id, "manager")
    reviewer = await firm.member(engagement_id, "reviewer")
    response = await api.get(manager, engagement_id)
    assert response.status_code == 200
    body = cast(Json, response.json())
    assert set(body) == ENGAGEMENT_KEYS
    team = {cast(str, m["user_id"]): m for m in cast(list[dict[str, object]], body["team"])}
    assert set(team) == {str(admin.user_id), str(manager.user_id), str(reviewer.user_id)}
    assert team[str(admin.user_id)]["role"] == "engagement_partner"
    assert team[str(manager.user_id)]["role"] == "manager"
    assert team[str(manager.user_id)]["display_name"] == manager.display_name
    assert team[str(reviewer.user_id)]["role"] == "reviewer"


async def test_ac5_get_of_an_engagement_that_does_not_exist_is_404(api: Api, firm: Firm) -> None:
    who = await firm.person("firm_admin")
    _assert_not_found(await api.get(who, uuid.uuid4()))


async def test_ac5_get_of_another_firms_engagement_is_404(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    other = Firm(await seed.firm(), seed)
    other_admin = await other.person("firm_admin")
    theirs = await api.create_ok(other_admin)
    mine = await firm.person("firm_admin")
    _assert_not_found(await api.get(mine, theirs["id"]))


async def test_ac5_missing_and_other_firm_ids_are_indistinguishable(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    other = Firm(await seed.firm(), seed)
    theirs = await api.create_ok(await other.person("firm_admin"))
    mine = await firm.person("firm_admin")
    calls: list[Callable[[object], Awaitable[httpx.Response]]] = [
        lambda e: api.get(mine, e),
        lambda e: api.items(mine, e),
        lambda e: api.add_item(mine, e),
    ]
    for call in calls:
        missing = await call(uuid.uuid4())
        foreign = await call(theirs["id"])
        assert (missing.status_code, missing.content) == (foreign.status_code, foreign.content)
        assert missing.headers.get("content-length") == foreign.headers.get("content-length")
        _assert_not_found(foreign)


async def test_ac5_same_firm_without_an_allowing_role_is_403_not_404(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    created = await api.create_ok(admin)
    nobody = await firm.person(None)
    _assert_forbidden(await api.get(nobody, created["id"]))


async def test_ac5_a_non_member_with_no_firm_role_sees_nothing_in_the_list(
    api: Api, firm: Firm
) -> None:
    admin = await firm.person("firm_admin")
    await api.create_ok(admin)
    nobody = await firm.person(None)
    assert _ids(await api.list(nobody)) == []


async def test_ac5_the_api_never_shows_another_firms_rows(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    a = firm
    b = Firm(await seed.firm(), seed)
    a_admin = await a.person("firm_admin")
    engagement = await api.create_ok(a_admin)
    assert (await api.add_item(a_admin, engagement["id"])).status_code == 201
    b_admin = await b.person("firm_admin")
    b_engagement = await api.create_ok(b_admin)

    assert _ids(await api.list(b_admin)) == [b_engagement["id"]]
    assert _ids(await api.list(a_admin)) == [engagement["id"]]
    _assert_not_found(await api.get(b_admin, engagement["id"]))
    _assert_not_found(await api.items(b_admin, engagement["id"]))
    _assert_not_found(await api.add_item(b_admin, engagement["id"]))
    assert (await seed.counts(a.tenant_id))["request_items"] == 1


@pytest.mark.parametrize("firm_role", ["firm_admin", "quality_partner", "practice_leader", None])
async def test_ac5_every_role_in_another_firm_gets_404(
    api: Api, firm: Firm, seed: Seeder, firm_role: str | None
) -> None:
    theirs = await api.create_ok(await firm.person("firm_admin"))
    other = Firm(await seed.firm(), seed)
    stranger = await other.person(firm_role)
    _assert_not_found(await api.get(stranger, theirs["id"]))
    assert _ids(await api.list(stranger)) == []


def _auth_context(who: Person, firm_role: FirmRole | None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,
        mfa_at=datetime.now(UTC),
    )


async def test_ac5_the_repository_never_returns_another_firms_engagement(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    a_admin = await firm.person("firm_admin")
    engagement = await api.create_ok(a_admin)
    engagement_id = uuid.UUID(cast(str, engagement["id"]))
    b = Firm(await seed.firm(), seed)
    b_admin = await b.person("firm_admin")
    b_ctx = _auth_context(b_admin, "firm_admin")
    a_ctx = _auth_context(a_admin, "firm_admin")

    async with tenant_session(a_ctx.tenant) as session:  # control: the owner firm sees it
        assert [e.id for e in await list_engagements(session, a_ctx)] == [engagement_id]
        found = await get_engagement(session, engagement_id)
        assert found is not None
    async with tenant_session(b_ctx.tenant) as session:
        assert list(await list_engagements(session, b_ctx)) == []
        assert await get_engagement(session, engagement_id) is None


async def test_ac5_a_direct_select_as_firm_b_never_returns_firm_a_rows(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    a_admin = await firm.person("firm_admin")
    engagement = await api.create_ok(a_admin)
    engagement_id = uuid.UUID(cast(str, engagement["id"]))
    item = cast(Json, (await api.add_item(a_admin, engagement_id)).json())
    b = Firm(await seed.firm(), seed)
    b_admin = await b.person("firm_admin")
    a_ctx = TenantContext(firm.tenant_id, "human", str(a_admin.user_id))
    b_ctx = TenantContext(b.tenant_id, "human", str(b_admin.user_id))

    async with tenant_session(a_ctx) as session:  # control: the query shape finds A's rows as A
        for statement, key in (
            ("SELECT id FROM engagements WHERE id = :v", engagement_id),
            ("SELECT id FROM request_items WHERE id = :v", uuid.UUID(cast(str, item["id"]))),
        ):
            assert (await session.execute(text(statement), {"v": key})).scalars().all() == [key]
    async with tenant_session(b_ctx) as session:
        for statement, key in (
            ("SELECT id FROM engagements WHERE id = :v", engagement_id),
            ("SELECT id FROM request_items WHERE id = :v", uuid.UUID(cast(str, item["id"]))),
            ("SELECT id FROM engagements", None),
            ("SELECT id FROM request_items", None),
            ("SELECT id FROM request_lists", None),
            ("SELECT id FROM clients", None),
            ("SELECT id FROM client_entities", None),
        ):
            params = {} if key is None else {"v": key}
            assert (await session.execute(text(statement), params)).scalars().all() == []


# --- AC-6: list visibility per role; metadata 200, content 403 -----------------------------------


async def test_ac6_firm_admin_and_quality_partner_see_every_engagement_in_the_firm(
    api: Api, firm: Firm
) -> None:
    admin = await firm.person("firm_admin")
    leader = await firm.person("practice_leader")
    created = [
        cast(str, (await api.create_ok(admin))["id"]),
        cast(str, (await api.create_ok(leader))["id"]),
    ]
    expected = list(reversed(created))
    quality = await firm.person("quality_partner")
    assert _ids(await api.list(admin)) == expected
    assert _ids(await api.list(quality)) == expected


async def test_ac6_others_see_only_the_engagements_they_are_members_of(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    first = await api.create_ok(admin)
    second = await api.create_ok(admin)
    third = await api.create_ok(admin)
    who = await firm.person(None)
    await firm.add_member(uuid.UUID(cast(str, first["id"])), who, "staff")
    await firm.add_member(uuid.UUID(cast(str, third["id"])), who, "reviewer")
    assert _ids(await api.list(who)) == [third["id"], first["id"]]
    assert second["id"] not in _ids(await api.list(who))


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac6_a_member_in_any_engagement_role_sees_the_engagement_and_can_get_it(
    api: Api, firm: Firm, role: str
) -> None:
    admin = await firm.person("firm_admin")
    created = await api.create_ok(admin)
    who = await firm.member(uuid.UUID(cast(str, created["id"])), role)
    assert _ids(await api.list(who)) == [created["id"]]
    assert (await api.get(who, created["id"])).status_code == 200


async def test_ac6_a_firm_admin_who_is_not_a_member_gets_metadata_but_not_content(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    creator = await firm.person("firm_admin")
    engagement = await api.create_ok(creator)
    assert (await api.add_item(creator, engagement["id"])).status_code == 201
    other_admin = await firm.person("firm_admin")

    assert engagement["id"] in _ids(await api.list(other_admin))
    metadata = await api.get(other_admin, engagement["id"])
    assert metadata.status_code == 200
    _assert_forbidden(await api.items(other_admin, engagement["id"]))
    _assert_forbidden(await api.add_item(other_admin, engagement["id"]))
    assert (await seed.counts(firm.tenant_id))["request_items"] == 1


async def test_ac6_a_quality_partner_who_is_not_a_member_gets_metadata(
    api: Api, firm: Firm
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    quality = await firm.person("quality_partner")
    assert (await api.get(quality, engagement["id"])).status_code == 200


async def test_ac6_the_team_in_get_is_visible_to_a_non_member_admin(api: Api, firm: Firm) -> None:
    creator = await firm.person("firm_admin")
    engagement = await api.create_ok(creator)
    other_admin = await firm.person("firm_admin")
    body = cast(Json, (await api.get(other_admin, engagement["id"])).json())
    assert [m["user_id"] for m in cast(list[Json], body["team"])] == [str(creator.user_id)]


# --- AC-7: create request items ------------------------------------------------------------------


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior"])
async def test_ac7_partner_manager_and_senior_create_request_items(
    api: Api, firm: Firm, seed: Seeder, role: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    engagement_id = uuid.UUID(cast(str, engagement["id"]))
    who = await firm.member(engagement_id, role)
    response = await api.add_item(
        who, engagement_id, {"description": "Aged AR", "audit_area": "AR"}
    )
    assert response.status_code == 201
    body = cast(Json, response.json())
    assert set(body) == ITEM_KEYS
    assert uuid.UUID(cast(str, body["id"]))
    assert body["engagement_id"] == str(engagement_id)
    assert body["description"] == "Aged AR"
    assert body["audit_area"] == "AR"
    assert body["status"] == "open"
    assert body["evidence_version_id"] is None
    assert datetime.fromisoformat(cast(str, body["created_at"])).tzinfo is not None

    rows = await seed.rows(
        "SELECT id, engagement_id, status, created_by FROM request_items WHERE tenant_id = $1",
        firm.tenant_id,
    )
    [row] = rows
    assert str(row["id"]) == body["id"]
    assert row["engagement_id"] == engagement_id
    assert row["status"] == "open"
    assert row["created_by"] == who.user_id


async def test_ac7_the_creator_is_an_engagement_partner_and_can_add_items(
    api: Api, firm: Firm
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    assert (await api.add_item(admin, engagement["id"])).status_code == 201


async def _audit_full(seed: Seeder, tenant_id: uuid.UUID) -> list[Json]:
    rows = await seed.rows(
        "SELECT action, actor_kind, actor_id, target_type, target_id, after_ref "
        "FROM audit_events WHERE tenant_id = $1 ORDER BY seq",
        tenant_id,
    )
    return [
        {
            **{
                k: row[k] for k in ("action", "actor_kind", "actor_id", "target_type", "target_id")
            },
            "after": None if row["after_ref"] is None else json.loads(cast(str, row["after_ref"])),
        }
        for row in rows
    ]


async def test_ac7_creating_the_first_item_writes_list_and_item_audit_events_and_an_outbox_event(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await _audit_full(seed, firm.tenant_id)
    response = await api.add_item(admin, engagement["id"])
    item = cast(Json, response.json())

    new_events = (await _audit_full(seed, firm.tenant_id))[len(before) :]
    assert sorted(cast(str, e["action"]) for e in new_events) == [
        "request_item.created",
        "request_list.created",
    ]
    by_action = {cast(str, e["action"]): e for e in new_events}
    for event in new_events:
        assert event["actor_kind"] == "human"
        assert event["actor_id"] == str(admin.user_id)
    created = by_action["request_item.created"]
    assert created["target_type"] == "request_item"
    assert created["target_id"] == item["id"]
    assert created["after"] == {"engagement_id": engagement["id"]}
    listed = by_action["request_list.created"]
    assert listed["target_type"] == "request_list"
    assert cast(Json, listed["after"])["engagement_id"] == engagement["id"]
    [payload] = await _outbox(seed, firm.tenant_id, "request_item.created")
    assert payload["request_item_id"] == item["id"]
    assert payload["engagement_id"] == engagement["id"]


async def test_ac7_later_items_write_no_further_request_list_event(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    for _ in range(3):
        assert (await api.add_item(admin, engagement["id"])).status_code == 201
    actions = [e["action"] for e in await _audit_full(seed, firm.tenant_id)]
    assert actions.count("request_list.created") == 1
    assert actions.count("request_item.created") == 3


async def test_ac4_the_member_added_event_names_the_creator_and_item_events_name_the_engagement(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    await api.create_ok(admin)
    events = {e["action"]: e for e in await _audit_full(seed, firm.tenant_id)}
    added = cast(Json, events["engagement_member.added"]["after"])
    assert added["user_id"] == str(admin.user_id)


async def test_ac7_the_first_item_creates_the_single_request_list_and_later_items_reuse_it(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    engagement_id = uuid.UUID(cast(str, engagement["id"]))
    assert (await seed.counts(firm.tenant_id))["request_lists"] == 0
    for _ in range(3):
        assert (await api.add_item(admin, engagement_id)).status_code == 201
    lists = await seed.rows(
        "SELECT id, engagement_id FROM request_lists WHERE tenant_id = $1", firm.tenant_id
    )
    [request_list] = lists
    assert request_list["engagement_id"] == engagement_id
    used = await seed.rows(
        "SELECT DISTINCT request_list_id FROM request_items WHERE tenant_id = $1", firm.tenant_id
    )
    assert [row["request_list_id"] for row in used] == [request_list["id"]]
    assert (await seed.counts(firm.tenant_id))["request_items"] == 3


async def test_ac7_each_engagement_has_its_own_single_request_list(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    first, second = await api.create_ok(admin), await api.create_ok(admin)
    for engagement in (first, second, first, second):
        assert (await api.add_item(admin, engagement["id"])).status_code == 201
    rows = await seed.rows(
        "SELECT engagement_id, count(*) AS n FROM request_lists WHERE tenant_id = $1 "
        "GROUP BY engagement_id",
        firm.tenant_id,
    )
    assert {(str(r["engagement_id"]), r["n"]) for r in rows} == {
        (cast(str, first["id"]), 1),
        (cast(str, second["id"]), 1),
    }


async def test_ac7_two_concurrent_first_items_end_with_one_request_list(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    responses = await asyncio.gather(
        api.add_item(admin, engagement["id"], {"description": "one", "audit_area": "A"}),
        api.add_item(admin, engagement["id"], {"description": "two", "audit_area": "B"}),
    )
    assert [r.status_code for r in responses] == [201, 201]
    counts = await seed.counts(firm.tenant_id)
    assert counts["request_lists"] == 1
    assert counts["request_items"] == 2
    used = await seed.rows(
        "SELECT DISTINCT request_list_id FROM request_items WHERE tenant_id = $1", firm.tenant_id
    )
    assert len(used) == 1
    listed = cast(list[Json], (await api.items(admin, engagement["id"])).json())
    assert {row["description"] for row in listed} == {"one", "two"}


async def test_ac7_many_concurrent_first_items_still_end_with_one_request_list(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    responses = await asyncio.gather(
        *(
            api.add_item(admin, engagement["id"], {"description": f"d{n}", "audit_area": "A"})
            for n in range(6)
        )
    )
    assert {r.status_code for r in responses} == {201}
    counts = await seed.counts(firm.tenant_id)
    assert (counts["request_lists"], counts["request_items"]) == (1, 6)


async def test_ac7_an_item_is_not_created_when_its_outbox_event_fails(
    lenient_client: httpx.AsyncClient, idp: FakeIdentityProvider, firm: Firm, seed: Seeder
) -> None:
    api = Api(lenient_client, idp)
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await seed.counts(firm.tenant_id)
    await seed.run(
        "ALTER TABLE outbox ADD CONSTRAINT zz_ac7_fail "
        "CHECK (event_type <> 'request_item.created') NOT VALID"
    )
    try:
        response = await api.add_item(admin, engagement["id"])
    finally:
        await seed.run("ALTER TABLE outbox DROP CONSTRAINT IF EXISTS zz_ac7_fail")
    assert response.status_code == 500
    assert await seed.counts(firm.tenant_id) == before  # no item, no list, no audit, no outbox


async def test_ac7_an_item_is_not_created_when_its_audit_event_fails(
    lenient_client: httpx.AsyncClient, idp: FakeIdentityProvider, firm: Firm, seed: Seeder
) -> None:
    api = Api(lenient_client, idp)
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await seed.counts(firm.tenant_id)
    await seed.run(
        "ALTER TABLE audit_events ADD CONSTRAINT zz_ac7_fail "
        "CHECK (action <> 'request_item.created') NOT VALID"
    )
    try:
        response = await api.add_item(admin, engagement["id"])
    finally:
        await seed.run("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS zz_ac7_fail")
    assert response.status_code == 500
    assert await seed.counts(firm.tenant_id) == before


@pytest.mark.parametrize(
    "body",
    [
        {"description": "", "audit_area": "Cash"},
        {"description": "   ", "audit_area": "Cash"},
        {"description": "d", "audit_area": ""},
        {"description": "d", "audit_area": " "},
        {"description": "x" * 2001, "audit_area": "Cash"},
        {"description": "d", "audit_area": "x" * 101},
        {"description": "d"},
        {"audit_area": "Cash"},
        {"description": "d", "audit_area": "Cash", "status": "received"},
        {"description": "d", "audit_area": "Cash", "engagement_id": str(uuid.uuid4())},
        {"description": {"x": DISTINCT_INPUT}, "audit_area": "Cash"},
        {"description": 5, "audit_area": "Cash"},
        {"description": "d", "audit_area": "Cash", "note": DISTINCT_INPUT},
    ],
)
async def test_ac7_invalid_bodies_are_422_without_echo_and_write_nothing(
    api: Api, firm: Firm, seed: Seeder, body: Json
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await seed.counts(firm.tenant_id)
    _assert_validation_error(await api.add_item(admin, engagement["id"], body))
    assert await seed.counts(firm.tenant_id) == before


async def test_ac7_limits_are_inclusive_and_trimmed(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    response = await api.add_item(
        admin, engagement["id"], {"description": "d" * 2000, "audit_area": "a" * 100}
    )
    assert response.status_code == 201
    response = await api.add_item(
        admin, engagement["id"], {"description": "  spaced  ", "audit_area": "  Cash "}
    )
    body = cast(Json, response.json())
    assert (body["description"], body["audit_area"]) == ("spaced", "Cash")


async def test_ac7_a_malformed_engagement_id_is_422_without_echo(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    for response in (
        await api.get(admin, DISTINCT_INPUT),
        await api.items(admin, DISTINCT_INPUT),
        await api.add_item(admin, DISTINCT_INPUT),
    ):
        _assert_validation_error(response)


# --- AC-8: reviewer and staff cannot create items; nothing is written ----------------------------


@pytest.mark.parametrize("role", ["reviewer", "staff"])
async def test_ac8_reviewer_and_staff_get_403_and_nothing_is_written(
    api: Api, firm: Firm, seed: Seeder, role: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    who = await firm.member(uuid.UUID(cast(str, engagement["id"])), role)
    before = await seed.counts(firm.tenant_id)
    _assert_forbidden(await api.add_item(who, engagement["id"]))
    assert await seed.counts(firm.tenant_id) == before
    assert before["request_lists"] == 0
    assert before["request_items"] == 0


@pytest.mark.parametrize("role", ["reviewer", "staff"])
async def test_ac8_a_denied_create_leaves_an_existing_list_and_items_untouched(
    api: Api, firm: Firm, seed: Seeder, role: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    assert (await api.add_item(admin, engagement["id"])).status_code == 201
    who = await firm.member(uuid.UUID(cast(str, engagement["id"])), role)
    before = await seed.counts(firm.tenant_id)
    audit_before = await _audit(seed, firm.tenant_id)
    _assert_forbidden(await api.add_item(who, engagement["id"]))
    assert await seed.counts(firm.tenant_id) == before
    assert await _audit(seed, firm.tenant_id) == audit_before


async def test_ac8_a_user_with_no_role_on_the_engagement_gets_403_and_nothing_is_written(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    nobody = await firm.person(None)
    before = await seed.counts(firm.tenant_id)
    _assert_forbidden(await api.add_item(nobody, engagement["id"]))
    assert await seed.counts(firm.tenant_id) == before


async def test_ac8_other_firm_or_missing_engagement_is_404_and_nothing_is_written(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    other = Firm(await seed.firm(), seed)
    theirs = await api.create_ok(await other.person("firm_admin"))
    mine = await firm.person("firm_admin")
    other_before = await seed.counts(other.tenant_id)
    _assert_not_found(await api.add_item(mine, theirs["id"]))
    _assert_not_found(await api.add_item(mine, uuid.uuid4()))
    assert await seed.counts(firm.tenant_id) == EMPTY
    assert await seed.counts(other.tenant_id) == other_before


# --- reading request items -----------------------------------------------------------------------


async def test_ac6_items_are_listed_in_creation_order(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    created: list[object] = []
    for n in range(4):
        response = await api.add_item(
            admin, engagement["id"], {"description": f"item {n}", "audit_area": "Cash"}
        )
        created.append(cast(Json, response.json())["id"])
    response = await api.items(admin, engagement["id"])
    assert response.status_code == 200
    rows = cast(list[Json], response.json())
    assert [row["id"] for row in rows] == created
    assert all(set(row) == ITEM_KEYS for row in rows)
    assert all(row["evidence_version_id"] is None for row in rows)
    assert all(row["engagement_id"] == engagement["id"] for row in rows)


async def test_ac6_an_engagement_without_items_has_an_empty_list(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    response = await api.items(admin, engagement["id"])
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac6_members_in_every_engagement_role_can_read_items(
    api: Api, firm: Firm, role: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    created = cast(Json, (await api.add_item(admin, engagement["id"])).json())
    who = await firm.member(uuid.UUID(cast(str, engagement["id"])), role)
    assert _ids(await api.items(who, engagement["id"])) == [created["id"]]


async def test_ac6_items_only_come_from_the_requested_engagement(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    first, second = await api.create_ok(admin), await api.create_ok(admin)
    one = cast(Json, (await api.add_item(admin, first["id"])).json())
    two = cast(Json, (await api.add_item(admin, second["id"])).json())
    assert _ids(await api.items(admin, first["id"])) == [one["id"]]
    assert _ids(await api.items(admin, second["id"])) == [two["id"]]


async def test_ac6_a_non_member_with_no_firm_role_gets_403_on_items(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    nobody = await firm.person(None)
    _assert_forbidden(await api.items(nobody, engagement["id"]))


async def test_ac5_items_of_another_firms_engagement_are_404(
    api: Api, firm: Firm, seed: Seeder
) -> None:
    other = Firm(await seed.firm(), seed)
    other_admin = await other.person("firm_admin")
    theirs = await api.create_ok(other_admin)
    assert (await api.add_item(other_admin, theirs["id"])).status_code == 201
    mine = await firm.person("firm_admin")
    _assert_not_found(await api.items(mine, theirs["id"]))


# --- contract revision 1 -------------------------------------------------------------------------

CONTROLS = ["\x00", "\x01", "\x08", "\x0a", "\x0d", "\x1b", "\x1f", "\x7f"]


@pytest.mark.parametrize("control", CONTROLS)
@pytest.mark.parametrize("field", ["name", "client_name", "client_entity_name"])
async def test_ac4_names_with_control_characters_are_422_and_write_nothing(
    api: Api, firm: Firm, seed: Seeder, field: str, control: str
) -> None:
    who = await firm.person("firm_admin")
    response = await api.create(who, **{field: f"a{control}b"})
    _assert_validation_error(response)
    assert await seed.counts(firm.tenant_id) == EMPTY


@pytest.mark.parametrize("control", CONTROLS)
async def test_ac7_audit_areas_with_control_characters_are_422(
    api: Api, firm: Firm, seed: Seeder, control: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await seed.counts(firm.tenant_id)
    response = await api.add_item(
        admin, engagement["id"], {"description": "d", "audit_area": f"a{control}b"}
    )
    _assert_validation_error(response)
    assert await seed.counts(firm.tenant_id) == before


@pytest.mark.parametrize("control", ["\x00", "\x01", "\x0d", "\x1b", "\x7f"])
async def test_ac7_descriptions_reject_control_characters_other_than_newline_and_tab(
    api: Api, firm: Firm, seed: Seeder, control: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    before = await seed.counts(firm.tenant_id)
    response = await api.add_item(
        admin, engagement["id"], {"description": f"a{control}b", "audit_area": "Cash"}
    )
    _assert_validation_error(response)
    assert await seed.counts(firm.tenant_id) == before


async def test_ac7_descriptions_may_contain_newlines_and_tabs(api: Api, firm: Firm) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    response = await api.add_item(
        admin, engagement["id"], {"description": "line one\n\tline two", "audit_area": "Cash"}
    )
    assert response.status_code == 201
    assert cast(Json, response.json())["description"] == "line one\n\tline two"


async def test_ac4_an_unhandled_error_is_a_500_with_a_fixed_body_and_a_log_of_the_class_only(
    lenient_client: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    firm: Firm,
    seed: Seeder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = Api(lenient_client, idp)
    who = await firm.person("firm_admin")
    await seed.run(
        "ALTER TABLE engagement_members ADD CONSTRAINT zz_log_fail CHECK (false) NOT VALID"
    )
    capsys.readouterr()
    try:
        response = await api.create(who, name=DISTINCT_INPUT)
    finally:
        await seed.run("ALTER TABLE engagement_members DROP CONSTRAINT IF EXISTS zz_log_fail")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    [logged] = [e for e in events if e.get("event") == "api.unexpected_error"]
    assert isinstance(logged.get("exception"), str) or isinstance(logged.get("error"), str)
    assert DISTINCT_INPUT not in out
    assert "zz_log_fail" not in out


@pytest.mark.parametrize("role", ["reviewer", "staff"])
async def test_ac8_denied_item_creation_writes_no_list_and_no_audit_event(
    api: Api, firm: Firm, seed: Seeder, role: str
) -> None:
    admin = await firm.person("firm_admin")
    engagement = await api.create_ok(admin)
    who = await firm.member(uuid.UUID(cast(str, engagement["id"])), role)
    audit_before = await _audit_full(seed, firm.tenant_id)
    _assert_forbidden(await api.add_item(who, engagement["id"]))
    assert await _audit_full(seed, firm.tenant_id) == audit_before
    assert await _outbox(seed, firm.tenant_id, "request_item.created") == []
