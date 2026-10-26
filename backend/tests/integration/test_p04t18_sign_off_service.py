"""P-04-T18 acceptance (TASK-1300; ADR-160 clauses 2 to 4; SHL-12): the sign-off service.

"In an API test Hannah Leclerc signs Trial Balance v1 at L2 after Marcus Delaney's L1 adoption,
and every R-SO rule returns its fixed error code." Requests go through the app as each person
(`current_context` overridden), with `review.grammar_api` on for the firm.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.review.api import STATEMENTS, ReviewableFacts, register_reviewable_facts

from .agent_tests.support import Person, Role, Seeder
from .conftest import MigratedDatabase
from .test_sign_off_segregation import Team
from .test_sign_off_segregation import (
    _trial_balance as trial_balance,  # pyright: ignore[reportPrivateUsage] -- the P-04-T15 suite's trial balance seed, shared
)

pytestmark = pytest.mark.asyncio
REVIEWER = STATEMENTS[2].version
EQR = STATEMENTS[5].version
# A test owner whose facts the tests set: target id -> facts.
PROBED: dict[uuid.UUID, ReviewableFacts] = {}


async def _probe_facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    return PROBED.get(target_id)


register_reviewable_facts("probe_signed", _probe_facts)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


def person_ctx(who: Person, actor_kind: str = "human") -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, actor_kind, str(who.user_id)),  # type: ignore[arg-type]
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


Call = Callable[..., Awaitable[httpx.Response]]


def as_(ctx: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: ctx
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

    return call


class World:
    def __init__(
        self, seed: Seeder, team: Team, people: dict[str, Person], entity: uuid.UUID
    ) -> None:
        self.seed, self.team, self.people, self.entity = seed, team, people, entity

    def __getitem__(self, name: str) -> Person:
        return self.people[name]

    async def sign(
        self, who: str, target_type: str, target: uuid.UUID, level: str, seen: str, **kw: object
    ) -> httpx.Response:
        body = {
            "target_type": target_type,
            "target_id": str(target),
            "level": level,
            "seen_hash": seen,
            "statement_version": kw.get("statement", EQR if level == "L5_eqr" else REVIEWER),
        }
        ctx = cast(AuthContext, kw.get("ctx") or person_ctx(self[who]))
        return await as_(ctx)("POST", "/v1/sign-offs", json=body)

    async def ladder(self, who: str, target_type: str, target: uuid.UUID) -> httpx.Response:
        return await as_(person_ctx(self[who]))(
            "GET", "/v1/sign-offs", params={"target_type": target_type, "target_id": str(target)}
        )

    async def count(self, target: uuid.UUID) -> int:
        return int(
            str(
                await self.seed.value(
                    "SELECT count(*) FROM sign_offs WHERE target_id = $1", target
                )
            )
        )

    def probe(self, **facts: object) -> uuid.UUID:
        target = uuid.uuid4()
        PROBED[target] = ReviewableFacts(
            "probe_signed",
            target,
            self.team.engagement,
            cast(str, facts.pop("digest", "a" * 64)),
            1,
            cast(frozenset[uuid.UUID], facts.pop("preparers", frozenset[uuid.UUID]())),
            **facts,  # type: ignore[arg-type]
        )
        return target


async def _named(seed: Seeder, who: Person, name: str) -> None:
    await seed.run("UPDATE users SET display_name = $1 WHERE id = $2", name, who.user_id)


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    names: dict[str, tuple[str, Role]] = {
        "margaret": ("Margaret Okonkwo", "engagement_partner"),
        "hannah": ("Hannah Leclerc", "manager"),
        "marcus": ("Marcus Delaney", "senior"),
        "ana": ("Ana Cruz", "staff"),
        "kevin": ("Kevin Osei", "senior"),
    }
    people = {key: await seed.person(tenant) for key in names}
    entity = await seed.entity(tenant, "Northwind Robotics 401(k) Plan")
    engagement = await seed.engagement(tenant, entity, people["margaret"].user_id)
    for key, (name, role) in names.items():
        await _named(seed, people[key], name)
        await seed.member(engagement, people[key], role)  # staff roles confirm independence
    thomas = await seed.person(tenant)
    await _named(seed, thomas, "Thomas Whitcombe")
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'eqr_reviewer')",
        tenant,
        engagement,
        thomas.user_id,
    )
    await seed.confirm(engagement, thomas)
    people["thomas"] = thomas
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'p04t18', 'TASK-1300')",
        tenant,
    )
    return World(seed, Team(seed, tenant, engagement), people, entity)


async def _tb(world: World) -> tuple[uuid.UUID, str]:
    """Trial Balance v1, adopted by Marcus (its preparer) and annotated by Kevin."""
    tb = await trial_balance(world.team, world.entity, world["marcus"], world["kevin"])
    found = await world.ladder("hannah", "trial_balance", tb)
    assert found.status_code == 200, found.text
    return tb, cast(str, found.json()["target"]["content_hash"])


async def test_ac_hannah_signs_trial_balance_v1_at_l2_after_marcus_l1(world: World) -> None:
    tb, seen = await _tb(world)
    assert seen.startswith("sha256:") and len(seen) == 71

    l1 = await world.sign("marcus", "trial_balance", tb, "L1_preparer", seen)
    assert l1.status_code == 201, l1.text
    l2 = await world.sign("hannah", "trial_balance", tb, "L2_reviewer", seen)
    assert l2.status_code == 201, l2.text
    signed = l2.json()
    assert (signed["level"], signed["initials"], signed["signer_name"]) == (
        "L2_reviewer",
        "HL",
        "Hannah Leclerc",
    )
    assert (signed["content_hash"], signed["statement_version"], signed["stale"]) == (
        seen,
        REVIEWER,
        False,
    )

    ladder = (await world.ladder("hannah", "trial_balance", tb)).json()
    assert ladder["target"]["label"] == "Trial Balance"
    assert ladder["target"]["version_no"] == 1
    by_level = {lv["level"]: lv["latest"] for lv in ladder["levels"]}
    assert by_level["L1_preparer"]["initials"] == "MD"
    assert by_level["L2_reviewer"]["initials"] == "HL"
    assert by_level["L3_manager"] is None

    rows = await world.seed.rows(
        "SELECT level, signed_by, initials, engagement_role_at_sign, version_no, "
        "statement_version, actor_kind, kind, independence_checked_at "
        "FROM sign_offs WHERE target_id = $1 ORDER BY level",
        tb,
    )
    assert [(r["level"], r["initials"], r["engagement_role_at_sign"]) for r in rows] == [
        (1, "MD", "senior"),
        (2, "HL", "manager"),
    ]
    assert all(r["actor_kind"] == "human" and r["kind"] == "ladder" for r in rows)
    assert all(r["version_no"] == 1 and r["independence_checked_at"] for r in rows)
    audited = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'sign_off.recorded'",
        world.team.tenant,
    )
    assert audited == 2
    announced = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'sign_off.recorded'",
        world.team.tenant,
    )
    assert announced == 2


async def test_rso_content_changed_writes_nothing(world: World) -> None:
    tb, _seen = await _tb(world)
    found = await world.sign("marcus", "trial_balance", tb, "L1_preparer", "sha256:" + "0" * 64)
    assert (found.status_code, found.json()["detail"]) == (409, "content_changed")
    assert await world.count(tb) == 0


async def test_rso3_the_preparer_is_refused_l2_with_segregation(world: World) -> None:
    tb, seen = await _tb(world)
    l1 = await world.sign("hannah", "trial_balance", tb, "L1_preparer", seen)
    assert l1.status_code == 201
    for who in ("marcus", "kevin", "hannah"):  # the adopter, the annotator, the L1 signer
        found = await world.sign(who, "trial_balance", tb, "L2_reviewer", seen)
        assert (found.status_code, found.json()["detail"]) == (409, "segregation"), who
    assert await world.count(tb) == 1


async def test_rso2_a_level_the_matrix_does_not_allow_is_level_not_permitted(
    world: World,
) -> None:
    target = world.probe()
    seen = "sha256:" + "a" * 64
    for who, level in (("ana", "L2_reviewer"), ("hannah", "L4_partner"), ("margaret", "L5_eqr")):
        found = await world.sign(who, "probe_signed", target, level, seen)
        assert (found.status_code, found.json()["detail"]) == (403, "level_not_permitted"), who
    # The EQR signs L5 only (R-SO-3): L1 to L4 are refused, L5 after the preparer is signed.
    for level in ("L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"):
        found = await world.sign("thomas", "probe_signed", target, level, seen)
        assert (found.status_code, found.json()["detail"]) == (403, "level_not_permitted")
    assert (
        await world.sign("ana", "probe_signed", target, "L1_preparer", seen)
    ).status_code == 201
    found = await world.sign("thomas", "probe_signed", target, "L5_eqr", seen)
    assert found.status_code == 201, found.text
    assert found.json()["statement_version"] == EQR


async def test_rso4_open_review_notes_block_l2_with_their_count(world: World) -> None:
    target = world.probe()
    seen = "sha256:" + "a" * 64
    assert (
        await world.sign("ana", "probe_signed", target, "L1_preparer", seen)
    ).status_code == 201
    for anchor in ("RA!C14", "RA!C22"):
        await world.seed.as_actor(
            world.team.tenant,
            ("human", str(world["hannah"].user_id)),
            "INSERT INTO reviewable_notes (tenant_id, engagement_id, target_type, target_id, "
            "anchor, body, raised_by) VALUES ($1, $2, 'probe_signed', $3, $4, 'Tie this.', $5)",
            world.team.tenant,
            world.team.engagement,
            target,
            anchor,
            world["hannah"].user_id,
        )
    found = await world.sign("hannah", "probe_signed", target, "L2_reviewer", seen)
    assert found.status_code == 409
    assert found.json() == {"detail": "open_review_notes", "facts": {"count": 2}}
    sheet = await as_(person_ctx(world["hannah"]))(
        "GET",
        "/v1/sign-offs/eligibility",
        params={"target_type": "probe_signed", "target_id": str(target), "level": "L2_reviewer"},
    )
    checks = {c["code"]: c for c in sheet.json()["checks"]}
    assert checks["open_review_notes"]["result"] == "fail"
    assert len(checks["open_review_notes"]["refs"]) == 2
    assert sheet.json()["eligible"] is False


async def test_rso5_an_unconfirmed_signer_is_independence_pending(world: World) -> None:
    target = world.probe()
    await world.seed.run(
        "UPDATE independence_confirmations SET status = 'requested' "
        "WHERE engagement_id = $1 AND user_id = $2",
        world.team.engagement,
        world["ana"].user_id,
    )
    found = await world.sign("ana", "probe_signed", target, "L1_preparer", "sha256:" + "a" * 64)
    assert (found.status_code, found.json()["detail"]) == (409, "independence_pending")
    assert await world.count(target) == 0


async def test_rso6_empty_fields_are_incomplete_and_uncited_values_uncited_change(
    world: World,
) -> None:
    seen = "sha256:" + "a" * 64
    empty = world.probe(incomplete_count=2)
    found = await world.sign("ana", "probe_signed", empty, "L1_preparer", seen)
    assert found.json() == {"detail": "incomplete", "facts": {"count": 2}}
    assert found.status_code == 409
    uncited = world.probe(uncited_count=1, cell_count=14, cited_count=13)
    found = await world.sign("ana", "probe_signed", uncited, "L1_preparer", seen)
    assert (found.status_code, found.json()["detail"]) == (422, "uncited_change")


async def test_rso8_an_l1_on_agent_work_records_the_run_it_adopted(world: World) -> None:
    run = uuid.uuid4()
    target = world.probe(adopted_run_id=run, adopted_run_number=4127)
    seen = "sha256:" + "a" * 64
    found = await world.sign("marcus", "probe_signed", target, "L1_preparer", seen)
    assert found.status_code == 201, found.text
    assert (found.json()["adopted_run_id"], found.json()["adopted_run_number"]) == (str(run), 4127)
    l2 = await world.sign("hannah", "probe_signed", target, "L2_reviewer", seen)
    assert l2.json()["adopted_run_id"] is None  # only the L1 adopts
    assert (
        await world.seed.value(
            "SELECT adopted_run_id FROM sign_offs WHERE target_id = $1 AND level = 1", target
        )
        == run
    )


async def test_rso1_only_a_live_person_signs(world: World) -> None:
    target = world.probe()
    seen = "sha256:" + "a" * 64
    for kind in ("agent", "system"):
        found = await world.sign(
            "ana", "probe_signed", target, "L1_preparer", seen, ctx=person_ctx(world["ana"], kind)
        )
        assert found.status_code == 403, kind
    assert await world.count(target) == 0


async def test_the_other_fixed_codes(world: World) -> None:
    target = world.probe()
    seen = "sha256:" + "a" * 64
    early = await world.sign("hannah", "probe_signed", target, "L2_reviewer", seen)
    assert (early.status_code, early.json()["detail"]) == (409, "not_prepared")
    wrong = await world.sign(
        "ana", "probe_signed", target, "L1_preparer", seen, statement="reviewer-v0"
    )
    assert (wrong.status_code, wrong.json()["detail"]) == (422, "sign_off_invalid")
    assert (
        await world.sign("ana", "probe_signed", target, "L1_preparer", seen)
    ).status_code == 201
    again = await world.sign("ana", "probe_signed", target, "L1_preparer", seen)
    assert (again.status_code, again.json()["detail"]) == (409, "already_signed")


async def test_the_routes_are_404_with_the_flag_off(world: World) -> None:
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1",
        world.team.tenant,
    )
    target = world.probe()
    assert (await world.ladder("hannah", "probe_signed", target)).status_code == 404
    found = await world.sign("ana", "probe_signed", target, "L1_preparer", "sha256:" + "a" * 64)
    assert found.status_code == 404
