# ac-test-author: ayushkbhatia
"""The shared C3 Undo conformance suite (P-04-T13; ADR-161 clause 6, DEC-24): one Undo contract,
tested once, for every Undo route that registers here.

For each registered case, decided by a person at T0 with business time frozen on a synthetic
firm: Undo inside 10 seconds (on `kernel.clock`) by the same person succeeds and appends a
compensating row by that person, leaving the decision's own rows in place; Undo after the window,
a second Undo, and Undo by anyone else answer `409 undo_window_closed`; where the decision holds an
effect behind an approval grant, Undo voids the grant, so the single gate (`consume_grant`) never
lets the effect out, and an Undo after the effect started answers `409 effect_started`. The
checks are pure functions over what was observed; `test_the_checks_fail_*` feed them a route that
skips the window or the grant void and require them to say so.

Registered: the evidence review-decision Undo (P-01-T15), the request send, binder publish and
follow-up send Undo (P-06-T17; the follow-up case seeds its published binder, its recipient and
the Reminder template as test data), and the client's Undo of an Ignore and of Mark as Done
(R-01-T08).

Window kinds (DEC-334): a firm decision that holds an effect leaving the firm is undone within
10 seconds (`ten_seconds`). A client's Ignore or Mark as Done holds none, so its Undo stays open
until the firm acts on the request or the binder (`until_firm_acts`; R-01 OQ-2, DEC-240), then
answers `409 firm_already_acted`. Every other check holds for both kinds: one compensating row
by the person who acted, the act's own rows kept, a second Undo refused, nobody else's Undo.
Boundary: `create_app()` over HTTP; seeding as the superuser.
Expectations: ADR-161, `docs/contracts/review-grammar.md` §errors, `docs/contracts/c5-requests-
binders.md` §2, §6, §7, and the P-01 contract for review decisions.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final, Literal, cast

import httpx
import pytest

from abacus.kernel.clock import frozen
from abacus.modules.communications.api import REMINDER_TEMPLATE
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.identity.api import consume_grant
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder

T0: Final = datetime.fromisoformat("2026-09-14T09:42:00-05:00")
TENANT_HEADER: Final = "X-Abacus-Tenant"


@dataclass
class World:
    seed: Seeder
    http: httpx.AsyncClient
    idp: FakeIdentityProvider
    tenant: uuid.UUID
    engagement: uuid.UUID
    decider: Person
    other: Person
    # The firm's partner on the engagement; for a client case, `decider` and `other` are clients.
    firm: Person | None = None
    state: dict[str, uuid.UUID] = field(default_factory=dict[str, uuid.UUID])

    async def call(
        self,
        who: Person,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        *,
        at: datetime,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.idp.token(who.subject)}",
            TENANT_HEADER: str(self.tenant),
            "Idempotency-Key": uuid.uuid4().hex,
        }
        with frozen(at):
            return await self.http.request(method, path, json=body or {}, headers=headers)


@dataclass(frozen=True)
class Case:
    """One Undo route. `compensations` lists the actor of each compensating row the Undo wrote;
    `decided` counts the decision's own rows (which an Undo must never remove); `grant` names the
    grant holding the decision's effect, when it has one. A `client` case's people are two client
    principals on the engagement (an engagement-scope owner grant each); `firm_acts` is the
    firm's act that closes an `until_firm_acts` window."""

    name: str
    registered_by: str
    flags: tuple[str, ...]
    prepare: Callable[[World], Awaitable[None]]
    decide: Callable[[World, Person, datetime], Awaitable[httpx.Response]]
    undo: Callable[[World, Person, datetime], Awaitable[httpx.Response]]
    compensations: Callable[[World], Awaitable[list[str]]]
    decided: Callable[[World], Awaitable[int]]
    grant: Callable[[World], Awaitable[uuid.UUID | None]] | None = None
    window: Literal["ten_seconds", "until_firm_acts"] = "ten_seconds"
    client: bool = False
    firm_acts: Callable[[World, datetime], Awaitable[httpx.Response]] | None = None


# --- the evidence review decision (P-01-T13, registered by P-01-T15) -----------------------------


