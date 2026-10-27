"""R-01-T26: portal settings and the read-only preview, live (DEC-653). "Publishing changes the
portal name, cadence and toggles atomically, and preview as a contact on a walled client answers
404." HTTP through `create_app()`; rows read back as the superuser."""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from .support import Json, Net

pytestmark = pytest.mark.asyncio
S: Final = "/v1/firm/portal-settings"


def _draft(expected: int, *, cadence: int = 5) -> Json:
    return {
        "brand": {"portal_name": "Brightwater Hale Client Portal", "sender_display_name": "BH"},
        "client_experience": {"show_team_card": False},
        "follow_up_policy": {"cadence_days": cadence},
        "expected_version": expected,
    }


async def test_publish_applies_name_cadence_and_toggles_at_once(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'test-seed', 'R-01-T26')",
        tenant,
    )
    grace = await seed.person(tenant, "firm_admin")
    saved = await net.call("PUT", f"{S}/draft", grace, body=_draft(0))
    assert saved.status_code == 200, saved.text
    assert cast(Json, saved.json())["expected_version"] == 1
    stale = await net.call("PUT", f"{S}/draft", grace, body=_draft(0, cadence=6))
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_version")

    headers = {**net.headers(grace), "Idempotency-Key": f"publish-{uuid.uuid4().hex[:8]}"}
    published = await net.http.post(f"{S}/publish", headers=headers)
    assert published.status_code == 201, published.text
    body = cast(Json, published.json())
    assert body["version"] == 1
    assert cast(Json, body["client_experience"])["show_team_card"] is False
    assert (
        await seed.value(
            "SELECT cadence_days FROM follow_up_policies WHERE tenant_id = $1", tenant
        )
        == 5
    )
    assert (
        await seed.value("SELECT portal_name FROM portal_branding WHERE tenant_id = $1", tenant)
        == "Brightwater Hale Client Portal"
    )
    after = cast(Json, (await net.call("GET", S, grace)).json())
    assert after["draft"] is None and cast(Json, after["published"])["version"] == 1
    again = await net.http.post(f"{S}/publish", headers=headers)  # the same key: the same answer
    assert again.status_code == 201 and cast(Json, again.json())["version"] == 1


async def test_preview_as_a_contact_on_a_walled_client_is_404(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    grace = await seed.person(tenant, "firm_admin")
    other = await seed.person(tenant, "firm_admin")
    copperleaf = await seed.site(tenant, grace.user_id, "Copperleaf")
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Tess Moreno', 'client_person') RETURNING id",
        tenant,
        copperleaf.client_id,
    )
    sample = await net.call("GET", f"{S}/preview?as={contact}", grace)
    assert sample.status_code == 200, sample.text
    assert cast(Json, sample.json())["read_only"] is True
    await net.wall(other, grace, copperleaf)
    walled = await net.call("GET", f"{S}/preview?as={contact}", grace)
    assert walled.status_code == 404, walled.text
    plain = cast(Json, (await net.call("GET", f"{S}/preview", grace)).json())
    assert (plain["sample"], plain["contact_id"]) == (True, None)
