# ac-test-author: ayushkbhatia
"""P-07-T56: independent acceptance tests (ADR-078) for P-07-T55 (roll-forward v2), T47 (gate and
notification registrations) and T57 (record activity), written from `engagements-v2.md` §8a, the
C13 and C16 contracts and P-07 Story 7.1, not from the implementing suites.

- Evidence is never copied and the carried requests are Draft, invisible to the client.
- A walled person gets 404 on the source; an active (unreleased) source answers 409; a client
  principal reaches no roll-forward route.
- The carried team's gates (C13) appear for the new engagement through the projector, and none
  reaches a client.
- Every outbox payload Create wrote carries identifiers and codes, never a name.
- Record activity respects walls: the walled person's read answers 404.
"""

from __future__ import annotations

import json
import uuid
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import C13_EVENTS
from abacus.modules.review.api import SUBSCRIPTIONS as GATES

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
FLAGS: Final = ("engagements.roll_forward_v2", "engagements.v2", "clients.v2")
NAME: Final = "Calloway Family Trust 401(k) Plan · PY2025"


async def _flags(net: Net, tenant: uuid.UUID) -> None:
    for flag in FLAGS:
        await net.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T56') "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = 'true'",
            tenant,
            flag,
        )
    forget_flags()


async def _firm(net: Net) -> tuple[uuid.UUID, Person, Person, Person, Site]:
    seed = net.seed
    tenant = await seed.firm()
    await _flags(net, tenant)
    admin = await seed.person(tenant, "firm_admin")
    partner = await seed.person(tenant)
    manager = await seed.person(tenant)
    for who, level in ((partner, "partner"), (manager, "manager")):
        await seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
            level,
        )
    site = await seed.site(tenant, admin.user_id, "Calloway")
    await seed.run_untriggered(
        "UPDATE engagements SET name = $2, type = 'ebp_audit', status = 'delivered' WHERE id = $1",
        site.engagement_id,
        NAME,
    )
    for n in range(3):
        await seed.item(site, f"Plan document {n}", status="received")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    template = await seed.value(
        "INSERT INTO acceptance_questionnaire_templates (tenant_id, name, family, created_by) "
        "VALUES ($1, 'Audit & assurance v3', 'audit_assurance', $2) RETURNING id",
        tenant,
        admin.user_id,
    )
    await seed.run(
        "INSERT INTO acceptance_questionnaire_template_versions "
        "(tenant_id, template_id, version_no, sections, created_by) "
        "VALUES ($1, $2, 1, $3::jsonb, $4)",
        tenant,
        template,
        json.dumps([{"code": "continuance", "title": "Continuance"}]),
        admin.user_id,
    )
    return tenant, admin, partner, manager, site


def _drafts(site: Site) -> str:
    return f"/v1/engagements/{site.engagement_id}/roll-forward/drafts"


async def _roll(net: Net, who: Person, site: Site) -> uuid.UUID:
    made = await net.call("POST", _drafts(site), who)
    assert made.status_code == 201, made.text
    draft = cast(dict[str, object], made.json())
    created = await net.http.post(
        f"{_drafts(site)}/{draft['id']}/create",
        headers={**net.headers(who), "Idempotency-Key": f"p07t56-{uuid.uuid4()}"},
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(cast(str, created.json()["engagement_id"]))


async def test_evidence_never_copied_and_carried_requests_stay_invisible_to_the_client(
    net: Net,
) -> None:
    seed = net.seed
    _tenant, _admin, _partner, manager, site = await _firm(net)
    claire = await seed.client_contact(site)
    new_id = await _roll(net, manager, site)

    assert (
        await seed.value("SELECT count(*) FROM evidence_items WHERE engagement_id = $1", new_id)
        == 0
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM evidence_versions v JOIN evidence_items i "
            "ON i.id = v.evidence_item_id WHERE i.engagement_id = $1",
            new_id,
        )
        == 0
    )
    items = await seed.rows(
        "SELECT id, status, client_visible FROM request_items WHERE engagement_id = $1", new_id
    )
    assert items and {(r["status"], r["client_visible"]) for r in items} == {("draft", False)}

    # The client sees none of them: not through the portal, not through a firm route.
    home = await net.call("GET", "/v1/portal/home", claire)
    for row in items:
        assert str(row["id"]) not in home.text
    firm_route = await net.call("GET", f"/v1/engagements/{new_id}/request-items", claire)
    assert firm_route.status_code in (403, 404)
    for path in (_drafts(site), f"/v1/engagements/{new_id}/record-activity"):
        refused = await net.call("GET", path, claire)
        assert refused.status_code in (403, 404), (path, refused.status_code)


async def test_a_walled_person_gets_404_and_an_unreleased_source_409(net: Net) -> None:
    seed = net.seed
    _tenant, admin, partner, manager, site = await _firm(net)
    await net.wall(admin, manager, site)
    walled = await net.call("POST", _drafts(site), manager)
    assert walled.status_code == 404, walled.text
    activity = await net.call(
        "GET", f"/v1/engagements/{site.engagement_id}/record-activity", manager
    )
    assert activity.status_code == 404, activity.text

    await seed.run_untriggered(
        "UPDATE engagements SET status = 'active' WHERE id = $1", site.engagement_id
    )
    active = await net.call("POST", _drafts(site), partner)
    assert active.status_code == 409, active.text


async def test_the_carried_teams_gates_appear_and_payloads_carry_no_names(net: Net) -> None:
    seed = net.seed
    tenant, _admin, partner, manager, site = await _firm(net)
    since = cast(int, await seed.value("SELECT coalesce(max(seq), 0) FROM outbox"))
    new_id = await _roll(net, manager, site)

    written = await seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 AND seq > $2 "
        "ORDER BY seq",
        tenant,
        since,
    )
    assert written
    for row in written:
        payload = str(row["payload"])
        assert NAME not in payload and "Calloway" not in payload  # identifiers only (C16)
    # Drive the C13 projector the way the worker does, over the events Create wrote.
    for row in written:
        if row["event_type"] not in C13_EVENTS:
            continue
        payload = row["payload"]
        event = OutboxEvent(
            row["id"],
            row["tenant_id"],
            row["event_type"],
            cast(dict[str, object], json.loads(payload) if isinstance(payload, str) else payload),
        )
        await GATES[event.event_type](event)
    gates = await seed.rows(
        "SELECT kind, state, assignee_user_id FROM human_gates WHERE tenant_id = $1 "
        "AND engagement_id = $2",
        tenant,
        new_id,
    )
    assert gates, "Create asks the carried team for independence: a gate waits on a person"
    assert {g["state"] for g in gates} == {"open"}
    assignees = {g["assignee_user_id"] for g in gates} - {None}
    assert assignees <= {partner.user_id, manager.user_id}
