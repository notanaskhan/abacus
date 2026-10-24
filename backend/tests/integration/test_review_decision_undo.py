"""P-01-T13 against Postgres (migration 0117; DEC-24, ADR-161 clause 6; P-01 AC 3.1.4, 3.1.4b).

"Undo within 10 s restores Uploaded - needs review, the same version can then be decided again,
and after 10 s Undo returns 409 undo_window_closed."

Every decision and Undo goes through `create_app()` as the app role with the fake identity
provider; business time is frozen (`kernel.clock.frozen`) on a synthetic firm, so the service's
window and the database's `abacus_now()` read the same instant. Seeding goes through the shared
Seeder as the superuser. Expectations come from the plan, not the implementation.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import undo_review_decision
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    configure_verifier,
    reset_verifier,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)
from abacus.modules.identity.service import TENANT_HEADER
from abacus_tools.fakes.identity import FakeIdentityProvider

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
Json = dict[str, Any]  # parsed JSON bodies, untyped by httpx
T0 = datetime.fromisoformat("2026-09-14T09:42:00-05:00")


def at(seconds: int) -> datetime:
    return T0.replace(second=seconds)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
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
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@dataclass(frozen=True)
class World:
    seed: Seeder
    http: httpx.AsyncClient
    idp: FakeIdentityProvider
    tenant: uuid.UUID
    engagement: uuid.UUID
    item: uuid.UUID
    version: uuid.UUID
    hannah: Person
    marcus: Person

    async def subject(self, who: Person) -> str:
        return str(
            await self.seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id)
        )

    async def post(self, who: Person, path: str, body: Json | None = None) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.idp.token(await self.subject(who))}",
            TENANT_HEADER: str(self.tenant),
        }
        return await self.http.post(path, json=body or {}, headers=headers)

    async def accept(self, who: Person, when: datetime) -> httpx.Response:
        with frozen(when):
            return await self.post(
                who,
                f"/v1/engagements/{self.engagement}/evidence-versions/{self.version}"
                "/decision/accept",
            )

    async def send_back(self, who: Person, when: datetime) -> httpx.Response:
        with frozen(when):
            return await self.post(
                who,
                f"/v1/engagements/{self.engagement}/evidence-versions/{self.version}"
                "/decision/send-back",
                {"reason_code": "wrong_document"},
            )

    async def undo(self, who: Person, decision: object, when: datetime) -> httpx.Response:
        with frozen(when):
            return await self.post(
                who, f"/v1/engagements/{self.engagement}/review-decisions/{decision}/undo"
            )

    async def item_status(self) -> str:
        return await self.seed.item_status(self.item)

    async def rows(self) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT id, decision, decision_seq, undoes_decision_id, actor_id, reason_code "
            "FROM review_decisions WHERE evidence_version_id = $1 ORDER BY decision_seq",
            self.version,
        )


@pytest.fixture
async def world(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> World:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    hannah = await seed.person(tenant)
    marcus = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, hannah.user_id)
    await seed.member(engagement, hannah, "engagement_partner")
    await seed.member(engagement, marcus, "manager")
    item = await seed.item(tenant, engagement, hannah.user_id)
    evidence_item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Certified trust report', 'system', 'seed') RETURNING id",
        tenant,
        engagement,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'upload', 'uploaded') RETURNING id",
            tenant,
            engagement,
            evidence_item,
            fingerprint,
            f"tenants/{tenant}/sha256/{fingerprint}",
        ),
    )
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagement,
        item,
        version,
    )
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", item)
    return World(seed, http, idp, tenant, engagement, item, version, hannah, marcus)


def _id(response: httpx.Response) -> str:
    assert response.status_code == 201, response.text
    return str(cast(Json, response.json())["id"])


# --- AC 3.1.4: Undo inside 10 s ------------------------------------------------------------------


async def test_ac314_undo_within_ten_seconds_restores_uploaded_and_keeps_the_accept(
    world: World,
) -> None:
    accepted = _id(await world.accept(world.hannah, at(0)))
    assert await world.item_status() == "received"

    response = await world.undo(world.hannah, accepted, at(7))
    assert response.status_code == 201, response.text
    body = cast(Json, response.json())
    assert body["undoes_decision_id"] == accepted
    assert body["item_status"] == "uploaded"
    assert body["request_item_ids"] == [str(world.item)]
    assert await world.item_status() == "uploaded"

    rows = await world.rows()
    assert [(r["decision"], r["decision_seq"]) for r in rows] == [("accept", 1), ("undone", 2)]
    assert str(rows[1]["undoes_decision_id"]) == accepted and rows[1]["reason_code"] is None
    assert rows[1]["actor_id"] == rows[0]["actor_id"] == str(world.hannah.user_id)

    events = await world.seed.events(world.tenant)
    undone = [e for e in events if e.action == "review_decision.undone"]
    assert [(e.actor_kind, e.actor_id) for e in undone] == [("human", str(world.hannah.user_id))]
    assert undone[0].after["undoes_decision_id"] == accepted
    assert "request_item.uploaded" in [e.action for e in events]
    outbox = await world.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2",
        world.tenant,
        "request_item.status_changed",
    )
    assert len(outbox) == 1


async def test_ac314_after_ten_seconds_undo_is_409_undo_window_closed(world: World) -> None:
    accepted = _id(await world.accept(world.hannah, at(0)))
    response = await world.undo(world.hannah, accepted, at(10))
    assert response.status_code == 409
    assert cast(Json, response.json())["detail"] == "undo_window_closed"
    assert await world.item_status() == "received"
    assert len(await world.rows()) == 1


async def test_ac314_only_the_person_who_decided_may_undo(world: World) -> None:
    accepted = _id(await world.accept(world.hannah, at(0)))
    response = await world.undo(world.marcus, accepted, at(3))
    assert response.status_code == 403
    assert len(await world.rows()) == 1


async def test_ac315_a_send_back_is_undone_the_same_way(world: World) -> None:
    returned = _id(await world.send_back(world.hannah, at(0)))
    assert await world.item_status() == "returned"
    assert (await world.undo(world.hannah, returned, at(5))).status_code == 201
    assert await world.item_status() == "uploaded"


async def test_ac314_undo_restores_the_reviewers_assignment(world: World) -> None:
    """Deciding clears the version's assignment; Undo puts it back as it was."""
    with frozen(at(0)):
        taken = await world.post(
            world.marcus,
            f"/v1/engagements/{world.engagement}/review-queue/{world.version}/take",
        )
    assert taken.status_code == 200, taken.text
    accepted = _id(await world.accept(world.hannah, at(1)))
    assignee = "SELECT assignee_user_id FROM review_assignments WHERE evidence_version_id = $1"
    assert await world.seed.value(assignee, world.version) is None
    assert (await world.undo(world.hannah, accepted, at(4))).status_code == 201
    assert await world.seed.value(assignee, world.version) == world.marcus.user_id


