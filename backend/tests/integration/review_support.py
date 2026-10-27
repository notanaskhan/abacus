"""Shared set-up for the P-04 review service tests (P-04-T21 to T23; TASK-1400 to TASK-1402).

The Brightwater Hale cast on Northwind Robotics 401(k) Plan with `review.grammar_api` on, a test
reviewable (`probe_reviewed`) whose facts the tests set, and requests through the app as each
person (`current_context` overridden). Not a test module: the suites import it.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx

from abacus.api import create_app
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.review.api import STATEMENTS, ReviewableFacts, register_reviewable_facts

from .agent_tests.support import Person, Role, Seeder

PROBE = "probe_reviewed"
REVIEWER = STATEMENTS[2].version
PROBED: dict[uuid.UUID, ReviewableFacts] = {}


async def _probe_facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    return PROBED.get(target_id)


register_reviewable_facts(PROBE, _probe_facts)


def person_ctx(who: Person, *, mfa_age: timedelta | None = timedelta(0)) -> AuthContext:
    """A signed-in person; `mfa_age` is how long ago their second factor was verified."""
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        None if mfa_age is None else datetime.now(UTC) - mfa_age,
    )


Call = Callable[..., Awaitable[httpx.Response]]


def as_(ctx: object) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: ctx
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

    return call


class Cast:
    """The firm, its engagement and its people by first name."""

    def __init__(
        self, seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID, people: dict[str, Person]
    ) -> None:
        self.seed, self.tenant, self.engagement, self.people = seed, tenant, engagement, people

    def __getitem__(self, name: str) -> Person:
        return self.people[name]

    def call(self, who: str, **kw: object) -> Call:
        return as_(person_ctx(self[who], **kw))  # type: ignore[arg-type]  # mfa_age only

    def probe(self, **facts: object) -> uuid.UUID:
        """A reviewable on the engagement; preparers and the digest default to none and 'a'."""
        target = uuid.uuid4()
        PROBED[target] = ReviewableFacts(
            PROBE,
            target,
            self.engagement,
            cast(str, facts.pop("digest", "a" * 64)),
            1,
            cast(frozenset[uuid.UUID], facts.pop("preparers", frozenset[uuid.UUID]())),
            **facts,  # type: ignore[arg-type]  # the remaining ReviewableFacts fields
        )
        return target

    async def sign(
        self, who: str, target: uuid.UUID, level: str, seen: str = "sha256:" + "a" * 64
    ) -> httpx.Response:
        body = {
            "target_type": PROBE,
            "target_id": str(target),
            "level": level,
            "seen_hash": seen,
            "statement_version": REVIEWER,
        }
        return await self.call(who)("POST", "/v1/sign-offs", json=body)

    async def value(self, sql: str, *args: object) -> object:
        return await self.seed.value(sql, *args)


async def _named(seed: Seeder, who: Person, name: str) -> None:
    await seed.run("UPDATE users SET display_name = $1 WHERE id = $2", name, who.user_id)


async def make_cast(dsn: str) -> Cast:
    seed = Seeder(dsn)
    tenant = await seed.firm()
    names: dict[str, tuple[str, Role]] = {
        "margaret": ("Margaret Okonkwo", "engagement_partner"),
        "hannah": ("Hannah Leclerc", "manager"),
        "marcus": ("Marcus Delaney", "senior"),
        "ana": ("Ana Cruz", "staff"),
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
        "VALUES ($1, 'review.grammar_api', 'true', 'p04', 'TASK-1400')",
        tenant,
    )
    return Cast(seed, tenant, engagement, people)
