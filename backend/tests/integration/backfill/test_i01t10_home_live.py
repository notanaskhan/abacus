"""I-01-T10: `GET /v1/home` live (DEC-648): role-shaped tiles from registered counts, the
viewer's work and deadlines from their assignments, the office filter, and walls (Lena Park's
answer has the shape of a firm without the walled client, INV-3)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import cast

import pytest

from .support import Json, Net, Person, Site

pytestmark = pytest.mark.asyncio
HOME = "/v1/home"


async def _work(net: Net, site: Site, who: Person, by: Person, due: date) -> uuid.UUID:
    item = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, due_on, "
            "created_by) VALUES ($1, $2, $3, 'assurance', $4, $5, $6) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            f"FY2026 audit {site.marker}",
            due,
            by.user_id,
        ),
    )
    await net.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'manager_reviewer', $5)",
        site.tenant_id,
        item,
        site.engagement_id,
        who.user_id,
        by.user_id,
    )
    return item


async def test_home_lists_my_work_and_deadlines_and_walls_leave_a_client_out(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'home.dashboard', 'true', 'test-seed', 'I-01-T10')",
        tenant,
    )
    admin = await seed.person(tenant, "firm_admin")
    hannah = await seed.person(tenant)
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    bayside = await seed.site(tenant, admin.user_id, "Bayside")
    for site in (ashford, bayside):
        await seed.member(site, hannah, "manager")
    today = date.today()
    await _work(net, ashford, hannah, admin, today + timedelta(days=3))
    await _work(net, bayside, hannah, admin, today + timedelta(days=30))

    response = await net.call("GET", HOME, hannah)
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    work = cast(Json, body["your_work"])
    assert work["label"] == "home.your_work.engagements"
    assert len(cast(list[Json], work["rows"])) == 2
    deadlines = cast(Json, body["deadlines"])
    rows = cast(list[Json], deadlines["rows"])
    assert [r["risk"] for r in rows] == ["due_soon"]
    assert cast(Json, deadlines["next"])["risk"] == "later"

    # Walled from Ashford: the same shape, as if Ashford did not exist.
    await net.wall(admin, hannah, ashford)
    walled = cast(Json, (await net.call("GET", HOME, hannah)).json())
    assert set(walled) == set(body)
    assert len(cast(list[Json], cast(Json, walled["your_work"])["rows"])) == 1
    assert cast(Json, walled["deadlines"])["rows"] == []
    assert "Ashford" not in str(walled)

    # An office nobody files under narrows everything to nothing (DEC-30).
    nowhere = cast(
        Json, (await net.call("GET", f"{HOME}?office_id={uuid.uuid4()}", hannah)).json()
    )
    assert cast(Json, nowhere["your_work"])["rows"] == []

    # The firm admin gets the metadata tile set and no work band (ADR-024).
    grace = cast(Json, (await net.call("GET", HOME, admin)).json())
    assert grace["your_work"] is None
    assert {t["key"] for t in cast(list[Json], grace["tiles"])} <= {
        "signatures_out",
        "inbox_waiting",
        "portal_invites_pending",
        "binders",
    }
