# ac-test-author: ayushkbhatia
"""Shared set-up for the P-04-T28 independent suites (TASK-1464; ADR-078): a firm with
`review.grammar_api` and `notifications.v2` on, the Brightwater Hale cast on one engagement, the
agent acting on a recorded run, C4 citations, and a test field owner and reviewable registered
through the public slots (`agents.api.register_suggestion_applier`,
`review.api.register_reviewable_facts`, `review.api.register_decision_kind`), as an owner module
registers its own. Not a test module: the two suites import it.

Seeding is the superuser's (`Seeder`), as the agents and owners write their rows; every verdict
goes through `create_app()` over HTTP as a signed-in person.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

import httpx

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import (
    AdoptedValue,
    register_suggestion_applier,
    register_suggestion_target,
)
from abacus.modules.identity.api import AgentContext, AuthContext, agent_context_for_run
from abacus.modules.notifications import api as notifications
from abacus.modules.review.api import (
    CardContext,
    CardFactor,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    Reassessment,
    ReviewableFacts,
    record_value,
    register_decision_kind,
    register_reviewable_facts,
)

from .support import Net, Person, Role, Seeder, Site

Json = dict[str, object]
RETURN: Final = "indep_return"  # a field owner whose applier writes through record_value
UNOWNED: Final = "indep_unowned"  # accepts suggestions, but nobody writes them
PROBE: Final = "indep_probe"  # a reviewable whose facts the tests set
MATERIALITY: Final = "indep_materiality"  # a decision kind reserved to the partner
QUESTION: Final = "planning_materiality"
SCREENER: Final = "evidence.screener"

# --- The field owner (ADR-161 clause 1, DEC-602) ---------------------------------------------


async def _apply(tx: UnitOfWork, _ctx: AuthContext, value: AdoptedValue) -> None:
    await record_value(
        tx,
        engagement_id=value.engagement_id,
        target_type=value.target_type,
        target_id=value.target_id,
        field_key=value.field_key,
        value=value.value,
        value_source=value.value_source,
        cause=value.cause,
        suggestion_id=value.suggestion_id,
        checkpoint_id=value.checkpoint_id,
        citation_ids=value.citation_ids,
        citation_note=value.citation_note,
    )


# Which engagement each test target belongs to, as its owner would say (security review M4).
OWNED: dict[uuid.UUID, uuid.UUID] = {}


async def _engagement_of(_tenant: TenantContext, target_id: uuid.UUID) -> uuid.UUID | None:
    return OWNED.get(target_id)


def own(site: Site) -> uuid.UUID:
    """A new target of the owner's, on the site's engagement."""
    target = uuid.uuid4()
    OWNED[target] = site.engagement_id
    return target


register_suggestion_applier(RETURN, _apply, engagement_of=_engagement_of)
register_suggestion_target(UNOWNED, engagement_of=_engagement_of)

# --- The reviewable (P-04-T18 slot) ------------------------------------------------------------
PROBED: dict[uuid.UUID, ReviewableFacts] = {}


async def _probe_facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    return PROBED.get(target_id)


register_reviewable_facts(PROBE, _probe_facts)


def content_hash(seed_text: str) -> str:
    """The owner's digest (bare hex, `review.hashing`); the wire carries it as `sha256:<hex>`."""
    return hashlib.sha256(seed_text.encode()).hexdigest()


def probe(site: Site, preparers: tuple[Person, ...], *, hash_text: str = "v1") -> uuid.UUID:
    """A workpaper-like reviewable on the site's engagement, prepared by `preparers`."""
    target = uuid.uuid4()
    PROBED[target] = ReviewableFacts(
        target_type=PROBE,
        target_id=target,
        engagement_id=site.engagement_id,
        content_hash=content_hash(f"{target}:{hash_text}"),
        version_no=1,
        preparer_user_ids=frozenset(p.user_id for p in preparers),
        label="Contributions testing",
    )
    return target


