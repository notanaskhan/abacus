# ac-test-author: notanaskhan
"""T-08-T27 (TASK-8940; SPEC-710 AC-14, AC-18, AC-24, AC-25, AC-34, AC-36; ADR-078): the first
independent suite over AY's amber T-08 code, black-box over HTTP on the migrated Postgres.

- AC-18: every portal principal gets 403 on `/v1/filing-deadlines*`.
- AC-24: acceptance of a two-year explanation is a person's at the reviewer level: a preparer
  (staff) is refused (403) before anything is written; another firm's reader gets 404 (DEC-43).
- AC-36 / AC-34: with its flag off a T-08 route answers 404 (the flag gates, fail closed).
- AC-25 is computation (staleness is never stored): a changed value is not "accepted"; the
  service suites hold it at the compute boundary; this suite holds the HTTP refusals around it.

Later decisions this follows instead of the spec's words: DEC-137 (flag expiry overrides, so
AC-34's date is not asserted), DEC-43 (other firm 404, never 403).
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str, value: str = "true") -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, $3, 'test-seed', 'T-08-T27 AC suite') "
        "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
        tenant,
        flag,
        value,
    )


async def _return(seed: Seeder, site: Site, by: Person) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'tax_return', $4, $5) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            f"Form 1040 {site.marker}",
            by.user_id,
        ),
    )


async def test_ac18_every_portal_principal_gets_403_on_filing_deadlines(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    await _flag(seed, tenant, "practice.filing_deadlines")
    for role in ("client_admin", "client_contributor"):
        client = await seed.client_contact(site, role)
        for path in (
            "/v1/filing-deadlines",
            "/v1/filing-deadlines/export",
            f"/v1/filing-deadlines/{uuid.uuid4()}",
        ):
            refused = await net.call("GET", path, client)
            assert refused.status_code == 403, (role, path, refused.text)
            assert site.marker not in refused.text


async def test_ac24_a_preparer_cannot_accept_an_explanation(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    preparer = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, preparer, "staff")
    await _flag(seed, tenant, "tax.two_year")
    return_id = await _return(seed, site, partner)
    path = f"/v1/tax-returns/{return_id}/two-year/lines/scha.11/explanation:accept"
    body = {"explanation_version_id": str(uuid.uuid4()), "values_hash": "0" * 64}
    before = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    refused = await net.call("POST", path, preparer, body=body)
    assert refused.status_code == 403, refused.text
    after = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    assert after == before  # nothing was written for a refused acceptance


async def test_ac24_another_firm_sees_the_return_as_absent(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    await _flag(seed, tenant, "tax.two_year")
    return_id = await _return(seed, site, partner)
    other_firm = await seed.firm()
    stranger = await seed.person(other_firm)
    await _flag(seed, other_firm, "tax.two_year")
    read = await net.call("GET", f"/v1/tax-returns/{return_id}/two-year", stranger)
    assert read.status_code == 404, read.text
    assert site.marker not in read.text


async def test_ac36_a_t08_route_answers_404_with_its_flag_off(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    return_id = await _return(seed, site, partner)
    await _flag(seed, tenant, "tax.two_year", "false")
    read = await net.call("GET", f"/v1/tax-returns/{return_id}/two-year", partner)
    assert read.status_code == 404, read.text
    await _flag(seed, tenant, "practice.filing_deadlines", "false")
    deadlines = await net.call("GET", "/v1/filing-deadlines", partner)
    assert deadlines.status_code == 404, deadlines.text
