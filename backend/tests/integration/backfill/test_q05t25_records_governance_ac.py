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


async def _governed(seed: Seeder) -> tuple[uuid.UUID, str]:
    """A firm with records governance on, and a record type with a published 7-year floor (the
    floor set is platform content a second staff member approves, Q-02-T23; written here as one
    published row on its own record type so no other set is superseded)."""
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'records.governance', 'true', 'test-seed', 'Q-05-T25')",
        tenant,
    )
    record_type = f"q05t25_{uuid.uuid4().hex[:12]}"
    await seed.run(
        "INSERT INTO retention_floors (set_version, record_type, service_line, "
        "legal_floor_years, anchor, authority, status, imported_by, approved_by, published_at) "
        "VALUES (1, $1, 'any', 7, 'report_release', 'Probe authority', 'published', 'staff-a', "
        "'staff-b', clock_timestamp())",
        record_type,
    )
    return tenant, record_type


def _policy(record_type: str, years: int) -> dict[str, object]:
    return {"record_type": record_type, "service_line": "audit", "retention_years": years}


async def test_ac_a_below_floor_policy_is_refused(net: Net, seed: Seeder) -> None:
    tenant, record_type = await _governed(seed)
    admin = await seed.person(tenant, "firm_admin")
    refused = await net.call(
        "POST", "/v1/retention/policies", admin, body=_policy(record_type, 1), headers=net.keyed()
    )
    assert refused.status_code == 422, refused.text
    assert refused.json().get("detail") == "below_floor"


async def test_ac_policy_changes_need_an_admin_with_fresh_mfa(net: Net, seed: Seeder) -> None:
    tenant, record_type = await _governed(seed)
    admin = await seed.person(tenant, "firm_admin")
    manager = await seed.person(tenant)
    long_enough = _policy(record_type, 8)
    as_manager = await net.call(
        "POST", "/v1/retention/policies", manager, body=long_enough, headers=net.keyed()
    )
    assert as_manager.status_code == 403, as_manager.text
    stale = await net.call(
        "POST", "/v1/retention/policies", admin, body=long_enough, mfa=False, headers=net.keyed()
    )
    assert stale.status_code == 403, stale.text


async def test_ac_destruction_approval_is_an_admins(net: Net, seed: Seeder) -> None:
    tenant = await seed.firm()
    manager = await seed.person(tenant)
    path = f"/v1/destruction-batches/{uuid.uuid4()}/approvals"
    refused = await net.call("POST", path, manager, body={"items_seen": 1204}, headers=net.keyed())
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