async def _review_prepare(world: World) -> None:
    seed, tenant, engagement = world.seed, world.tenant, world.engagement
    list_id = await seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
        tenant,
        engagement,
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by, status) VALUES ($1, $2, $3, 'Certified trust report', "
            "'Investments', $4, 'uploaded') RETURNING id",
            tenant,
            engagement,
            list_id,
            world.decider.user_id,
        ),
    )
    evidence = await seed.value(
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
            evidence,
            fingerprint,
            f"tenants/{tenant}/sha256/{fingerprint}",
        ),
    )
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagement,
        item,
        version,
    )
    world.state.update(item=item, version=version)


async def _review_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    response = await world.call(
        who,
        "POST",
        f"/v1/engagements/{world.engagement}/evidence-versions/{world.state['version']}"
        "/decision/accept",
        at=at,
    )
    if response.status_code == 201:
        world.state["decision"] = uuid.UUID(response.json()["id"])
    return response


async def _review_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who,
        "POST",
        f"/v1/engagements/{world.engagement}/review-decisions/{world.state['decision']}/undo",
        at=at,
    )


async def _review_compensations(world: World) -> list[str]:
    rows = await world.seed.rows(
        "SELECT actor_id FROM review_decisions WHERE undoes_decision_id = $1",
        world.state["decision"],
    )
    return [str(r["actor_id"]) for r in rows]


async def _review_decided(world: World) -> int:
    return int(
        cast(
            int,
            await world.seed.value(
                "SELECT count(*) FROM review_decisions WHERE id = $1", world.state["decision"]
            ),
        )
    )


REVIEW_DECISION: Final = Case(
    "evidence_review_decision",
    "P-01-T15",
    (),
    _review_prepare,
    _review_decide,
    _review_undo,
    _review_compensations,
    _review_decided,
)


# --- the request send and the binder publish (P-06-T10, P-06-T07; registered by P-06-T17) ------


async def _binder(world: World, kind: str) -> uuid.UUID:
    work_item = await world.seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", world.engagement
    )
    response = await world.call(
        world.decider,
        "POST",
        "/v1/binders",
        {"work_item_id": str(work_item), "kind": kind, "name": "2025 Binder"},
        at=T0 - timedelta(minutes=5),
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _request(world: World, binder: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by, client_visible, due_on) VALUES ($1, $2, $3, "
            "'Brokerage statements', 'Income', $4, false, '2026-10-01') RETURNING id",
            world.tenant,
            world.engagement,
            binder,
            world.decider.user_id,
        ),
    )


async def _send_prepare(world: World) -> None:
    binder = await _binder(world, "pbc")
    world.state.update(binder=binder, item=await _request(world, binder))


async def _send_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who,
        "POST",
        f"/v1/engagements/{world.engagement}/request-items/{world.state['item']}/send",
        at=at,
    )


async def _send_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who,
        "POST",
        f"/v1/engagements/{world.engagement}/request-items/{world.state['item']}/send/undo",
        at=at,
    )


async def _audited(world: World, action: str, target: uuid.UUID) -> list[str]:
    rows = await world.seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "AND target_id = $3",
        world.tenant,
        action,
        str(target),
    )
    return [str(r["actor_id"]) for r in rows]


async def _held_grant(
    world: World, event_type: str, key: str, subject: uuid.UUID
) -> uuid.UUID | None:
    rows = await world.seed.rows(
        "SELECT grant_id FROM outbox WHERE tenant_id = $1 AND event_type = $2 "
        "AND payload->>$3 = $4 AND grant_id IS NOT NULL",
        world.tenant,
        event_type,
        key,
        str(subject),
    )
    return cast(uuid.UUID, rows[0]["grant_id"]) if rows else None


async def _send_compensations(world: World) -> list[str]:
    return await _audited(world, "request_item.send_undone", world.state["item"])


async def _send_decided(world: World) -> int:
    return len(await _audited(world, "request_item.sent", world.state["item"]))


async def _send_grant(world: World) -> uuid.UUID | None:
    return await _held_grant(world, "request_item.sent", "request_item_id", world.state["item"])


SEND: Final = Case(
    "request_item_send",
    "P-06-T17",
    ("binders.engine",),
    _send_prepare,
    _send_decide,
    _send_undo,
    _send_compensations,
    _send_decided,
    _send_grant,
)


