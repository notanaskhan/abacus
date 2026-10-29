# ac-test-author: ayushkbhatia
"""Q-04-T009 (SPEC-403 AC-11): the go-live check reads a real firm through public interfaces as the
platform, with no person's session: its MFA coverage, admins, support switch, opt-in, flags and
stages; a firm below 100% MFA fails `identity.mfa_all_staff` with the count. Boundary:
`abacus_tools.go_live.collect` and `evaluate` on the migrated Postgres (Temporal absent: the
provisioning read falls back to the key state)."""

from __future__ import annotations

from datetime import datetime

import pytest

from abacus_tools import go_live, release_windows

from .support import Seeder

pytestmark = pytest.mark.asyncio


async def test_ac11_a_firm_below_full_mfa_fails_with_the_item_named(seed: Seeder) -> None:
    tenant = await seed.firm()
    await seed.person(tenant, "firm_admin")
    await seed.person(tenant, "security_admin")
    await seed.person(tenant)
    facts = await go_live.collect(tenant, release_windows.load())
    assert (facts.mfa_enrolled, facts.mfa_seats) == (0, 3)
    assert (facts.firm_admins, facts.security_admins) == (1, 1)
    assert facts.pilot_code is None  # not in the committed calendar
    assert facts.support_requests_allowed is True  # the default with no policy row
    at = datetime.fromisoformat("2027-05-24T10:00:00-05:00")
    items = {i.id: i for i in go_live.evaluate("shadow", facts, at, release_windows.load())}
    assert items["identity.mfa_all_staff"].status == "fail"
    assert items["identity.mfa_all_staff"].value == "0 of 3 staff"
    # DEC-903 (G-01-T19): roles are mapped only once every active staff member has a role
    # template (P-10); the seeded members have none, so the row fails and names them.
    assert facts.members_without_level == 3
    assert items["identity.roles_mapped"].status == "fail"
    assert "3 staff without a role template" in items["identity.roles_mapped"].value
    assert items["windows.entry"].status == "fail"
    assert all(i.value for i in items.values())

    await seed.run("UPDATE memberships SET level = 'staff' WHERE tenant_id = $1", tenant)
    facts = await go_live.collect(tenant, release_windows.load())
    items = {i.id: i for i in go_live.evaluate("shadow", facts, at, release_windows.load())}
    assert items["identity.roles_mapped"].status == "pass"


async def test_the_reads_are_the_firms_own(seed: Seeder) -> None:
    mine = await seed.firm()
    other = await seed.firm()
    for _ in range(4):
        await seed.person(other)
    await seed.person(mine)
    facts = await go_live.collect(mine, release_windows.load())
    assert facts.mfa_seats == 1
