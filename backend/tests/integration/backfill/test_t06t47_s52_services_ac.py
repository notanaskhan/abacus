# ac-test-author: notanaskhan
"""T-06-T47 (TASK-8943; T-06 §3 F1-F4, F6; ADR-078; DEC-88): AY's S52 entity-return services
(fixed assets, book-tax and basis, states and PTET, the hand-off landing), black-box over HTTP on
the migrated Postgres. What every one of them promises before its figures: another firm's return is
absent (404, DEC-43), a client principal never reads the workpapers, a person off the engagement
reads nothing (walls, DEC-88), and the hand-off landing of a return with no hand-off is empty
rather than invented. The figure-level ACs (TXP-03 to TXP-09 a-e) are held by the service and
golden suites on the Ridgeline scenario; this suite holds the refusals around them."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
READS = ("fixed-assets", "basis", "states", "handoff")
FLAGS = ("tax.entity_workspace", "tax.entity_depth", "tax.tb_handoff")


async def _return(seed: Seeder) -> tuple[Person, Site, uuid.UUID]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Ridgeline")
    await seed.member(site, partner, "engagement_partner")
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-06-T47')",
            tenant,
            flag,
        )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'tax_return', $4, $5) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            f"2025 Form 1065 {site.marker}",
            partner.user_id,
        ),
    )
    return partner, site, item


async def test_ac_another_firm_reads_every_s52_workpaper_as_absent(net: Net, seed: Seeder) -> None:
    _partner, site, item = await _return(seed)
    stranger = await seed.person(await seed.firm())
    for read in READS:
        found = await net.call("GET", f"/v1/tax-returns/{item}/{read}", stranger)
        assert found.status_code == 404, (read, found.text)
        assert site.marker not in found.text


async def test_ac_a_client_principal_never_reads_the_workpapers(net: Net, seed: Seeder) -> None:
    _partner, site, item = await _return(seed)
    client = await seed.client_contact(site)
    for read in READS:
        refused = await net.call("GET", f"/v1/tax-returns/{item}/{read}", client)
        assert refused.status_code in (403, 404), (read, refused.text)
        assert site.marker not in refused.text


async def test_ac_dec88_a_person_off_the_engagement_reads_nothing(net: Net, seed: Seeder) -> None:
    _partner, site, item = await _return(seed)
    outsider = await seed.person(site.tenant_id)
    for read in READS:
        refused = await net.call("GET", f"/v1/tax-returns/{item}/{read}", outsider)
        assert refused.status_code in (403, 404), (read, refused.text)
        assert site.marker not in refused.text


async def test_ac_f6_a_return_with_no_hand_off_has_an_empty_landing(
    net: Net, seed: Seeder
) -> None:
    partner, _site, item = await _return(seed)
    landing = await net.call("GET", f"/v1/tax-returns/{item}/handoff", partner)
    if landing.status_code == 200:
        body = landing.json()
        assert body.get("handoff_id") is None
        assert body.get("book_income") is None
        assert body.get("candidates", []) == []
    else:  # a work item with no return record is absent, never an invented landing
        assert landing.status_code == 404, landing.text
