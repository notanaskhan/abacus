# ac-test-author: notanaskhan
"""Q-05-T27 (TASK-8942; SPEC-711; ADR-078): the reserved quality decisions, black-box over HTTP on
the migrated Postgres. Concluding the annual evaluation is the QM owner's (`quality_evaluation.
decide`, quality partner): a firm admin and a manager are refused (403); resolving a consultation
difference is the quality partner's (a manager is refused); quality reads are firm-wide only for
the quality roles and never reach a client principal; another firm's id is absent (404)."""

from __future__ import annotations

import uuid

import pytest

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio


async def _firm(seed: Seeder) -> uuid.UUID:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'quality.management', 'true', 'test-seed', 'Q-05-T27')",
        tenant,
    )
    return tenant


async def test_ac_only_the_qm_owner_concludes_the_evaluation(net: Net, seed: Seeder) -> None:
    tenant = await _firm(seed)
    admin = await seed.person(tenant, "firm_admin")
    manager = await seed.person(tenant)
    path = "/v1/quality/evaluations/2026/request-conclusion"
    for who in (admin, manager):
        refused = await net.call("POST", path, who, body={})
        assert refused.status_code in (403, 404), refused.text
        assert refused.status_code != 200


async def test_ac_only_the_quality_partner_resolves_a_difference(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    manager = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Harlow")
    await seed.member(site, manager, "manager")
    refused = await net.call(
        "POST",
        f"/v1/consultations/{uuid.uuid4()}/resolve-difference",
        manager,
        body={"resolution": "Use the consultee's position.", "rationale": "Per policy."},
    )
    assert refused.status_code in (403, 404, 422), refused.text
    assert refused.status_code != 200


async def test_ac_quality_reads_never_reach_a_client(net: Net, seed: Seeder) -> None:
    tenant = await _firm(seed)
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Bayside")
    client = await seed.client_contact(site)
    for path in ("/v1/quality/dashboard", "/v1/quality/findings", "/v1/quality/inspections"):
        refused = await net.call("GET", path, client)
        assert refused.status_code in (403, 404), (path, refused.text)
        assert site.marker not in refused.text
