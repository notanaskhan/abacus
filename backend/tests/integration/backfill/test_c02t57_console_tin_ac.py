# ac-test-author: ayushkbhatia
"""C-02-T57 (TASK-8945; SPEC-700; ADR-078 suite 3): the ledger console and TIN handling, black-box
over HTTP on the migrated Postgres. The console is scoped to the client entity's engagement team
and its walls: another firm reads it as absent (404, DEC-43), a person off the team and a client
principal are refused; a TIN reveal is refused to a person off the team and to another firm, and
no read answers an unmasked TIN. Offshore refusal and the reveal log naming the person are held by
the identity/evidence reveal suites; this suite holds the console's edge."""

from __future__ import annotations

import re

import pytest

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio
TIN = re.compile(r"\b\d{2}-\d{7}\b|\b\d{3}-\d{2}-\d{4}\b")


async def test_ac_the_console_is_scoped_to_the_team(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Copperleaf")
    await seed.member(site, partner, "engagement_partner")
    path = f"/v1/client-entities/{site.entity_id}/ledger-console"
    stranger = await seed.person(await seed.firm())
    absent = await net.call("GET", path, stranger)
    assert absent.status_code == 404, absent.text
    outsider = await seed.person(tenant)
    client = await seed.client_contact(site)
    for who in (outsider, client):
        refused = await net.call("GET", path, who)
        assert refused.status_code in (403, 404), refused.text
        assert site.marker not in refused.text
        assert not TIN.search(refused.text)


async def test_ac_a_tin_reveal_is_refused_off_the_team(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Copperleaf")
    await seed.member(site, partner, "engagement_partner")
    path = f"/v1/client-entities/{site.entity_id}/tin/reveal"
    outsider = await seed.person(tenant)
    stranger = await seed.person(await seed.firm())
    for who in (outsider, stranger):
        refused = await net.call("POST", path, who, body={"reason": "Vendor 1099 check"})
        assert refused.status_code in (403, 404), refused.text
        assert not TIN.search(refused.text)