async def test_ac315_undoing_a_send_back_restores_the_items_own_prior_status(
    world: World,
) -> None:
    """An item already Returned stays Returned when a send-back on it is undone (DEC-214)."""
    await world.seed.run("UPDATE request_items SET status = 'returned' WHERE id = $1", world.item)
    returned = _id(await world.send_back(world.hannah, at(0)))
    assert await world.item_status() == "returned"
    response = await world.undo(world.hannah, returned, at(3))
    assert response.status_code == 201, response.text
    assert cast(Json, response.json())["item_status"] == "returned"
    assert await world.item_status() == "returned"
    outbox = await world.seed.rows(
        "SELECT 1 FROM outbox WHERE tenant_id = $1 AND event_type = 'request_item.status_changed'",
        world.tenant,
    )
    assert outbox == []  # nothing moved


# --- AC 3.1.4b: Undo, then decide again ----------------------------------------------------------


async def test_ac314b_undo_then_another_reviewer_decides_the_same_version(world: World) -> None:
    accepted = _id(await world.accept(world.hannah, at(0)))
    assert (await world.undo(world.hannah, accepted, at(4))).status_code == 201

    again = _id(await world.send_back(world.marcus, at(6)))
    assert await world.item_status() == "returned"
    rows = await world.rows()
    assert [(r["decision"], r["decision_seq"]) for r in rows] == [
        ("accept", 1),
        ("undone", 2),
        ("send_back", 3),
    ]
    assert str(rows[2]["id"]) == again

    second = await world.undo(world.hannah, accepted, at(7))  # the first accept, again
    assert second.status_code == 409
    assert cast(Json, second.json())["detail"] == "undo_window_closed"


