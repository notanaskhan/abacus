"""P-07-T30 security review (DEC-327): a client principal holds `engagement.read_metadata` for
its own engagement (SPEC-020), but the internal roster (roles, budget hours, independence
answers, join dates, approvers) is never theirs: `GET …/team` and `GET …/team/approval` answer
403 for a client user's token, while the engagement partner still reads both."""

from __future__ import annotations

from .support import Net, Seeder


async def test_review_a_client_token_cannot_read_the_team_or_its_approval(
    net: Net, seed: Seeder
) -> None:
    tenant_id = await seed.firm()
    partner = await seed.person(tenant_id)
    site = await seed.site(tenant_id, partner.user_id, "Calloway")
    await seed.member(site, partner, "engagement_partner")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'engagements.v2', 'true', 'test-seed', 'P-07-T30 review')",
        tenant_id,
    )
    client = await seed.client_contact(site)
    base = f"/v1/engagements/{site.engagement_id}"
    for path in (f"{base}/team", f"{base}/team/approval"):
        refused = await net.call("GET", path, client)
        assert refused.status_code == 403, (path, refused.text)
        assert "budget_hours" not in refused.text and "role" not in refused.json()
        allowed = await net.call("GET", path, partner)
        assert allowed.status_code == 200, (path, allowed.text)