async def _publish_prepare(world: World) -> None:
    binder = await _binder(world, "intake")  # intake publishes before G3 (C5 §6)
    world.state.update(binder=binder, item=await _request(world, binder))


async def _publish_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(who, "POST", f"/v1/binders/{world.state['binder']}/publish", at=at)


async def _publish_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who, "POST", f"/v1/binders/{world.state['binder']}/publish/undo", at=at
    )


async def _publish_compensations(world: World) -> list[str]:
    return await _audited(world, "binder.publish_undone", world.state["binder"])


async def _publish_decided(world: World) -> int:
    return len(await _audited(world, "binder.published", world.state["binder"]))


async def _publish_grant(world: World) -> uuid.UUID | None:
    return await _held_grant(world, "binder.published", "binder_id", world.state["binder"])


PUBLISH: Final = Case(
    "binder_publish",
    "P-06-T17",
    ("binders.engine",),
    _publish_prepare,
    _publish_decide,
    _publish_undo,
    _publish_compensations,
    _publish_decided,
    _publish_grant,
)

# --- the follow-up send (P-06-T14, registered by P-06-T17) ---------------------------------------

# Test data imported through the platform's import path as staff would (the product holds no
# template text, AGENTS 16); one content, so importing it again writes nothing.
_REMINDER_SUBJECT: Final = "{{firm_name}} is still waiting on {{engagement_display_name}}"
_REMINDER_BODY: Final = (
    "Hi {{recipient_first_name}},\n\n{{firm_name}} is still waiting for the following:\n\n"
    "{{request_list}}\n\nOpen your list: {{app_link}}\n"
)
_REMINDER_VARIABLES: Final = [
    "app_link",
    "engagement_display_name",
    "firm_name",
    "recipient_first_name",
    "request_list",
]


async def _follow_up_prepare(world: World) -> None:
    """A published binder with one requested, client-visible item, a client admin to remind, and
    the follow-up drafted for them before T0."""
    await import_platform_version(
        "staff-undo-suite",
        REMINDER_TEMPLATE,
        "en-US",
        _REMINDER_SUBJECT,
        _REMINDER_BODY,
        _REMINDER_VARIABLES,
    )
    await world.seed.client(world.tenant, world.engagement, "Claire Feld")
    work_item = await world.seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", world.engagement
    )
    created = await world.call(
        world.decider,
        "POST",
        "/v1/binders",
        {"work_item_id": str(work_item), "kind": "organizer", "name": "2025 Binder"},
        at=T0 - timedelta(minutes=5),
    )
    assert created.status_code == 201, created.text
    binder = uuid.UUID(created.json()["id"])
    await world.seed.run(
        "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
        "audit_area, created_by, client_visible, due_on, status, requested_at) VALUES ($1, $2, "
        "$3, 'Brokerage statements', 'Income', $4, true, '2026-09-01', 'requested', $5)",
        world.tenant,
        world.engagement,
        binder,
        world.decider.user_id,
        T0 - timedelta(minutes=4),
    )
    await world.seed.run(
        "UPDATE request_lists SET status = 'published', published_at = $2, published_by = $3 "
        "WHERE id = $1",
        binder,
        T0 - timedelta(minutes=4),
        world.decider.user_id,
    )
    drafted = await world.call(
        world.decider,
        "POST",
        "/v1/follow-ups/drafts",
        {"binder_ids": [str(binder)]},
        at=T0 - timedelta(minutes=1),
    )
    assert drafted.status_code == 201, drafted.text
    items = drafted.json()["items"]
    assert len(items) == 1, items
    world.state.update(binder=binder, follow_up=uuid.UUID(items[0]["id"]))


async def _follow_up_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(who, "POST", f"/v1/follow-ups/{world.state['follow_up']}/send", at=at)


async def _follow_up_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(who, "POST", f"/v1/follow-ups/{world.state['follow_up']}/undo", at=at)


async def _follow_up_compensations(world: World) -> list[str]:
    return await _audited(world, "follow_up.undone", world.state["follow_up"])


async def _follow_up_decided(world: World) -> int:
    return len(await _audited(world, "follow_up.sent", world.state["follow_up"]))


async def _follow_up_grant(world: World) -> uuid.UUID | None:
    return await _held_grant(world, "follow_up.sent", "follow_up_id", world.state["follow_up"])


