"""A-06-T10's notification (TASK-5303; A-06 §4.5; DEC-2422).

Boundary: `create_app()` over HTTP on the migrated test database, then the relay's own event. A
recorded client decision writes one `proposed_entry.client_decided` to the outbox, and the
catalogue fans it out as `proposed_entry_client_responded` to the engagement's partner and
managers.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.kernel.flags import forget_flags

from .tb_support import Books, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'adjustments.entries', 'true', 'test-seed', 'A-06-T10') "
        "ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    forget_flags()
    return found


async def _approved_entry(world: Books) -> uuid.UUID:
    entry = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO proposed_entries (id, tenant_id, engagement_id, work_item_id, kind, number, "
        "ref, threshold_result, is_attest_client, status, created_by_kind, created_by_id) VALUES "
        "($1, $2, $3, $4, 'aje', 1, 'AJE-1', 'review_required', true, 'approved', 'human', 'x')",
        entry,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
    )
    return entry


async def _record(world: Books, entry: uuid.UUID, decision: str) -> None:
    done = await world.call(
        "POST",
        f"/v1/proposed-entries/{entry}/client-decision:record",
        world.manager,
        {
            "decision": decision,
            "by_contact_id": str(uuid.uuid4()),
            "decided_on": "2027-10-04",
            "evidence_version_id": str(uuid.uuid4()),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert done.status_code == 200, done.text


@pytest.mark.parametrize("decision", ["client_accepted", "client_declined", "client_question"])
async def test_a_recorded_client_decision_writes_one_event(world: Books, decision: str) -> None:
    entry = await _approved_entry(world)
    await _record(world, entry, decision)
    rows = await world.seed.value(
        "SELECT json_agg(payload) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'proposed_entry.client_decided'",
        world.tenant_id,
    )
    payloads = cast(list[dict[str, str]], json.loads(cast(str, rows)))
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["entry_id"] == str(entry)
    assert payload["engagement_id"] == str(world.site.engagement_id)
    assert payload["decision"] == decision