async def test_ac314b_a_second_decision_while_one_is_effective_is_409_already_decided(
    world: World,
) -> None:
    _id(await world.accept(world.hannah, at(0)))
    response = await world.accept(world.marcus, at(2))
    assert response.status_code == 409
    assert cast(Json, response.json())["detail"] == "already_decided"


# --- ADR-005: humans decide, and only in a request they make -------------------------------------


async def test_inv1_an_agent_or_a_worker_cannot_undo(world: World) -> None:
    accepted = _id(await world.accept(world.hannah, at(0)))
    hannah = AuthContext(
        TenantContext(world.tenant, "human", str(world.hannah.user_id)),
        world.hannah.user_id,
        uuid.uuid4(),
        None,
        None,
    )
    run = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(world.tenant, "agent", f"agent:probe:{run}", world.hannah.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=world.engagement,
        task_scope=frozenset({"review_decision.undo", "evidence.accept"}),
        initiator=hannah,
        issued_by=_ISSUER,
    )
    for ctx in (hannah, agent):  # outside any served request: a worker, a script, an agent
        with frozen(at(1)), pytest.raises(Forbidden):
            async with uow(ctx.tenant) as tx:
                await undo_review_decision(
                    tx,
                    cast(AuthContext, ctx),
                    world.engagement,
                    uuid.UUID(accepted),
                )
    assert len(await world.rows()) == 1


# --- The database (0117), as the superuser with the session's actor and business time ------------

DECIDE = (
    "INSERT INTO review_decisions (id, tenant_id, engagement_id, evidence_version_id, "
    "request_item_id, decision, reason_code, corrects_proposal, actor_kind, actor_id, "
    "decision_seq, undoes_decision_id) VALUES ($1, $2, $3, $4, $5, $6, $7, false, $8, $9, "
    "$10, $11)"
)


async def _row(
    world: World,
    who: tuple[str, str],
    decision: str,
    seq: int,
    undoes: uuid.UUID | None,
    when: str,
    reason: str | None = None,
) -> uuid.UUID:
    made = uuid.uuid4()
    await world.seed.as_actor(
        world.tenant,
        who,
        DECIDE,
        made,
        world.tenant,
        world.engagement,
        world.version,
        world.item,
        decision,
        reason,
        *who,
        seq,
        undoes,
        at=when,
    )
    return made


async def test_0117_the_database_holds_the_undo_rules(world: World) -> None:
    hannah = ("human", str(world.hannah.user_id))
    marcus = ("human", str(world.marcus.user_id))
    first = await _row(world, hannah, "accept", 1, None, "2026-09-14T09:42:00-05:00")
    with pytest.raises(asyncpg.CheckViolationError):  # a second decision while one is effective
        await _row(world, marcus, "accept", 2, None, "2026-09-14T09:42:01-05:00")
    with pytest.raises(asyncpg.CheckViolationError, match="already_decided"):  # a stale number
        await _row(world, marcus, "accept", 1, None, "2026-09-14T09:42:01-05:00")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # someone else's decision
        await _row(world, marcus, "undone", 2, first, "2026-09-14T09:42:02-05:00")
    with pytest.raises(asyncpg.CheckViolationError, match="undo_window_closed"):  # too late
        await _row(world, hannah, "undone", 2, first, "2026-09-14T09:42:11-05:00")
    with pytest.raises(asyncpg.CheckViolationError):  # an undo carries no reason
        await _row(world, hannah, "undone", 2, first, "2026-09-14T09:42:03-05:00", "other")
    undone = await _row(world, hannah, "undone", 2, first, "2026-09-14T09:42:09-05:00")
    with pytest.raises(asyncpg.CheckViolationError):  # an undo of an undo
        await _row(world, hannah, "undone", 3, undone, "2026-09-14T09:42:09-05:00")
    third = await _row(world, marcus, "accept", 3, None, "2026-09-14T09:42:10-05:00")
    with pytest.raises(asyncpg.CheckViolationError, match="undo_window_closed"):  # not effective
        await _row(world, hannah, "undone", 4, first, "2026-09-14T09:42:10-05:00")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # nor undoes it for them
        await _row(
            world, ("agent", "agent:probe"), "undone", 4, third, "2026-09-14T09:42:11-05:00"
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # insert-only, still
        await world.seed.run("UPDATE review_decisions SET decision = 'reject'")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await world.seed.run("DELETE FROM review_decisions")
