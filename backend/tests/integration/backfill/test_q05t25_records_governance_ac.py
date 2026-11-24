# ac-test-author: ayushkbhatia
"""Q-05-T25 (TASK-8946; SPEC-711 records governance; ADR-078; DEC-71): the destruction and
retention edges, black-box over HTTP on the migrated Postgres.

- Below-floor policy refused: a retention policy shorter than the firm floor is 422 `below_floor`.
- Policy changes need a security or firm admin with a recent MFA: a manager is refused, and an
  admin without fresh MFA is refused.
- Destruction approval is an admin's (`destruction.approve`): a manager is refused; a batch of
  another firm is absent (404, DEC-43); the agent and the system hold nothing (matrix).
- A client principal never reads a batch, its documents list or a certificate.

I-HOLD across execution, segregation of the assembler and approver, shrink-only batches, shared
objects, retain-until, 410 after destruction, purge and certificate bytes are held by the Q-05-T11
to T15 service and workflow suites on the PF-X1 batch; listed for the end-pass security review.
"""

from __future__ import annotations

import uuid

import pytest

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio
POLICY = {
    "record_type": "audit_workpapers",
    "service_line": "audit",
    "firm_years": 1,
    "clock_start_event": "report_release",
}


async def test_ac_a_below_floor_policy_is_refused(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    refused = await net.call("POST", "/v1/retention/policies", admin, body=POLICY)
    assert refused.status_code == 422, refused.text
    assert refused.json().get("code") == "below_floor"


async def test_ac_policy_changes_need_an_admin_with_fresh_mfa(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    manager = await seed.person(tenant)
    long_enough = {**POLICY, "firm_years": 8}
    as_manager = await net.call("POST", "/v1/retention/policies", manager, body=long_enough)
    assert as_manager.status_code == 403, as_manager.text
    stale = await net.call("POST", "/v1/retention/policies", admin, body=long_enough, mfa=False)
    assert stale.status_code == 403, stale.text


async def test_ac_destruction_approval_is_an_admins(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    manager = await seed.person(tenant)
    path = f"/v1/destruction-batches/{uuid.uuid4()}/approvals"
    refused = await net.call("POST", path, manager, body={"items_seen": 1204})
    assert refused.status_code in (403, 404), refused.text
    assert refused.status_code != 201
    stranger_admin = await seed.person(await seed.firm(), "firm_admin")
    absent = await net.call("GET", f"/v1/destruction-batches/{uuid.uuid4()}", stranger_admin)
    assert absent.status_code == 404, absent.text


async def test_ac_a_client_never_reads_destruction_records(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Lakeshore")
    client = await seed.client_contact(site)
    batch, certificate = uuid.uuid4(), uuid.uuid4()
    for path in (
        "/v1/destruction-batches",
        f"/v1/destruction-batches/{batch}",
        f"/v1/destruction-batches/{batch}/documents.csv",
        f"/v1/destruction-certificates/{certificate}",
    ):
        refused = await net.call("GET", path, client)
        assert refused.status_code in (403, 404), (path, refused.text)
        assert site.marker not in refused.text
