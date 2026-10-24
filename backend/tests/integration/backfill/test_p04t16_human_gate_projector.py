"""P-04-T16 (P-04 §3 F9; C13): the human-gate projector.

- Replaying the same events leaves `human_gates` unchanged (idempotent on the event), and a full
  rebuild from the owners' records yields the same rows.
- A walled client's gates are never listed or counted (INV-3).
- The agent's typed proposals (screening results, upload reviews, guidance drafts) project as
  `proposal` gates, and a person's decision closes them (DEC-28).

Boundary: the migrated Postgres (superuser seeding where no route makes the row), the projector
as the relay calls it, `GET /v1/human-gates` over HTTP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import rebuild_human_gates
from abacus.modules.review.gates import apply_event

from .support import Net, Person, Seeder, Site


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    manager: Person
    site: Site
    walled: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed


async def _run(seed: Seeder, firm: uuid.UUID, site: Site, by: uuid.UUID, agent: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
            "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'], 'completed', now()) "
            "RETURNING id",
            firm,
            agent,
            site.engagement_id,
            site.version_id,
            by,
        ),
    )


async def _proposals(
    seed: Seeder, firm: uuid.UUID, site: Site, by: uuid.UUID
) -> dict[str, uuid.UUID]:
    screen = await _run(seed, firm, site, by, "evidence.screener")
    result = await seed.value(
        "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
        "($1, $2, $3, $4, 'needs_revision', 0.5, 'Totals differ', '[]', '[]') RETURNING id",
        firm,
        site.engagement_id,
        site.version_id,
        screen,
    )
    review_run = await _run(seed, firm, site, by, "evidence.upload_reviewer")
    review = await seed.value(
        "INSERT INTO upload_reviews (tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, prompt_ref, no_concerns) VALUES ($1, $2, $3, $4, "
        "'evidence.upload_reviewer@v1', false) RETURNING id",
        firm,
        site.engagement_id,
        site.version_id,
        review_run,
    )
    draft_run = await _run(seed, firm, site, by, "requests.guidance_drafter")
    draft = await seed.value(
        "INSERT INTO guidance_drafts (tenant_id, engagement_id, request_item_id, agent_run_id, "
        "prompt_ref, why, good_looks_like, passed_checks, check_reasons) VALUES ($1, $2, $3, $4, "
        "'requests.guidance_drafter@v1', 'Why', 'Good', true, '{}') RETURNING id",
        firm,
        site.engagement_id,
        site.item_id,
        draft_run,
    )
    return {
        "screening_result": cast(uuid.UUID, result),
        "upload_review": cast(uuid.UUID, review),
        "guidance_draft": cast(uuid.UUID, draft),
    }


def _event(
    firm: uuid.UUID, kind: str, site: Site, event_id: uuid.UUID | None = None
) -> OutboxEvent:
    return OutboxEvent(
        event_id or uuid.uuid4(), firm, kind, {"engagement_id": str(site.engagement_id)}
    )


async def _rows(seed: Seeder, firm: uuid.UUID) -> list[tuple[object, ...]]:
    found = await seed.rows(
        "SELECT kind, subject_ref->>'type' AS t, subject_ref->>'id' AS s, engagement_id, state, "
        "source_event_id, updated_at FROM human_gates WHERE tenant_id = $1 ORDER BY t, s",
        firm,
    )
    return [tuple(r) for r in found]


async def _firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'P-04-T16')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Granite")
    walled = await seed.site(tenant_id, admin.user_id, "Ashford")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    await seed.member(walled, manager, "manager")
    return Firm(net, tenant_id, admin, manager, site, walled)


async def test_p04t16_the_typed_proposals_project_as_proposal_gates(
    net: Net, seed: Seeder
) -> None:
    firm = await _firm(net, seed)
    made = await _proposals(seed, firm.tenant_id, firm.site, firm.manager.user_id)
    await apply_event(_event(firm.tenant_id, "proposal.recorded", firm.site))
    rows = await _rows(seed, firm.tenant_id)
    assert [(r[0], r[1], r[2], r[4]) for r in rows] == [
        ("proposal", t, str(made[t]), "open")
        for t in ("guidance_draft", "screening_result", "upload_review")
    ]
    # A person approves the draft: its gate closes; the other two still wait.
    await seed.run(
        "INSERT INTO guidance_draft_decisions (tenant_id, draft_id, decision, edited, "
        "confirmed_read, decided_by) VALUES ($1, $2, 'approved', false, true, $3)",
        firm.tenant_id,
        made["guidance_draft"],
        firm.manager.user_id,
    )
    await apply_event(_event(firm.tenant_id, "guidance_draft.decided", firm.site))
    states = {r[1]: r[4] for r in await _rows(seed, firm.tenant_id)}
    assert states == {
        "guidance_draft": "done",
        "screening_result": "open",
        "upload_review": "open",
    }


async def test_p04t16_replaying_the_same_events_leaves_human_gates_unchanged(
    net: Net, seed: Seeder
) -> None:
    firm = await _firm(net, seed)
    await _proposals(seed, firm.tenant_id, firm.site, firm.manager.user_id)
    event = _event(firm.tenant_id, "proposal.recorded", firm.site)
    await apply_event(event)
    before = await _rows(seed, firm.tenant_id)
    audits = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'human_gate.projected'",
        firm.tenant_id,
    )
    await apply_event(event)  # redelivered
    await apply_event(_event(firm.tenant_id, "proposal.recorded", firm.site))  # another event
    assert await _rows(seed, firm.tenant_id) == before  # same rows, same timestamps
    assert (
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'human_gate.projected'",
            firm.tenant_id,
        )
        == audits
    )


async def test_p04t16_a_rebuild_from_the_owners_yields_the_same_rows(
    net: Net, seed: Seeder
) -> None:
    firm = await _firm(net, seed)
    await _proposals(seed, firm.tenant_id, firm.site, firm.manager.user_id)
    await _proposals(seed, firm.tenant_id, firm.walled, firm.manager.user_id)
    for site in (firm.site, firm.walled):
        await apply_event(_event(firm.tenant_id, "proposal.recorded", site))
    projected = [(r[0], r[1], r[2], r[3], r[4]) for r in await _rows(seed, firm.tenant_id)]
    await seed.run("DELETE FROM human_gates WHERE tenant_id = $1", firm.tenant_id)
    assert await rebuild_human_gates(firm.tenant_id) == len(projected)
    rebuilt = [(r[0], r[1], r[2], r[3], r[4]) for r in await _rows(seed, firm.tenant_id)]
    assert rebuilt == projected
    assert await rebuild_human_gates(firm.tenant_id) == 0  # nothing left to change


async def test_p04t16_a_walled_clients_gates_are_never_listed_or_counted(
    net: Net, seed: Seeder
) -> None:
    firm = await _firm(net, seed)
    mine = await _proposals(seed, firm.tenant_id, firm.site, firm.manager.user_id)
    await _proposals(seed, firm.tenant_id, firm.walled, firm.manager.user_id)
    for site in (firm.site, firm.walled):
        await apply_event(_event(firm.tenant_id, "proposal.recorded", site))
    before = await net.call("GET", "/v1/human-gates", firm.manager)
    assert before.status_code == 200, before.text
    assert before.json()["total"] == 6
    await net.wall(firm.admin, firm.manager, firm.walled)
    after = await net.call("GET", "/v1/human-gates", firm.manager)
    assert after.status_code == 200, after.text
    body = after.json()
    assert body["total"] == 3
    assert body["counts"] == {"proposal": 3}
    assert {i["engagement_id"] for i in body["items"]} == {str(firm.site.engagement_id)}
    assert {i["subject"]["id"] for i in body["items"]} == {str(v) for v in mine.values()}
    walled = await net.call(
        "GET", f"/v1/human-gates?engagement_id={firm.walled.engagement_id}", firm.manager
    )
    assert walled.status_code == 200 and walled.json()["total"] == 0


async def test_p04t16_the_list_is_off_with_the_review_grammar_flag(net: Net, seed: Seeder) -> None:
    tenant_id = await seed.firm()
    who = await seed.person(tenant_id, "firm_admin")
    response = await net.call("GET", "/v1/human-gates", who)
    assert response.status_code == 404
