"""T-02-T09 (TASK-2214; SPEC-502 AC-10 to AC-14; T-02 §3, §4.3; TAX-01) over HTTP against
Postgres: the practice board's rows, tiles and bulk assignment.

The row's acceptance: tiles foot to 79 open, 145 done and 224 total, and a walled user's tiles,
totals and rows exclude walled returns. The Brightwater Hale footing (79/145/224) is the scenario
slice's (T-02-T11, golden footing tests); here a smaller synthetic board proves the same rules:
done is filed or accepted, everything else is open, and a wall removes a return from every
count with no hidden count.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

Json = dict[str, object]
Call = Callable[..., Awaitable[httpx.Response]]
DEMO = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


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


def _as(principal: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: principal
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

    return call


def _ctx(tenant: uuid.UUID, user: uuid.UUID, membership: uuid.UUID, role: str) -> AuthContext:
    return AuthContext(
        TenantContext(tenant, "human", str(user)),
        user,
        membership,
        role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass
class Board:
    seed: Seeder
    tenant: uuid.UUID
    partner: uuid.UUID
    offices: dict[str, uuid.UUID]
    clients: dict[str, uuid.UUID] = field(default_factory=dict[str, uuid.UUID])
    returns: dict[str, uuid.UUID] = field(default_factory=dict[str, uuid.UUID])

    async def person(self, name: str, firm_role: str | None) -> AuthContext:
        user = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
                name,
            ),
        )
        membership = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
                "VALUES ($1, $2, $3, 'active', 'partner', 'staff') RETURNING id",
                self.tenant,
                user,
                firm_role,
            ),
        )
        return _ctx(self.tenant, user, membership, firm_role or "staff")

    async def tax_return(
        self,
        client: str,
        status: str,
        *,
        office: str = "Chicago",
        form: str = "1040",
        extended: bool = False,
        due: date | None = None,
    ) -> uuid.UUID:
        if client not in self.clients:
            self.clients[client] = cast(
                uuid.UUID,
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                    self.tenant,
                    client,
                ),
            )
        client_id = self.clients[client]
        entity = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                "RETURNING id",
                self.tenant,
                client_id,
                client,
            ),
        )
        engagement = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, $4, "
                "'2025-01-01', '2025-12-31', $5) RETURNING id",
                self.tenant,
                client_id,
                entity,
                f"{client} TY2025",
                self.partner,
            ),
        )
        item = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
                "kind, name, office_id, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, "
                "$6, $7) RETURNING id",
                self.tenant,
                engagement,
                client_id,
                entity,
                f"{client} {form}",
                self.offices[office],
                self.partner,
            ),
        )
        await self.seed.run(
            "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
            "form, tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
            self.tenant,
            item,
            engagement,
            entity,
            form,
        )
        await self.seed.run(
            "UPDATE tax_returns SET status = $2, extended = $3, original_due_on = $4 "
            "WHERE work_item_id = $1",
            item,
            status,
            extended,
            due,
        )
        self.returns[f"{client} {form}"] = item
        return item


@pytest.fixture
async def board(seed: Seeder) -> Board:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.returns_v1', 'true', 't02-t09', 'T-02-T09')",
        tenant,
    )
    offices = {
        name: cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, $2, "
                "'America/Chicago') RETURNING id",
                tenant,
                name,
            ),
        )
        for name in ("Chicago", "Denver")
    }
    partner = (await seed.person(tenant)).user_id
    b = Board(seed, tenant, partner, offices)
    await b.tax_return("Ridgeline Partners", "preparing", form="1065", extended=True)
    await b.tax_return("Feld Household", "in_review", due=date(2026, 10, 15))
    await b.tax_return("Copperleaf Dental", "filed", office="Denver", form="1120s")
    await b.tax_return("Granite Peak", "accepted", office="Denver")
    await b.tax_return("Lakeshore Foundation", "not_started", form="990")
    return b


async def test_ac10_tiles_foot_open_done_and_total(board: Board) -> None:
    admin = await board.person("Grace Holloway", "firm_admin")
    with frozen(DEMO):
        found = await _as(admin)("GET", "/v1/tax-returns/summary")
    assert found.status_code == 200, found.text
    s = cast(Json, found.json())
    assert (s["total"], s["open"], s["done"], s["extended"]) == (5, 3, 2, 1)
    tiles = {t["status"]: t["count"] for t in cast(list[Json], s["tiles"])}
    assert sum(cast(int, n) for n in tiles.values()) == 5
    assert (tiles["filed"], tiles["accepted"], tiles["preparing"]) == (1, 1, 1)
    offices = {o["office_id"]: (o["open"], o["done"]) for o in cast(list[Json], s["offices"])}
    assert offices == {
        str(board.offices["Chicago"]): (3, 0),
        str(board.offices["Denver"]): (0, 2),
    }


async def test_ac11_a_walled_user_counts_and_sees_nothing_of_a_walled_return(
    board: Board,
) -> None:
    walled = await board.person("Hannah Leclerc", "firm_admin")
    await board.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        board.tenant,
        walled.user_id,
        board.clients["Copperleaf Dental"],
        board.partner,
    )
    with frozen(DEMO):
        s = cast(Json, (await _as(walled)("GET", "/v1/tax-returns/summary")).json())
        rows = cast(Json, (await _as(walled)("GET", "/v1/tax-returns")).json())
    assert (s["total"], s["open"], s["done"]) == (4, 3, 1)
    names = {r["client_name"] for r in cast(list[Json], rows["items"])}
    assert "Copperleaf Dental" not in names and rows["total"] == 4
    assert "hidden" not in str(s) and "hidden" not in str(rows)


async def test_ac12_filters_search_and_sort(board: Board) -> None:
    admin = await board.person("Grace Holloway", "firm_admin")
    call = _as(admin)
    with frozen(DEMO):
        reviewing = cast(Json, (await call("GET", "/v1/tax-returns?status=in_review")).json())
        searched = cast(Json, (await call("GET", "/v1/tax-returns?q=ridge")).json())
        denver = cast(
            Json, (await call("GET", f"/v1/tax-returns?office={board.offices['Denver']}")).json()
        )
        due = cast(Json, (await call("GET", "/v1/tax-returns?due_within_days=45")).json())
        by_client = cast(Json, (await call("GET", "/v1/tax-returns?sort=client")).json())
    assert [r["client_name"] for r in cast(list[Json], reviewing["items"])] == ["Feld Household"]
    first = cast(list[Json], searched["items"])[0]
    assert first["client_name"] == "Ridgeline Partners" and first["tags"] == ["ext"]
    assert {r["form"] for r in cast(list[Json], denver["items"])} == {"1120s", "1040"}
    assert [r["client_name"] for r in cast(list[Json], due["items"])] == ["Feld Household"]
    names = [str(r["client_name"]) for r in cast(list[Json], by_client["items"])]
    assert names == sorted(names, key=str.casefold)


async def test_ac12_an_unknown_sort_is_refused(board: Board) -> None:
    admin = await board.person("Grace Holloway", "firm_admin")
    found = await _as(admin)("GET", "/v1/tax-returns?sort=status")
    assert found.status_code == 422


async def test_ac13_bulk_assign_refuses_what_the_viewer_cannot_see(board: Board) -> None:
    admin = await board.person("Grace Holloway", "firm_admin")
    unknown = uuid.uuid4()
    with frozen(DEMO):
        found = await _as(admin)(
            "POST",
            "/v1/tax-returns:bulk-assign",
            json={
                "return_ids": [str(unknown)],
                "role": "preparer",
                "user_id": str(admin.user_id),
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert found.status_code == 200, found.text
    assert found.json() == {"assigned": 0, "refused": [str(unknown)]}


async def test_inv4_a_client_principal_gets_404(board: Board) -> None:
    client = AuthContext(
        TenantContext(board.tenant, "human", str(uuid.uuid4())),
        uuid.uuid4(),
        uuid.uuid4(),
        None,
        None,
        client=True,
    )
    found = await _as(client)("GET", "/v1/tax-returns")
    assert found.status_code == 404