def hash_of(target: uuid.UUID) -> str:
    return "sha256:" + PROBED[target].content_hash


# --- The decision kind: Northwind planning materiality (F-04 §3.6 golden, contract §8) --------
# Literals typed from the contract's SHL-11 a and d examples, never computed from a module.
_OPTIONS: Final = (
    CardOption(
        "pct_1_0",
        "1.0% — $168,100",
        {
            "rate": "0.010",
            "materiality": "168100",
            "performance_materiality": "126075",
            "clearly_trivial": "8405",
        },
    ),
    CardOption(
        "pct_1_5",
        "1.5% — $252,200",
        {
            "rate": "0.015",
            "materiality": "252200",
            "performance_materiality": "189150",
            "clearly_trivial": "12610",
        },
    ),
)


async def _options(_tenant: TenantContext, _subject: CardSubject) -> ComputedCard:
    return ComputedCard(
        options=_OPTIONS,
        context=(CardContext("amount", "Amount", "$16,812,400"),),
        factors=(CardFactor("late_deposits", "Late deposits of participant contributions"),),
    )


async def _reassess(
    _tenant: TenantContext, _subject: CardSubject, _decided: str | None, _card: ComputedCard
) -> Reassessment:
    # Tue Oct 6 (contract §8, SHL-11 d): 1.5% of 16,861,000 at the firm's rounding is
    # 252,900, $700 from 252,200: no change.
    return Reassessment(
        changed=False,
        figures={"benchmark": "16861000", "materiality": "252900", "difference": "700"},
    )


register_decision_kind(
    DecisionKind(
        code=MATERIALITY,
        reserved_role="engagement_partner",
        options=_options,
        questions={QUESTION: "Which planning materiality should the Northwind PY2025 audit use?"},
        reassess=_reassess,
    )
)


# --- The firm -------------------------------------------------------------------------------
CAST: Final[dict[str, tuple[str, Role]]] = {
    "margaret": ("Margaret Okonkwo", "engagement_partner"),
    "hannah": ("Hannah Leclerc", "manager"),
    "priya": ("Priya Raman", "manager"),
    "samuel": ("Samuel Ito", "senior"),
    "raj": ("Raj Malhotra", "senior"),
    "ana": ("Ana Cruz", "staff"),
    "lena": ("Lena Park", "staff"),
    "kevin": ("Kevin Osei", "reviewer"),
}


@dataclass(frozen=True)
class World:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    site: Site
    people: dict[str, Person]

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    def __getitem__(self, key: str) -> Person:
        return self.people[key]

    async def call(
        self,
        method: str,
        path: str,
        who: str | Person,
        body: Mapping[str, object] | None = None,
        *,
        tenant: uuid.UUID | None = None,
    ) -> httpx.Response:
        person = self.people[who] if isinstance(who, str) else who
        return await self.net.call(method, path, person, body=body, tenant=tenant)

    async def call_with(
        self,
        method: str,
        path: str,
        who: str,
        body: Mapping[str, object] | None,
        headers: Mapping[str, str],
    ) -> httpx.Response:
        """A request with extra headers (`Idempotency-Key`)."""
        return await self.net.http.request(
            method, path, json=body, headers={**self.net.headers(self.people[who]), **headers}
        )

    async def stale_mfa(
        self,
        method: str,
        path: str,
        who: str,
        body: Mapping[str, object] | None = None,
        **headers: str,
    ) -> httpx.Response:
        """A request whose second factor was verified an hour ago (past the 900 s window)."""
        person = self.people[who]
        hour_ago = int(system_now().timestamp()) - 3600
        token = self.net.idp.token(person.subject, mfa=True, auth_time=hour_ago)
        return await self.net.http.request(
            method, path, json=body, headers={"Authorization": f"Bearer {token}", **headers}
        )


