"""I-01-T12: Home's client activity projection (DEC-900; I-01 AC4.3, AC4.4). Replaying the same
events leaves the projection unchanged, rows hold no free text, a walled user's timeline omits
the client entirely, the prune drops rows past 90 days and the rebuild restores the outbox."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.practice.activity import (
    ACTIVITY_TYPES,
    on_event,
    prune_firm,
    rebuild_home_activity,
)

from .support import Json, Net

pytestmark = pytest.mark.asyncio
HOME = "/v1/home"


def _upload(tenant: uuid.UUID, engagement: uuid.UUID) -> OutboxEvent:
    return OutboxEvent(
        uuid.uuid4(),
        tenant,
        "evidence.uploaded",
        {
            "engagement_id": str(engagement),
            "request_item_id": str(uuid.uuid4()),
            "evidence_version_id": str(uuid.uuid4()),
            "uploaded_by": str(uuid.uuid4()),
        },
    )


async def _rows(net: Net, tenant: uuid.UUID) -> list[Json]:
    found = await net.seed.rows(
        "SELECT event_type, actor_kind, actor_ref, subject_ref, facts, client_id "
        "FROM home_activity_items WHERE tenant_id = $1 ORDER BY occurred_at, id",
        tenant,
    )
    return [dict(r) for r in found]


async def _flag(net: Net, tenant: uuid.UUID) -> None:
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'home.dashboard', 'true', 'test-seed', 'I-01-T12')",
        tenant,
    )


async def test_ac_replaying_events_leaves_the_projection_unchanged_and_rows_hold_no_text(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await _flag(net, tenant)
    admin = await seed.person(tenant, "firm_admin")
    hannah = await seed.person(tenant)
    site = await seed.site(tenant, admin.user_id, "Ashford")
    await seed.member(site, hannah, "manager")

    events = [
        _upload(tenant, site.engagement_id),
        OutboxEvent(
            uuid.uuid4(),
            tenant,
            "follow_up.sent",
            {
                "engagement_id": str(site.engagement_id),
                "follow_up_id": str(uuid.uuid4()),
                "sent_by": str(hannah.user_id),
            },
        ),
        OutboxEvent(
            uuid.uuid4(),
            tenant,
            "gate.met",
            {"engagement_id": str(site.engagement_id), "gate": "G3"},
        ),
        OutboxEvent(
            uuid.uuid4(),
            tenant,
            "upload_review.recorded",
            {"engagement_id": str(site.engagement_id), "evidence_version_id": str(uuid.uuid4())},
        ),
        # G1 is not client activity: no row.
        OutboxEvent(
            uuid.uuid4(),
            tenant,
            "gate.met",
            {"engagement_id": str(site.engagement_id), "gate": "G1"},
        ),
    ]
    for event in events:
        await on_event(event)
    first = await _rows(net, tenant)
    assert sorted(str(r["event_type"]) for r in first) == sorted(ACTIVITY_TYPES)

    # The same events again, in another order: nothing changes.
    for event in reversed(events):
        await on_event(event)
    assert await _rows(net, tenant) == first

    # Identifiers, codes and counts only: no names, no amounts, no free text.
    for row in first:
        assert row["client_id"] == site.client_id
        for blob in (row["actor_ref"], row["subject_ref"], row["facts"]):
            loaded = cast(Json, json.loads(blob) if isinstance(blob, str) else blob)
            for key, value in loaded.items():
                assert key in {"type", "id", "count", "gate"}
                if key == "id":
                    uuid.UUID(str(value))
                elif isinstance(value, str):
                    assert value.replace("_", "").isalnum() and len(value) <= 20
    assert site.marker not in str(first)

    response = await net.call("GET", HOME, hannah)
    assert response.status_code == 200, response.text
    activity = cast(list[Json], cast(Json, response.json())["client_activity"])
    assert len(activity) == 4
    assert {a["client_id"] for a in activity} == {str(site.client_id)}
    assert all(a["client_label"] for a in activity)


async def test_ac_a_walled_users_timeline_omits_the_client_entirely(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await _flag(net, tenant)
    admin = await seed.person(tenant, "firm_admin")
    lena = await seed.person(tenant)
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    bayside = await seed.site(tenant, admin.user_id, "Bayside")
    for site in (ashford, bayside):
        await seed.member(site, lena, "manager")
        await on_event(_upload(tenant, site.engagement_id))

    before = cast(Json, (await net.call("GET", HOME, lena)).json())
    assert len(cast(list[Json], before["client_activity"])) == 2

    await net.wall(admin, lena, ashford)
    after = cast(Json, (await net.call("GET", HOME, lena)).json())
    rows = cast(list[Json], after["client_activity"])
    assert [r["client_id"] for r in rows] == [str(bayside.client_id)]
    assert str(ashford.client_id) not in str(after)
    assert ashford.marker not in str(after)

    # An office nobody files under narrows the timeline to nothing (DEC-30, a filter only).
    nowhere = cast(Json, (await net.call("GET", f"{HOME}?office_id={uuid.uuid4()}", lena)).json())
    assert nowhere["client_activity"] == []


async def test_the_prune_drops_rows_past_90_days_and_the_rebuild_restores_the_outbox(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Calloway")
    old, recent = _upload(tenant, site.engagement_id), _upload(tenant, site.engagement_id)
    await on_event(old)
    await on_event(recent)
    await seed.run(
        "UPDATE home_activity_items SET occurred_at = $2 WHERE source_event_id = $1",
        old.event_id,
        datetime.now(UTC) - timedelta(days=91),
    )
    assert await prune_firm(tenant) == 1
    assert await prune_firm(tenant) == 0  # nothing left to prune: no write, no audit event
    remaining = await seed.rows(
        "SELECT source_event_id FROM home_activity_items WHERE tenant_id = $1", tenant
    )
    assert [r["source_event_id"] for r in remaining] == [recent.event_id]

    # The rebuild reads the firm's published events: one missing row comes back, once.
    await seed.run("DELETE FROM home_activity_items WHERE tenant_id = $1", tenant)
    for event in (recent, _upload(tenant, site.engagement_id)):
        await seed.run(
            "INSERT INTO outbox (id, tenant_id, event_type, payload, published_at) "
            "VALUES ($1, $2, $3, $4::jsonb, clock_timestamp())",
            event.event_id,
            tenant,
            event.event_type,
            json.dumps(event.payload),
        )
    assert await rebuild_home_activity(tenant) == 2
    assert await rebuild_home_activity(tenant) == 0