FOLLOW_UP: Final = Case(
    "follow_up_send",
    "P-06-T17",
    ("binders.engine",),
    _follow_up_prepare,
    _follow_up_decide,
    _follow_up_undo,
    _follow_up_compensations,
    _follow_up_decided,
    _follow_up_grant,
)

# --- the client's Undo of an Ignore and of Mark as Done (R-01-T08) -------------------------------


async def _client_binder(world: World) -> None:
    """A published binder with one client-visible request, as the firm left it."""
    assert world.firm is not None
    work_item = await world.seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", world.engagement
    )
    created = await world.call(
        world.firm,
        "POST",
        "/v1/binders",
        {"work_item_id": str(work_item), "kind": "organizer", "name": "2025 Binder"},
        at=T0 - timedelta(minutes=5),
    )
    assert created.status_code == 201, created.text
    binder = uuid.UUID(created.json()["id"])
    item = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by, client_visible, due_on) VALUES ($1, $2, $3, "
            "'2025 Form 1099-B', 'Income', $4, true, '2026-10-01') RETURNING id",
            world.tenant,
            world.engagement,
            binder,
            world.firm.user_id,
        ),
    )
    await world.seed.run(
        "UPDATE request_lists SET status = 'published', published_at = $2, published_by = $3 "
        "WHERE id = $1",
        binder,
        T0 - timedelta(minutes=4),
        world.firm.user_id,
    )
    await world.seed.run(
        "UPDATE request_items SET status = 'requested', requested_at = $2 WHERE id = $1",
        item,
        T0 - timedelta(minutes=4),
    )
    world.state.update(binder=binder, item=item)


async def _ignore_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who,
        "POST",
        f"/v1/portal/request-items/{world.state['item']}/ignore",
        {"reason": "not_this_year"},
        at=at,
    )


async def _ignore_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who, "POST", f"/v1/portal/request-items/{world.state['item']}/ignore/undo", at=at
    )


async def _ignore_compensations(world: World) -> list[str]:
    return await _audited(world, "request_item.ignore_undone", world.state["item"])


async def _ignore_decided(world: World) -> int:
    return len(await _audited(world, "request_item.ignored", world.state["item"]))


async def _waive(world: World, at: datetime) -> httpx.Response:
    """The firm waives the request (Kevin's "not applicable")."""
    assert world.firm is not None
    return await world.call(
        world.firm,
        "POST",
        f"/v1/engagements/{world.engagement}/request-items/{world.state['item']}/waive",
        {"na_reason": "not_applicable_this_year", "note": "Not needed this year"},
        at=at,
    )


IGNORE: Final = Case(
    "client_ignore",
    "R-01-T08",
    ("binders.engine",),
    _client_binder,
    _ignore_decide,
    _ignore_undo,
    _ignore_compensations,
    _ignore_decided,
    window="until_firm_acts",
    client=True,
    firm_acts=_waive,
)


async def _done_decide(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who, "POST", f"/v1/portal/binders/{world.state['binder']}/mark-done", at=at
    )


async def _done_undo(world: World, who: Person, at: datetime) -> httpx.Response:
    return await world.call(
        who, "POST", f"/v1/portal/binders/{world.state['binder']}/mark-done/undo", at=at
    )


async def _done_compensations(world: World) -> list[str]:
    return await _audited(world, "binder.mark_done_undone", world.state["binder"])


async def _done_decided(world: World) -> int:
    return len(await _audited(world, "binder.marked_done", world.state["binder"]))


MARK_DONE: Final = Case(
    "client_mark_done",
    "R-01-T08",
    ("binders.engine",),
    _client_binder,
    _done_decide,
    _done_undo,
    _done_compensations,
    _done_decided,
    window="until_firm_acts",
    client=True,
    firm_acts=_waive,
)

CASES: Final = (REVIEW_DECISION, SEND, PUBLISH, FOLLOW_UP, IGNORE, MARK_DONE)
GRANT_HELD: Final = tuple(c for c in CASES if c.grant is not None)
TEN_SECONDS: Final = tuple(c for c in CASES if c.window == "ten_seconds")
UNTIL_FIRM_ACTS: Final = tuple(c for c in CASES if c.window == "until_firm_acts")


# --- the contract's checks, over what was observed -----------------------------------------------