async def _named(seed: Seeder, tenant_id: uuid.UUID, name: str) -> Person:
    who = await seed.person(tenant_id)
    await seed.run("UPDATE users SET display_name = $1 WHERE id = $2", name, who.user_id)
    return who


async def make_world(net: Net, label: str = "Northwind Robotics 401(k) Plan") -> World:
    seed = net.seed
    tenant_id = await seed.firm()
    for flag in ("review.grammar_api", "review.approve_agent_output", "notifications.v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-04-T28')",
            tenant_id,
            flag,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, label)
    people: dict[str, Person] = {}
    for key, (name, role) in CAST.items():
        people[key] = await _named(seed, tenant_id, name)
        await seed.member(site, people[key], role)
    return World(net, tenant_id, admin, site, people)


async def second_site(world: World, label: str) -> Site:
    """Another client of the same firm, with the whole cast on its engagement."""
    site = await world.seed.site(world.tenant_id, world.admin.user_id, label)
    for key, (_, role) in CAST.items():
        await world.seed.member(site, world[key], role)
    return site


async def agent(
    world: World,
    scope: frozenset[str] = frozenset({"proposal.create", "suggestion.create"}),
    *,
    site: Site | None = None,
    shadow: bool = False,
    agent_id: str = SCREENER,
) -> AgentContext:
    """The agent acting on a recorded run on the site's engagement, for Hannah."""
    where = site or world.site
    run_id = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, finished_at, output, shadow) VALUES ($1, $2, "
        "$3, 1, $4, $5, $6, 'completed', now(), $7, $8)",
        run_id,
        world.tenant_id,
        agent_id,
        where.engagement_id,
        world["hannah"].user_id,
        sorted(scope),
        json.dumps({"reasoning": "Prior-year treatment supports passive."}),
        shadow,
    )
    return await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=run_id,
        agent_id=agent_id,
        engagement_id=where.engagement_id,
        task_scope=scope,
        initiator_user_id=world["hannah"].user_id,
    )


async def cite(world: World, *, site: Site | None = None, verified: bool = True) -> uuid.UUID:
    """A C4 citation on the site's engagement, verified by code (or not)."""
    where = site or world.site
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, locator, verified, verification_reason, "
            "verifier_version, created_by_kind, created_by_run_id) VALUES ($1, $2, "
            "'proposal_probe', $3, 1, 'record_field', 'tax_return', $3, "
            '\'{"record_type": "tax_return", "field": "line"}\', $4, $5, \'v1\', '
            "'agent', $3) RETURNING id",
            world.tenant_id,
            where.engagement_id,
            uuid.uuid4(),
            verified,
            None if verified else "value_mismatch",
        ),
    )


async def outbox(world: World, event_type: str) -> list[OutboxEvent]:
    rows = await world.seed.rows(
        "SELECT id, event_type, payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 "
        "ORDER BY seq",
        world.tenant_id,
        event_type,
    )
    return [
        OutboxEvent(
            row["id"],
            world.tenant_id,
            str(row["event_type"]),
            cast(
                Json,
                json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
            ),
        )
        for row in rows
    ]


async def deliver(world: World, event_type: str) -> int:
    """Every `event_type` row the product wrote, delivered to the notifications handler twice
    (a redelivery), as the relay does."""
    events = await outbox(world, event_type)
    handler = notifications.SUBSCRIPTIONS[event_type]
    for event in events:
        await handler(event)
        await handler(event)
    return len(events)


async def notified(world: World, kind: str) -> list[uuid.UUID]:
    rows = await world.seed.rows(
        "SELECT recipient_user_id FROM notifications WHERE tenant_id = $1 AND kind = $2 "
        "ORDER BY recipient_user_id",
        world.tenant_id,
        kind,
    )
    return [cast(uuid.UUID, r["recipient_user_id"]) for r in rows]


async def audit_rows(world: World, action: str) -> list[tuple[str, str]]:
    rows = await world.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "ORDER BY seq",
        world.tenant_id,
        action,
    )
    return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]
