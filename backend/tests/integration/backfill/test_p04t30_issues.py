"""P-04-T30 (TASK-1619; ADR-160; SPEC-360; DEC-714): issues service part 1 over HTTP on P-04-T28's
world (a probe reviewable on the Ridgeline engagement).

"Eleven open Ridgeline issues that block final_approval appear as one failing check on the
final-approval eligibility read" (P-04-T30 acceptance). Around it: create seals the title and reads
it back once per read (an access event); the list carries status counts and kind facets; an update
against a stale version is 409 `issue_changed`; assigning notifies the assignee once
(`issue.assigned`); an engine diagnostic seen twice is one issue.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.review import issues

from . import test_p04t28_proposals_independent as t28
from .p04t28_support import PROBE, World, probe

world = t28.world


def _body(target: uuid.UUID, **extra: object) -> dict[str, object]:
    return {
        "record_type": PROBE,
        "record_id": str(target),
        "kind": "review_point",
        "title": "Tie line 14 to the K-1 detail",
        "blocks": ["final_approval"],
        **extra,
    }


async def test_ac_eleven_blocking_issues_are_one_failing_final_approval_check(
    world: World,
) -> None:
    target = probe(world.site, (world["samuel"],))
    for _ in range(11):
        made = await world.call("POST", "/v1/issues", "samuel", _body(target))
        assert made.status_code == 201, made.text
    read = await world.call(
        "GET",
        f"/v1/sign-offs/eligibility?target_type={PROBE}&target_id={target}&level=L4_partner",
        "samuel",
    )
    assert read.status_code == 200, read.text
    checks = [c for c in read.json()["checks"] if c["code"] == "open_issues"]
    assert len(checks) == 1
    assert checks[0]["result"] == "fail" and checks[0]["facts"]["count"] == 11


async def test_create_read_list_and_a_stale_update(world: World) -> None:
    target = probe(world.site, (world["samuel"],))
    made = await world.call("POST", "/v1/issues", "samuel", _body(target, priority="high"))
    issue = made.json()["issue"]
    assert made.json()["title"] == "Tie line 14 to the K-1 detail"
    stored = await world.seed.value("SELECT title_sealed FROM issues WHERE id = $1", issue["id"])
    assert b"Tie line 14" not in cast(bytes, stored)  # sealed at rest
    listed = await world.call(
        "GET", f"/v1/issues?record_type={PROBE}&record_id={target}", "samuel"
    )
    body = listed.json()
    assert body["counts"] == {"open": 1}
    assert body["facets"]["kind"][0]["value"] == "review_point"
    stale = await world.call(
        "PATCH", f"/v1/issues/{issue['id']}", "samuel", {"seen_version": 9, "priority": "low"}
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "issue_changed"


async def test_assigning_notifies_the_assignee_once(world: World) -> None:
    target = probe(world.site, (world["samuel"],))
    made = await world.call("POST", "/v1/issues", "samuel", _body(target))
    issue = made.json()["issue"]
    assigned = await world.call(
        "PATCH",
        f"/v1/issues/{issue['id']}",
        "samuel",
        {"seen_version": issue["version"], "assignee_user_id": str(world["priya"].user_id)},
    )
    assert assigned.status_code == 200, assigned.text
    events = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'issue.assigned'",
        world.tenant_id,
    )
    assert events == 1


async def test_an_engine_diagnostic_seen_twice_is_one_issue(world: World) -> None:
    target = probe(world.site, (world["samuel"],))
    work_item = uuid.uuid4()
    samuel = world["samuel"]
    ctx = AuthContext(
        TenantContext(world.tenant_id, "human", str(samuel.user_id)),
        samuel.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    first = await issues.record_engine_issue(
        ctx,
        record_type=PROBE,
        record_id=target,
        work_item_id=work_item,
        source_ref="E-1040-17",
        title="Form 8995-A line 1 disagrees",
    )
    again = await issues.record_engine_issue(
        ctx,
        record_type=PROBE,
        record_id=target,
        work_item_id=work_item,
        source_ref="E-1040-17",
        title="Form 8995-A line 1 disagrees",
    )
    assert first == again
