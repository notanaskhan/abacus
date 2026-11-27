"""T-08-T32 (TASK-9033; DEC-6038): TAX-15's queue and detail reads on the migrated Postgres. An
opportunity on a return the partner may see reads with its consent basis, its owner and its tax
year (additive); a client filter keeps the per-return view to that client; a person outside the
walls sees nothing and no count of it."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.kernel.flags import forget_flags

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio


async def test_t08t32_queue_and_detail_carry_consent_owner_and_year(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        partner.user_id,
    )
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.planning', 'true', 'test-seed', 'T-08-T32')",
        tenant,
    )
    forget_flags()
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            tenant, site.engagement_id, site.client_id, site.entity_id,
            f"2025 Form 1040 {site.marker}", partner.user_id,
        ),
    )  # fmt: skip
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        tenant, item, site.engagement_id, site.entity_id,
    )  # fmt: skip
    opportunity = await seed.value(
        "INSERT INTO planning_opportunities (tenant_id, engagement_id, work_item_id, client_id, "
        "source_kind, rule_key, category, title, body, status, est_savings, savings_basis, "
        "owner_user_id) VALUES ($1, $2, $3, $4, 'rule', 'charitable.daf_bunching', "
        "'Charitable giving', 'Bunch 2026–2027 gifts through a donor-advised fund', "  # noqa: RUF001 -- the design's en dash
        "'[]'::jsonb, 'open', 1810, '{\"rate\": \"0.32\"}'::jsonb, $5) "
        "RETURNING id",
        tenant, site.engagement_id, item, site.client_id, partner.user_id,
    )  # fmt: skip

    listed = await net.call(
        "GET", "/v1/planning-opportunities", partner, params={"client_id": str(site.client_id)}
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["opportunity_id"] == str(opportunity)
    assert (row["consent_basis"], row["owner_user_id"], row["tax_year"]) == (
        "301_7216_2h",
        str(partner.user_id),
        2025,
    )
    other = await net.call(
        "GET", "/v1/planning-opportunities", partner, params={"client_id": str(uuid.uuid4())}
    )
    assert other.status_code == 200 and other.json()["total"] == 0  # the per-return view (f)
    detail = await net.call("GET", f"/v1/planning-opportunities/{opportunity}", partner)
    assert detail.status_code == 200, detail.text
    assert detail.json()["tax_year"] == 2025
    outsider = await seed.person(tenant)
    hidden = await net.call("GET", "/v1/planning-opportunities", outsider)
    assert hidden.status_code in (403, 404) or hidden.json()["total"] == 0, hidden.text
