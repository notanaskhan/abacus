# ac-test-author: ayushkbhatia
"""P-04 F9 (C13; P-04-T17, TASK-1279): the human-gate projection a consumer reads.

What F9 and the contract promise, tested from outside the projector:
- the same outbox event delivered twice leaves `human_gates` unchanged, and a full rebuild from
  the owners' records yields the same rows (idempotent on the event; DEC-320 "reconcile, not
  replay");
- a walled person is never counted or listed a gate of the walled client (INV-3, SPEC-002), and
  another firm sees nothing;
- one query yields Daniel Reyes's 11 = 3 + 6 + 2 as `counts` per DF-25 kind
  (`docs/contracts/review-grammar.md`, "Home");
- the agent's typed proposals (`screening_results`, `upload_reviews`, `guidance_drafts`) project
  as `proposal` gates (DEC-28), and a person's decision on the version closes them.

Boundary: `create_app()` over HTTP for the read (`GET /v1/human-gates` behind
`review.grammar_api`); the projector is driven as the worker drives it, through
`review.api.SUBSCRIPTIONS` with the outbox rows the product wrote (or, for a consumer's own
source, an event of the fixed C13 set), and `review.api.rebuild_human_gates`. Decisions, sign-off
requests and exports have no owner on main yet (DEC-320: they register in I-01 and the P-04
services), so this suite registers a consumer's sources through the public slot
(`register_gate_source`), as I-01 will.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import (
    C13_EVENTS,
    SUBSCRIPTIONS,
    GateSource,
    OpenGate,
    rebuild_human_gates,
    register_gate_source,
)

from .support import Json, Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

GATES: Final = "/v1/human-gates"

# A consumer's own gates (I-01's decisions, sign-off requests and exports), keyed by firm: what
# the owner says waits on a person now. Firms this suite didn't make have none.
_WAITING: dict[uuid.UUID, list[OpenGate]] = {}


def _open_for(
    subject_type: str,
) -> Callable[[TenantContext, uuid.UUID | None], Awaitable[list[OpenGate]]]:
    async def open_for(tenant: TenantContext, engagement_id: uuid.UUID | None) -> list[OpenGate]:
        return [
            g
            for g in _WAITING.get(tenant.tenant_id, [])
            if _TYPE_OF.get(g.subject_id) == subject_type
            and (engagement_id is None or g.engagement_id == engagement_id)
        ]

    return open_for


_TYPE_OF: dict[uuid.UUID, str] = {}
# subject type -> (DF-25 kind, the read action that admits a person to its subjects)
CONSUMER: Final = {
    "consumer_decision": ("decision", "decision.read"),
    "consumer_sign_off_request": ("sign_off_request", "sign_off.read"),
    "consumer_export": ("export", "decision.read"),
}
for _type, (_kind, _read) in CONSUMER.items():
    register_gate_source(GateSource(_type, _kind, _read, frozenset(C13_EVENTS), _open_for(_type)))


def _waiting(
    firm: uuid.UUID,
    subject_type: str,
    engagement_id: uuid.UUID,
    *,
    assignee: Person | None = None,
    due_on: date | None = None,
) -> uuid.UUID:
    subject = uuid.uuid4()
    _TYPE_OF[subject] = subject_type
    _WAITING.setdefault(firm, []).append(
        OpenGate(
            subject,
            engagement_id,
            assignee_user_id=assignee.user_id if assignee else None,
            due_on=due_on,
        )
    )
    return subject


def _settle(firm: uuid.UUID, subject: uuid.UUID) -> None:
    _WAITING[firm] = [g for g in _WAITING[firm] if g.subject_id != subject]


def _event(
    firm: uuid.UUID, engagement_id: uuid.UUID, event_id: uuid.UUID | None = None
) -> OutboxEvent:
    """A C13 event about an engagement, as the relay hands it to the projector."""
    return OutboxEvent(
        event_id or uuid.uuid4(),
        firm,
        "review_decision.recorded",
        {"engagement_id": str(engagement_id), "evidence_version_id": str(uuid.uuid4())},
    )


async def _deliver(event: OutboxEvent) -> None:
    await SUBSCRIPTIONS[event.event_type](event)


async def _replay_outbox(seed: Seeder, firm: uuid.UUID) -> int:
    """Every C13 event the product wrote for the firm, in order, as the worker delivers them."""
    rows = await seed.rows(
        "SELECT id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = ANY($2::text[]) ORDER BY seq",
        firm,
        sorted(C13_EVENTS),
    )
    for row in rows:
        payload = row["payload"]
        await _deliver(
            OutboxEvent(
                row["id"],
                firm,
                str(row["event_type"]),
                cast(Json, json.loads(payload) if isinstance(payload, str) else payload),
            )
        )
    return len(rows)


async def _stored(seed: Seeder, firm: uuid.UUID) -> list[tuple[object, ...]]:
    rows = await seed.rows(
        "SELECT id, kind, subject_ref::text, engagement_id, assignee_user_id, due_on, state, "
        "source_event_id, updated_at FROM human_gates WHERE tenant_id = $1 ORDER BY id",
        firm,
    )
    return [tuple(r.values()) for r in rows]


async def _open_rows(seed: Seeder, firm: uuid.UUID) -> set[tuple[object, ...]]:
    rows = await seed.rows(
        "SELECT kind, subject_ref::text, engagement_id, assignee_user_id, due_on FROM "
        "human_gates WHERE tenant_id = $1 AND state = 'open'",
        firm,
    )
    return {tuple(r.values()) for r in rows}


async def _projected_audits(seed: Seeder, firm: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'human_gate.projected'",
            firm,
        ),
    )


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    daniel: Person  # Daniel Reyes, engagement partner on both clients
    lena: Person  # Lena Park, staff on both; walled from Ashford in the wall tests
    hannah: Person  # another manager on both; never walled
    ashford: Site
    bayside: Site

    async def gates(self, who: Person, query: str = "?assignee=me") -> tuple[int, Json]:
        response = await self.net.call("GET", f"{GATES}{query}", who)
        return response.status_code, cast(Json, response.json())


async def _firm(net: Net, *, flag: bool = True) -> Firm:
    seed = net.seed
    tenant_id = await seed.firm()
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'P-04-T17')",
            tenant_id,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    daniel = await seed.person(tenant_id)
    lena = await seed.person(tenant_id)
    hannah = await seed.person(tenant_id)
    ashford = await seed.site(tenant_id, admin.user_id, "Ashford")
    bayside = await seed.site(tenant_id, admin.user_id, "Bayside")
    for site in (ashford, bayside):
        await seed.member(site, daniel, "engagement_partner")
        await seed.member(site, lena, "staff")
        await seed.member(site, hannah, "manager")
    return Firm(net, tenant_id, admin, daniel, lena, hannah, ashford, bayside)


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net)


def _nonzero(counts: object) -> dict[str, int]:
    return {k: v for k, v in cast(dict[str, int], counts).items() if v}


async def _daniels_eleven(f: Firm) -> dict[str, list[uuid.UUID]]:
    """3 decisions, 6 sign-off requests and 2 exports on Daniel across both clients; plus one
    of each kind on Hannah, which never counts for Daniel."""
    made: dict[str, list[uuid.UUID]] = {"decision": [], "sign_off_request": [], "export": []}
    plan = (
        ("consumer_decision", f.ashford, 2),
        ("consumer_decision", f.bayside, 1),
        ("consumer_sign_off_request", f.ashford, 4),
        ("consumer_sign_off_request", f.bayside, 2),
        ("consumer_export", f.bayside, 2),
    )
    for subject_type, site, n in plan:
        for _ in range(n):
            made[CONSUMER[subject_type][0]].append(
                _waiting(f.tenant_id, subject_type, site.engagement_id, assignee=f.daniel)
            )
    for subject_type in CONSUMER:
        _waiting(f.tenant_id, subject_type, f.bayside.engagement_id, assignee=f.hannah)
    for site in (f.ashford, f.bayside):
        await _deliver(_event(f.tenant_id, site.engagement_id))
    return made


# --- F9 story 3 (contract "Home"): one query, 11 = 3 + 6 + 2 -------------------------------


async def test_ac_f9_home_one_query_reads_daniels_eleven_as_three_six_two(firm: Firm) -> None:
    await _daniels_eleven(firm)
    status, page = await firm.gates(firm.daniel)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"decision": 3, "sign_off_request": 6, "export": 2}
    assert sum(_nonzero(page["counts"]).values()) == 11
    assert page["total"] == 11
    items = cast(list[Json], page["items"])
    assert len(items) == 11
    assert {i["assignee_user_id"] for i in items} == {str(firm.daniel.user_id)}
    assert {i["state"] for i in items} == {"open"}
    by_kind = {k: sum(1 for i in items if i["kind"] == k) for k in ("decision", "export")}
    assert by_kind == {"decision": 3, "export": 2}


async def test_ac_f9_home_hannahs_gates_never_count_for_daniel_and_hers_are_hers(
    firm: Firm,
) -> None:
    await _daniels_eleven(firm)
    status, page = await firm.gates(firm.hannah)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"decision": 1, "sign_off_request": 1, "export": 1}
    assert page["total"] == 3


async def test_ac_f9_home_an_unassigned_gate_waits_on_everyone_who_may_read_it(
    firm: Firm,
) -> None:
    _waiting(firm.tenant_id, "consumer_decision", firm.bayside.engagement_id)
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    for who in (firm.daniel, firm.hannah, firm.lena):
        status, page = await firm.gates(who)
        assert status == 200, page
        assert _nonzero(page["counts"]) == {"decision": 1}, who


async def test_ac_f9_home_kind_and_engagement_filters_narrow_the_list(firm: Firm) -> None:
    await _daniels_eleven(firm)
    status, page = await firm.gates(firm.daniel, "?assignee=me&kind=decision")
    assert status == 200, page
    assert {i["kind"] for i in cast(list[Json], page["items"])} == {"decision"}
    assert len(cast(list[Json], page["items"])) == 3
    status, page = await firm.gates(
        firm.daniel, f"?assignee=me&engagement_id={firm.bayside.engagement_id}"
    )
    assert status == 200, page
    items = cast(list[Json], page["items"])
    assert {i["engagement_id"] for i in items} == {str(firm.bayside.engagement_id)}
    assert len(items) == 1 + 2 + 2


async def test_ac_f9_home_pages_with_a_cursor_cover_the_eleven_once(firm: Firm) -> None:
    await _daniels_eleven(firm)
    seen: list[str] = []
    query = "?assignee=me&limit=4"
    for _ in range(5):
        status, page = await firm.gates(firm.daniel, query)
        assert status == 200, page
        seen.extend(str(i["id"]) for i in cast(list[Json], page["items"]))
        cursor = page.get("next_cursor")
        if not cursor:
            break
        query = f"?assignee=me&limit=4&cursor={cursor}"
    assert len(seen) == 11 and len(set(seen)) == 11


# --- F9 story 1: idempotent on the event; a rebuild yields the same rows ---------------------


async def test_ac_f9_1_the_same_event_delivered_twice_leaves_human_gates_unchanged(
    firm: Firm,
) -> None:
    await _daniels_eleven(firm)
    event = _event(firm.tenant_id, firm.ashford.engagement_id)
    await _deliver(event)
    before = await _stored(firm.net.seed, firm.tenant_id)
    audits = await _projected_audits(firm.net.seed, firm.tenant_id)
    await _deliver(event)
    await _deliver(event)
    assert await _stored(firm.net.seed, firm.tenant_id) == before
    assert await _projected_audits(firm.net.seed, firm.tenant_id) == audits


async def test_ac_f9_1_a_new_subject_after_a_redelivery_is_projected_once(firm: Firm) -> None:
    await _daniels_eleven(firm)
    _waiting(firm.tenant_id, "consumer_export", firm.ashford.engagement_id, assignee=firm.daniel)
    event = _event(firm.tenant_id, firm.ashford.engagement_id)
    await _deliver(event)
    await _deliver(event)
    status, page = await firm.gates(firm.daniel)
    assert status == 200, page
    assert _nonzero(page["counts"])["export"] == 3
    rows = await firm.net.seed.rows(
        "SELECT count(*) AS n FROM human_gates WHERE tenant_id = $1 GROUP BY subject_ref "
        "HAVING count(*) > 1",
        firm.tenant_id,
    )
    assert rows == []


async def test_ac_f9_1_a_projection_that_changes_rows_is_audited_by_the_system(
    firm: Firm,
) -> None:
    await _daniels_eleven(firm)
    rows = await firm.net.seed.rows(
        "SELECT actor_kind, target_type, target_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'human_gate.projected'",
        firm.tenant_id,
    )
    assert rows, "a projection that wrote rows is audited"
    assert {r["actor_kind"] for r in rows} == {"system"}
    assert {str(r["target_id"]) for r in rows} <= {
        str(firm.ashford.engagement_id),
        str(firm.bayside.engagement_id),
    }


async def test_ac_f9_1_a_rebuild_with_nothing_changed_writes_nothing(firm: Firm) -> None:
    await _daniels_eleven(firm)
    before = await _stored(firm.net.seed, firm.tenant_id)
    assert await rebuild_human_gates(firm.tenant_id) == 0
    assert await _stored(firm.net.seed, firm.tenant_id) == before


async def test_ac_f9_1_a_full_rebuild_from_nothing_yields_the_same_rows(firm: Firm) -> None:
    await _daniels_eleven(firm)
    before = await _open_rows(firm.net.seed, firm.tenant_id)
    status, read_before = await firm.gates(firm.daniel)
    assert status == 200
    await firm.net.seed.run("DELETE FROM human_gates WHERE tenant_id = $1", firm.tenant_id)
    assert await rebuild_human_gates(firm.tenant_id) == len(before)
    assert await _open_rows(firm.net.seed, firm.tenant_id) == before
    status, read_after = await firm.gates(firm.daniel)
    assert status == 200
    assert read_after["counts"] == read_before["counts"]
    assert read_after["total"] == read_before["total"] == 11


async def test_ac_f9_1_events_out_of_order_or_late_converge_on_the_owners_state(
    firm: Firm,
) -> None:
    """Payloads are never trusted for state (DEC-320): an old event delivered after a newer one
    leaves what the owner says now."""
    subjects = await _daniels_eleven(firm)
    old = _event(firm.tenant_id, firm.bayside.engagement_id)
    _settle(firm.tenant_id, subjects["export"][0])
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    await _deliver(old)
    status, page = await firm.gates(firm.daniel)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"decision": 3, "sign_off_request": 6, "export": 1}


async def test_ac_f9_1_a_settled_subject_goes_done_and_a_returned_one_reopens_its_row(
    firm: Firm,
) -> None:
    subjects = await _daniels_eleven(firm)
    decision = subjects["decision"][0]
    gone = next(g for g in _WAITING[firm.tenant_id] if g.subject_id == decision)
    row_before = await firm.net.seed.rows(
        "SELECT id FROM human_gates WHERE tenant_id = $1 AND subject_ref->>'id' = $2",
        firm.tenant_id,
        str(decision),
    )
    _settle(firm.tenant_id, decision)
    await _deliver(_event(firm.tenant_id, gone.engagement_id))
    states = await firm.net.seed.rows(
        "SELECT id, state FROM human_gates WHERE tenant_id = $1 AND subject_ref->>'id' = $2",
        firm.tenant_id,
        str(decision),
    )
    assert [(r["id"], r["state"]) for r in states] == [(row_before[0]["id"], "done")]
    status, page = await firm.gates(firm.daniel)
    assert _nonzero(page["counts"])["decision"] == 2 and page["total"] == 10
    _WAITING[firm.tenant_id].append(gone)
    await _deliver(_event(firm.tenant_id, gone.engagement_id))
    states = await firm.net.seed.rows(
        "SELECT id, state FROM human_gates WHERE tenant_id = $1 AND subject_ref->>'id' = $2",
        firm.tenant_id,
        str(decision),
    )
    assert [(r["id"], r["state"]) for r in states] == [(row_before[0]["id"], "open")]
    status, page = await firm.gates(firm.daniel)
    assert status == 200 and page["total"] == 11


async def test_ac_f9_1_a_voided_gate_stays_voided_through_events_and_rebuilds(
    firm: Firm,
) -> None:
    subjects = await _daniels_eleven(firm)
    voided = subjects["sign_off_request"][0]
    await firm.net.seed.run(
        "UPDATE human_gates SET state = 'voided' WHERE tenant_id = $1 AND subject_ref->>'id' = $2",
        firm.tenant_id,
        str(voided),
    )
    await _deliver(_event(firm.tenant_id, firm.ashford.engagement_id))
    await rebuild_human_gates(firm.tenant_id)
    state = await firm.net.seed.value(
        "SELECT state FROM human_gates WHERE tenant_id = $1 AND subject_ref->>'id' = $2",
        firm.tenant_id,
        str(voided),
    )
    assert state == "voided"
    status, page = await firm.gates(firm.daniel)
    assert status == 200 and _nonzero(page["counts"])["sign_off_request"] == 5


# --- F9 story 2: walls (INV-3), other firms, who may read -----------------------------------


async def test_ac_f9_2_a_walled_person_is_never_counted_a_gate_of_the_walled_client(
    firm: Firm,
) -> None:
    """The row's acceptance: the suite fails if a walled client's gate is counted."""
    for site in (firm.ashford, firm.ashford, firm.bayside):
        _waiting(firm.tenant_id, "consumer_decision", site.engagement_id, assignee=firm.lena)
    _waiting(firm.tenant_id, "consumer_export", firm.ashford.engagement_id)
    for site in (firm.ashford, firm.bayside):
        await _deliver(_event(firm.tenant_id, site.engagement_id))
    status, page = await firm.gates(firm.lena)
    assert status == 200 and _nonzero(page["counts"]) == {"decision": 3, "export": 1}

    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    status, page = await firm.gates(firm.lena)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"decision": 1}
    assert page["total"] == 1
    items = cast(list[Json], page["items"])
    assert {i["engagement_id"] for i in items} == {str(firm.bayside.engagement_id)}
    assert str(firm.ashford.client_id) not in json.dumps(page)
    assert str(firm.ashford.engagement_id) not in json.dumps(page)


async def test_ac_f9_2_a_walled_engagement_filter_reveals_nothing(firm: Firm) -> None:
    _waiting(firm.tenant_id, "consumer_decision", firm.ashford.engagement_id, assignee=firm.lena)
    await _deliver(_event(firm.tenant_id, firm.ashford.engagement_id))
    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    status, page = await firm.gates(
        firm.lena, f"?assignee=me&engagement_id={firm.ashford.engagement_id}"
    )
    # Spec gap: a filter on a walled engagement may answer 404 or an empty page; never a row
    # or a count (INV-3).
    assert status in (200, 404), page
    if status == 200:
        assert page["items"] == [] and _nonzero(page.get("counts", {})) == {}
        assert page["total"] == 0


async def test_ac_f9_2_the_wall_hides_nothing_from_a_colleague_who_is_not_walled(
    firm: Firm,
) -> None:
    _waiting(firm.tenant_id, "consumer_decision", firm.ashford.engagement_id)
    await _deliver(_event(firm.tenant_id, firm.ashford.engagement_id))
    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    status, page = await firm.gates(firm.hannah)
    assert status == 200 and _nonzero(page["counts"]) == {"decision": 1}
    status, page = await firm.gates(firm.lena)
    assert status == 200 and _nonzero(page["counts"]) == {}


async def test_ac_f9_2_a_rebuild_after_the_wall_still_counts_nothing_walled(
    firm: Firm,
) -> None:
    await _daniels_eleven(firm)
    await firm.net.wall(firm.admin, firm.daniel, firm.ashford)
    await firm.net.seed.run("DELETE FROM human_gates WHERE tenant_id = $1", firm.tenant_id)
    await rebuild_human_gates(firm.tenant_id)
    status, page = await firm.gates(firm.daniel)
    assert status == 200, page
    # Bayside only: 1 decision, 2 sign-off requests, 2 exports.
    assert _nonzero(page["counts"]) == {"decision": 1, "sign_off_request": 2, "export": 2}


async def test_ac_f9_2_a_person_off_the_engagement_reads_none_of_its_gates(
    firm: Firm,
) -> None:
    outsider = await firm.net.seed.person(firm.tenant_id)
    _waiting(firm.tenant_id, "consumer_decision", firm.ashford.engagement_id)
    await _deliver(_event(firm.tenant_id, firm.ashford.engagement_id))
    status, page = await firm.gates(outsider)
    assert status == 200, page
    assert page["items"] == [] and _nonzero(page["counts"]) == {}


async def test_ac_f9_2_another_firm_sees_none_of_this_firms_gates(net: Net, firm: Firm) -> None:
    await _daniels_eleven(firm)
    other = await _firm(net)
    status, page = await other.gates(other.daniel)
    assert status == 200 and page["items"] == [] and _nonzero(page["counts"]) == {}
    response = await net.call("GET", f"{GATES}?assignee=me", other.daniel, tenant=firm.tenant_id)
    assert response.status_code in (403, 404)
    assert str(firm.ashford.engagement_id) not in response.text


async def test_ac_f9_2_a_client_user_reads_no_firm_gate(firm: Firm) -> None:
    _waiting(firm.tenant_id, "consumer_decision", firm.ashford.engagement_id)
    await _deliver(_event(firm.tenant_id, firm.ashford.engagement_id))
    contact = await firm.net.seed.client_contact(firm.ashford)
    response = await firm.net.call("GET", f"{GATES}?assignee=me", contact)
    # Spec gap: contract §2 lists no client role for `human_gate.read`, and says nothing of
    # the answer a client principal gets (a refusal, or the empty list visible() leaves). It
    # never carries a firm gate or count (INV-3, INV-4).
    assert response.status_code in (200, 403), response.text
    if response.status_code == 200:
        page = cast(Json, response.json())
        assert page["items"] == [] and _nonzero(page["counts"]) == {}
    assert str(firm.ashford.engagement_id) not in response.text


async def test_ac_c3_flag_off_the_read_answers_404(net: Net) -> None:
    off = await _firm(net, flag=False)
    _waiting(off.tenant_id, "consumer_decision", off.ashford.engagement_id, assignee=off.daniel)
    await _deliver(_event(off.tenant_id, off.ashford.engagement_id))
    status, _ = await off.gates(off.daniel)
    assert status == 404


# --- F9 story 3: the typed agent proposals project as `proposal` gates (DEC-28) --------------

_RUN: Final = (
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
    "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'], 'completed', now()) RETURNING id"
)


async def _agent_proposals(f: Firm, site: Site) -> dict[str, uuid.UUID]:
    """A screening, an upload review with a shown flag and a passed guidance draft on the
    site's version and item, written as the agents write them; then the agent's event."""
    seed = f.net.seed
    # The upload fulfils the item, as a client's upload does, so a person can decide on it.
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        f.tenant_id,
        site.engagement_id,
        site.item_id,
        site.version_id,
    )
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", site.item_id)

    async def run(agent: str) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await seed.value(
                _RUN, f.tenant_id, agent, site.engagement_id, site.version_id, f.hannah.user_id
            ),
        )

    screening = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
            "($1, $2, $3, $4, 'needs_revision', 0.5, 'Totals differ', '[]', '[]') "
            "RETURNING id",
            f.tenant_id,
            site.engagement_id,
            site.version_id,
            await run("evidence.screener"),
        ),
    )
    review = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO upload_reviews (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, prompt_ref, no_concerns) VALUES ($1, $2, $3, $4, "
            "'evidence.upload_reviewer@v1', false) RETURNING id",
            f.tenant_id,
            site.engagement_id,
            site.version_id,
            await run("evidence.upload_reviewer"),
        ),
    )
    await seed.run(
        "INSERT INTO upload_review_flags (tenant_id, review_id, position, category, "
        "confidence, rationale, citations, shown) VALUES ($1, $2, 1, 'altered', 0.9, "
        '\'Edited totals\', \'[{"page": 1, "quote": "Total", "verified": true}]\'::jsonb, '
        "true)",
        f.tenant_id,
        review,
    )
    draft = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO guidance_drafts (tenant_id, engagement_id, request_item_id, "
            "agent_run_id, prompt_ref, why, good_looks_like, passed_checks, check_reasons) "
            "VALUES ($1, $2, $3, $4, 'requests.guidance_drafter@v1', 'Why', 'Good', true, "
            "'{}') RETURNING id",
            f.tenant_id,
            site.engagement_id,
            site.item_id,
            await run("requests.guidance_drafter"),
        ),
    )
    for source in ("screening_result", "upload_review", "guidance_draft"):
        await _deliver(
            OutboxEvent(
                uuid.uuid4(),
                f.tenant_id,
                "proposal.recorded",
                {"engagement_id": str(site.engagement_id), "source": source},
            )
        )
    return {"screening_result": screening, "upload_review": review, "guidance_draft": draft}


def _subjects(page: Json) -> dict[str, str]:
    return {
        str(cast(Json, i["subject"])["type"]): str(cast(Json, i["subject"])["id"])
        for i in cast(list[Json], page["items"])
    }


async def test_ac_f9_3_the_typed_agent_proposals_project_as_proposal_gates(firm: Firm) -> None:
    made = await _agent_proposals(firm, firm.bayside)
    status, page = await firm.gates(firm.hannah)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"proposal": 3}
    assert {i["kind"] for i in cast(list[Json], page["items"])} == {"proposal"}
    assert _subjects(page) == {k: str(v) for k, v in made.items()}
    # An agent's proposal is assigned to nobody: it waits on everyone who may decide it.
    assert {i["assignee_user_id"] for i in cast(list[Json], page["items"])} == {None}


async def test_ac_f9_3_a_rebuild_projects_the_agent_proposals_too(firm: Firm) -> None:
    await _agent_proposals(firm, firm.bayside)
    before = await _open_rows(firm.net.seed, firm.tenant_id)
    await firm.net.seed.run("DELETE FROM human_gates WHERE tenant_id = $1", firm.tenant_id)
    await rebuild_human_gates(firm.tenant_id)
    assert await _open_rows(firm.net.seed, firm.tenant_id) == before
    assert len(before) == 3


async def test_ac_f9_3_a_persons_decision_on_the_version_closes_its_proposals(
    firm: Firm,
) -> None:
    """Accepting the version (a person's decision, AUD-03) leaves nothing on it waiting; the
    worker learns of it from the product's own outbox."""
    made = await _agent_proposals(firm, firm.bayside)
    response = await firm.net.call(
        "POST",
        f"/v1/engagements/{firm.bayside.engagement_id}/evidence-versions/"
        f"{firm.bayside.version_id}/decision/accept",
        firm.daniel,
        body={"seen_proposal": str(made["screening_result"])},
    )
    assert response.status_code in (200, 201), response.text
    assert await _replay_outbox(firm.net.seed, firm.tenant_id) >= 1
    status, page = await firm.gates(firm.hannah)
    assert status == 200, page
    assert set(_subjects(page)) == {"guidance_draft"}
    # Replaying the whole history again changes nothing.
    before = await _stored(firm.net.seed, firm.tenant_id)
    await _replay_outbox(firm.net.seed, firm.tenant_id)
    assert await _stored(firm.net.seed, firm.tenant_id) == before


async def test_ac_f9_3_a_walled_person_is_counted_no_proposal_of_the_walled_client(
    firm: Firm,
) -> None:
    await _agent_proposals(firm, firm.ashford)
    await _agent_proposals(firm, firm.bayside)
    status, page = await firm.gates(firm.lena)
    assert status == 200 and _nonzero(page["counts"]) == {"proposal": 6}
    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    status, page = await firm.gates(firm.lena)
    assert status == 200, page
    assert _nonzero(page["counts"]) == {"proposal": 3}
    assert str(firm.ashford.engagement_id) not in json.dumps(page)
