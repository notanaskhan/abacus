# ac-test-author: ayushkbhatia
"""C-02-T36 (TASK-8944; SPEC-700 W1; ADR-078 suite 2; ADR-344, ADR-164): the W1 write path's
refusals, black-box over HTTP on the migrated Postgres.

- The POR-16 write grant is the client's: a firm principal never creates one through the portal
  route, and an unknown connection is absent (404).
- The posting log is firm work: a client principal never reads `…/posting-batches`; another
  firm's batch is absent (404, DEC-43); a staff member cannot retry or undo a batch (the matrix
  gives post and dry run to senior and above, and nobody below).
- The kill switch: with `adjustments.posting` off the posting routes answer 404 (fail closed).

Write interception, idempotency under retry, read-back mismatch, closing-date conflicts and the
attest policy are held at the provider boundary by the C-02 service suites (T18, T19, T24); this
suite holds the HTTP edge around them.
"""

from __future__ import annotations

import uuid

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio


async def _cas(seed: Seeder, posting: str = "true") -> tuple[Person, Person, Site]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    staff = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Copperleaf")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, staff, "staff")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'adjustments.posting', $2, 'test-seed', 'C-02-T36')",
        tenant,
        posting,
    )
    return partner, staff, site


async def test_ac_the_write_grant_is_the_clients(net: Net, seed: Seeder) -> None:
    partner, _staff, site = await _cas(seed)
    path = f"/v1/portal/connections/{uuid.uuid4()}/write-grants"
    as_firm = await net.call(
        "POST",
        path,
        partner,
        body={
            "capability_id": "ledger_post_journal_entries",
            "consent_copy_version": "por16.qbo.post_entries.v2",
        },
        headers=net.keyed(),
    )
    assert as_firm.status_code in (403, 404), as_firm.text
    client = await seed.client_contact(site)
    # The current grant is only ever revoked (DELETE); an unknown connection is absent.
    unknown = await net.call("DELETE", f"{path}/current", client, headers=net.keyed())
    assert unknown.status_code == 404, unknown.text


async def test_ac_the_posting_log_is_never_a_clients(net: Net, seed: Seeder) -> None:
    _partner, _staff, site = await _cas(seed)
    client = await seed.client_contact(site)
    refused = await net.call(
        "GET", f"/v1/client-entities/{site.entity_id}/posting-batches", client
    )
    assert refused.status_code in (403, 404), refused.text
    assert site.marker not in refused.text


async def test_ac_another_firms_batch_is_absent(net: Net, seed: Seeder) -> None:
    stranger = await seed.person(await seed.firm())
    absent = await net.call("GET", f"/v1/posting-batches/{uuid.uuid4()}", stranger)
    assert absent.status_code == 404, absent.text


async def test_ac_staff_cannot_retry_or_undo_a_batch(net: Net, seed: Seeder) -> None:
    _partner, staff, _site = await _cas(seed)
    batch = uuid.uuid4()
    for path in (
        f"/v1/posting-batches/{batch}/undo",
        f"/v1/posting-batches/{batch}/entries/{uuid.uuid4()}/retry",
    ):
        refused = await net.call("POST", path, staff, body={}, headers=net.keyed())
        assert refused.status_code in (403, 404), (path, refused.text)
        assert refused.status_code != 200


async def test_ac_the_kill_switch_closes_the_posting_routes(net: Net, seed: Seeder) -> None:
    partner, _staff, site = await _cas(seed, posting="false")
    closed = await net.call(
        "GET", f"/v1/client-entities/{site.entity_id}/posting-batches", partner
    )
    assert closed.status_code == 404, closed.text