@dataclass(frozen=True)
class Observed:
    decided_status: int
    undo_status: int
    decider: str
    compensations: list[str]
    decided_before: int
    decided_after: int


def undo_problems(seen: Observed) -> list[str]:
    found: list[str] = []
    if seen.decided_status not in (200, 201, 202):
        found.append(f"the decision answered {seen.decided_status}")
    if seen.undo_status not in (200, 201):
        found.append(f"Undo inside the window answered {seen.undo_status}")
    if seen.compensations != [seen.decider]:
        found.append(f"compensating rows by {seen.compensations}, not one by the decider")
    if seen.decided_after < seen.decided_before or seen.decided_before == 0:
        found.append("the decision's own rows were removed")
    return found


def refusal_problems(response: httpx.Response, code: str) -> list[str]:
    if response.status_code == 409 and response.json() == {"detail": code}:
        return []
    return [f"{response.status_code} {response.text}, not 409 {code}"]


async def grant_problems(world: World, grant: uuid.UUID | None) -> list[str]:
    """A voided grant lets nothing out: `consume_grant` refuses it with its own payload."""
    if grant is None:
        return ["the decision's effect is not held behind a grant"]
    rows = await world.seed.rows(
        "SELECT voided_at, used_at, payload_sha256 FROM approval_grants WHERE id = $1", grant
    )
    found: list[str] = []
    if rows[0]["voided_at"] is None:
        found.append("Undo did not void the grant")
    with frozen(T0 + timedelta(seconds=30)):
        if await consume_grant(world.tenant, grant, uuid.uuid4(), str(rows[0]["payload_sha256"])):
            found.append("the voided grant let the effect out")
    return found


# --- fixtures ------------------------------------------------------------------------------------


