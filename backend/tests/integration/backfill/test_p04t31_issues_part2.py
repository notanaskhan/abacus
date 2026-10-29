# ac-test-author: ayushkbhatia
"""P-04-T31 (TASK-1738; SHL-15; ISSUE-001; DEC-828): issues part 2 over HTTP on P-04-T28's world.

Acceptance (the task row): "Ana Cruz's Northwind issue creates one client-visible request item
that carries only the client wording, and no agent context can resolve any issue."

Also: resolve → verify → reopen moves one step at a time on the seen version; not applicable from
open; a status it cannot reach is 409; fix instructions with no runner registered are 409
`fix_runner_unavailable` and record nothing; send-to-client waits for G3 and a replay of the same
Idempotency-Key makes no second item.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any, cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import Forbidden, member_context
from abacus.modules.review import issue_resolutions

from . import test_p04t28_proposals_independent as t28
from .p04t28_support import PROBE, World, probe

world = t28.world
Body = dict[str, Any]  # a response body as the contract shapes it
INTERNAL = "Internal: K-1 line 14 still ties to the old detail"
WORDING = "Please send the corrected 2025 K-1 for the plan."


async def _issue(world: World, who: str = "ana") -> Body:
    target = probe(world.site, (world["samuel"],))
    made = await world.call(
        "POST",
        "/v1/issues",
        who,
        {
            "record_type": PROBE,
            "record_id": str(target),
            "kind": "waiting_on_client",
            "title": INTERNAL,
        },
    )
    assert made.status_code == 201, made.text
    return cast(Body, made.json()["issue"])


async def _g3(world: World) -> None:
    await world.seed.run(
        "INSERT INTO engagement_letters (tenant_id, engagement_id, status, letter_date, "
        "recorded_by) VALUES ($1, $2, 'signed', '2026-04-02', 'test-seed') "
        "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET status = 'signed'",
        world.tenant_id,
        world.site.engagement_id,
    )


async def _send(world: World, issue: Body, key: str) -> httpx.Response:
    contact = uuid.uuid4()
    return await world.call_with(
        "POST",
        f"/v1/issues/{issue['id']}/send-to-client",
        "ana",
        {"seen_version": issue["version"], "client_wording": WORDING, "contact_id": str(contact)},
        {"Idempotency-Key": key},
    )


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_one_request_item_with_only_the_client_wording(world: World) -> None:
    await _g3(world)
    issue = await _issue(world)
    key = str(uuid.uuid4())
    sent = await _send(world, issue, key)
    assert sent.status_code == 200, sent.text
    again = await _send(world, issue, key)
    assert again.status_code == 200
    rows = await world.seed.rows(
        "SELECT description FROM request_items WHERE engagement_id = $1 AND description = $2",
        world.site.engagement_id,
        WORDING,
    )
    assert len(rows) == 1
    leaked = await world.seed.value(
        "SELECT count(*) FROM request_items WHERE engagement_id = $1 AND description LIKE $2",
        world.site.engagement_id,
        "%Internal%",
    )
    assert leaked == 0


async def test_ac_no_agent_context_can_resolve_any_issue(world: World) -> None:
    issue = await _issue(world)
    person = await member_context(world.tenant_id, world["samuel"].user_id)
    assert person is not None
    agent = replace(person, tenant=TenantContext(world.tenant_id, "agent", "agent:run"))
    for to in ("resolved", "verified", "not_applicable", "reopened"):
        with pytest.raises(Forbidden):
            await issue_resolutions.move(agent, uuid.UUID(issue["id"]), to, issue["version"])
    status = await world.seed.value("SELECT status FROM issues WHERE id = $1", issue["id"])
    assert status == "open"


# --- The rest of the row ------------------------------------------------------------------------


async def test_resolve_verify_reopen_one_step_at_a_time(world: World) -> None:
    issue = await _issue(world)
    path = f"/v1/issues/{issue['id']}"
    version = issue["version"]
    early = await world.call("POST", f"{path}/verify", "samuel", {"seen_version": version})
    assert early.status_code == 409
    for step, expect in (("resolve", "resolved"), ("verify", "verified"), ("reopen", "reopened")):
        moved = await world.call("POST", f"{path}/{step}", "samuel", {"seen_version": version})
        assert moved.status_code == 200, moved.text
        assert moved.json()["issue"]["status"] == expect
        version = moved.json()["issue"]["version"]
    stale = await world.call("POST", f"{path}/resolve", "samuel", {"seen_version": 1})
    assert stale.status_code == 409


async def test_not_applicable_from_open(world: World) -> None:
    issue = await _issue(world)
    done = await world.call(
        "POST",
        f"/v1/issues/{issue['id']}/mark-not-applicable",
        "samuel",
        {"seen_version": issue["version"]},
    )
    assert done.status_code == 200, done.text
    assert done.json()["issue"]["status"] == "not_applicable"


async def test_fix_instructions_with_no_runner_record_nothing(world: World) -> None:
    issue = await _issue(world)
    refused = await world.call(
        "POST",
        f"/v1/issues/{issue['id']}/fix-instructions",
        "samuel",
        {"seen_version": issue["version"], "text": "Use the amended K-1"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "fix_runner_unavailable"
    events = await world.seed.value(
        "SELECT count(*) FROM issue_events WHERE issue_id = $1 AND event = 'fix_instructions_set'",
        issue["id"],
    )
    assert events == 0


async def test_send_to_client_waits_for_g3(world: World) -> None:
    issue = await _issue(world)
    refused = await _send(world, issue, str(uuid.uuid4()))
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "gate_unmet"
