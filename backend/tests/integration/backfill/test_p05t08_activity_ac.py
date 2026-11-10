"""P-05-T08 (ac-test-author; SPEC-650 AC-32, AC-34, AC-36, AC-38): AUD-29's engagement routes over
HTTP, from the SPEC and the P-05-T02 501 stubs. P-05-T11 (S35) builds them, so each is a strict
xfail citing this row's task: the suite fails the moment the routes answer and the mark is not
removed with them.

The seed is AUD-29a's split: 12 events by people and 11 by the agent on Northwind, none by policy,
so All 23 · Human 12 · via Agent 11 · Policy 0, footing under any filter.
"""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow

from .p05_support import Collab, collab
from .support import Net

pytestmark = pytest.mark.asyncio
WAITING = pytest.mark.xfail(
    strict=True, reason="TASK-6604: the AUD-29 routes answer 501 until P-05-T11 (S35)"
)


@pytest.fixture
async def w(net: Net) -> Collab:
    world = await collab(net)
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit_trail.engagement_activity', 'true', 'test-seed', 'P-05-T08')",
        world.tenant_id,
    )
    forget_flags()
    for n in range(23):
        kind = "human" if n < 12 else "agent"
        actor = str(world.margaret.user_id) if kind == "human" else f"run-{uuid.uuid4()}"
        # An agent always acts for a person (audit_events_agent_acts_for_a_person): Hannah's run.
        on_behalf = world.hannah.user_id if kind == "agent" else None
        async with uow(TenantContext(world.tenant_id, kind, actor, on_behalf)) as tx:
            tx.record(
                "engagement.note_added",
                target=Target("engagement", world.site.engagement_id),
            )
    return world


def _path(w: Collab, tail: str) -> str:
    return f"/v1/engagements/{w.site.engagement_id}/audit-events/{tail}"


@WAITING
async def test_ac32_the_segments_foot_12_11_0_to_23(w: Collab) -> None:
    response = await w.call("POST", _path(w, "query"), w.hannah, {"segment": "all"})
    assert response.status_code == 200, response.text
    assert response.json()["counts"] == {"all": 23, "human": 12, "via_agent": 11, "policy": 0}
    agent = await w.call("POST", _path(w, "query"), w.hannah, {"segment": "via_agent"})
    assert len(agent.json()["items"]) == 11
    assert agent.json()["counts"]["all"] == 23  # counts foot under every filter


@WAITING
async def test_ac34_the_search_text_stays_in_the_body(w: Collab) -> None:
    response = await w.call("POST", _path(w, "query"), w.hannah, {"q": "Materiality"})
    assert response.status_code == 200, response.text
    assert "Materiality" not in str(response.request.url)


# The refusals come before the 501: authorisation and walls already answer (no WAITING).
async def test_ac36_a_firm_admin_and_a_client_are_refused(w: Collab) -> None:
    for who in (w.grace, w.client, w.victor):
        response = await w.call("POST", _path(w, "query"), who, {})
        assert response.status_code in (403, 404), who


@WAITING
async def test_ac38_export_needs_export_create_and_a_fresh_mfa(w: Collab) -> None:
    staff = await w.call("POST", _path(w, "export"), w.marcus, {})
    assert staff.status_code == 403
    stale = await w.call("POST", _path(w, "export"), w.margaret, {}, mfa=False)
    assert stale.status_code in (401, 403)
    done = await w.call("POST", _path(w, "export"), w.margaret, {})
    assert done.status_code == 200, done.text
    assert done.headers["content-type"].startswith("text/csv")
    lines = done.text.strip().splitlines()
    assert len(lines) == 1 + 23  # the header and the filtered rows
    exported = await w.audit_actions(w.site.engagement_id)
    assert ("audit_event.exported", str(w.margaret.user_id)) in exported


async def test_ac39_flag_off_the_activity_routes_answer_not_found(w: Collab) -> None:
    await w.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'audit_trail.engagement_activity'",
        w.tenant_id,
    )
    forget_flags()
    response = await w.call("POST", _path(w, "query"), w.hannah, {})
    assert response.status_code == 404