async def _world(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> World:
    tenant = await seed.firm(*case.flags)
    hannah = await seed.person(tenant, "Hannah Leclerc")
    marcus = await seed.person(tenant, "Marcus Webb")
    engagement = await seed.engagement(tenant, hannah)
    await seed.member(engagement, hannah, "engagement_partner")
    await seed.member(engagement, marcus, "engagement_partner")
    world = World(seed, http, idp, tenant, engagement, hannah, marcus)
    if case.client:
        claire = await seed.client(tenant, engagement, "Claire Feld")
        jonah = await seed.client(tenant, engagement, "Jonah Feld")
        world = World(seed, http, idp, tenant, engagement, claire, jonah, hannah)
    await case.prepare(world)
    return world


async def _decided(world: World, case: Case) -> tuple[httpx.Response, int]:
    response = await case.decide(world, world.decider, T0)
    assert response.status_code in (200, 201, 202), (case.name, response.text)
    return response, await case.decided(world)


def _ids(cases: tuple[Case, ...]) -> list[str]:
    return [f"{c.name}[{c.registered_by}]" for c in cases]


# --- the contract, per registered route ----------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
async def test_c3_undo_inside_ten_seconds_appends_a_compensating_row_by_the_same_person(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    world = await _world(seed, http, idp, case)
    decided, before = await _decided(world, case)
    undone = await case.undo(world, world.decider, T0 + timedelta(seconds=8))
    seen = Observed(
        decided.status_code,
        undone.status_code,
        str(world.decider.user_id),
        await case.compensations(world),
        before,
        await case.decided(world),
    )
    assert undo_problems(seen) == [], undone.text


@pytest.mark.parametrize("case", TEN_SECONDS, ids=_ids(TEN_SECONDS))
async def test_c3_undo_after_ten_seconds_is_409_undo_window_closed(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    late = await case.undo(world, world.decider, T0 + timedelta(seconds=11))
    assert refusal_problems(late, "undo_window_closed") == []
    assert await case.compensations(world) == []


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
async def test_c3_only_the_person_who_decided_may_undo(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    """ADR-161 clause 6 and P-01 AC 3.1.4: Undo is the decider's alone. Another partner on the
    team is refused and nothing is written: C3 answers 409 `undo_window_closed` (review-grammar.md
    §errors); P-01 names no code for the review decision, which answers 403 `forbidden`."""
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    other = await case.undo(world, world.other, T0 + timedelta(seconds=5))
    assert refusal_problems(other, "undo_window_closed") == [] or (
        other.status_code,
        other.json(),
    ) == (403, {"detail": "forbidden"}), other.text
    assert await case.compensations(world) == []


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
async def test_c3_a_second_undo_is_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    first = await case.undo(world, world.decider, T0 + timedelta(seconds=4))
    assert first.status_code in (200, 201), first.text
    again = await case.undo(world, world.decider, T0 + timedelta(seconds=6))
    assert again.status_code == 409, again.text
    assert len(await case.compensations(world)) == 1


@pytest.mark.parametrize("case", UNTIL_FIRM_ACTS, ids=_ids(UNTIL_FIRM_ACTS))
async def test_c3_a_client_undo_outlives_ten_seconds(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    """DEC-334: nothing leaves the firm, so the client's Undo is open an hour later."""
    world = await _world(seed, http, idp, case)
    decided, before = await _decided(world, case)
    undone = await case.undo(world, world.decider, T0 + timedelta(hours=1))
    seen = Observed(
        decided.status_code,
        undone.status_code,
        str(world.decider.user_id),
        await case.compensations(world),
        before,
        await case.decided(world),
    )
    assert undo_problems(seen) == [], undone.text


@pytest.mark.parametrize("case", UNTIL_FIRM_ACTS, ids=_ids(UNTIL_FIRM_ACTS))
async def test_c3_a_client_undo_after_the_firm_acted_is_409_firm_already_acted(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    """DEC-24, R-01 Stories 3.1 and 4.1: once the firm has acted, the Undo is closed and nothing
    is written."""
    assert case.firm_acts is not None
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    acted = await case.firm_acts(world, T0 + timedelta(minutes=1))
    assert acted.status_code in (200, 201), acted.text
    late = await case.undo(world, world.decider, T0 + timedelta(minutes=2))
    assert (late.status_code, late.json()["detail"]) == (409, "firm_already_acted"), late.text
    assert await case.compensations(world) == []


@pytest.mark.parametrize("case", GRANT_HELD, ids=_ids(GRANT_HELD))
async def test_c3_undo_voids_the_grant_and_the_effect_never_leaves(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    assert case.grant is not None
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    grant = await case.grant(world)
    undone = await case.undo(world, world.decider, T0 + timedelta(seconds=8))
    assert undone.status_code in (200, 201), undone.text
    assert await grant_problems(world, grant) == []


@pytest.mark.parametrize("case", GRANT_HELD, ids=_ids(GRANT_HELD))
async def test_c3_undo_after_the_effect_started_is_409_effect_started(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, case: Case
) -> None:
    """The dispatcher consumed the grant at `not_before` (T0 + 10 s, on its clock); an Undo that
    reaches the server stamped before the window's end still finds the effect started."""
    assert case.grant is not None
    world = await _world(seed, http, idp, case)
    await _decided(world, case)
    grant = await case.grant(world)
    assert grant is not None
    payload = await seed.value("SELECT payload_sha256 FROM approval_grants WHERE id = $1", grant)
    with frozen(T0 + timedelta(seconds=10)):
        assert await consume_grant(world.tenant, grant, uuid.uuid4(), str(payload))
    started = await case.undo(world, world.decider, T0 + timedelta(seconds=9))
    assert refusal_problems(started, "effect_started") == []


# --- the checks catch a route that breaks the contract -------------------------------------------


def test_the_checks_fail_a_route_that_skips_the_window() -> None:
    late = httpx.Response(200, json={"id": str(uuid.uuid4())})
    assert refusal_problems(late, "undo_window_closed") != []


def test_the_checks_fail_an_undo_that_deletes_or_is_by_someone_else() -> None:
    deleted = Observed(201, 200, "hannah", ["hannah"], 1, 0)
    assert undo_problems(deleted) != []
    by_another = Observed(201, 200, "hannah", ["marcus"], 1, 1)
    assert undo_problems(by_another) != []
    nothing = Observed(201, 200, "hannah", [], 1, 1)
    assert undo_problems(nothing) != []


async def test_the_checks_fail_an_undo_that_leaves_the_grant_live(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    world = await _world(seed, http, idp, SEND)
    await _decided(world, SEND)
    grant = await _send_grant(world)  # decided, never undone: a route that skipped the void
    assert await grant_problems(world, grant) != []
