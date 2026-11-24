# ac-test-author: ayushkbhatia
"""Q-05-T26 (TASK-8941; SPEC-711 AC-15 to AC-18; ADR-078; ADR P-43): post-issuance access,
black-box over HTTP on the migrated Postgres, and the archived-write allowlist through the repo's
own rule (ARCHIVE-001).

- The `post_issuance` archived-write kind is settable only from the allowlisted services
  (`tests/unit/quality/test_q05t26_archive_rule.py`, the repo rule ARCHIVE-001).
- Only the engagement partner decides, with fresh MFA and a rationale: a manager gets 403, the
  partner without a recent MFA gets 403, an empty rationale is 422, and none writes anything.
- Only the engagement partner reopens for reissue (a manager gets 403).
- A case opens only on an archived audit (409 `not_archived` before the lock).
- Another firm reads the cases as absent (404, DEC-43); a client principal never reads them.

Later decisions: DEC-5724 (the decision is recorded on the case row, not a P-04 card), DEC-5936
(the decision logs its archive addition; that path needs a locked archive and is held by the
service suites).
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio


async def _audit(seed: Seeder) -> tuple[Person, Person, Site, uuid.UUID]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    manager = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Northwind")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit.post_issuance', 'true', 'test-seed', 'Q-05-T26')",
        tenant,
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            # `site()` opens the engagement with its one assurance work item (the audit).
            "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 "
            "AND kind = 'assurance'",
            tenant,
            site.engagement_id,
        ),
    )
    return partner, manager, site, item


def _cases(item: uuid.UUID) -> str:
    return f"/v1/audits/{item}/post-issuance/cases"


async def test_ac17_only_the_partner_decides_with_fresh_mfa_and_a_rationale(
    net: Net, seed: Seeder
) -> None:
    partner, manager, site, item = await _audit(seed)
    path = f"{_cases(item)}/{uuid.uuid4()}/decision"
    body = {"decision": "no_action", "rationale": "Below clearly trivial."}
    before = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1", site.tenant_id
    )
    as_manager = await net.call("POST", path, manager, body=body, headers=net.keyed())
    assert as_manager.status_code == 403, as_manager.text
    stale = await net.call("POST", path, partner, body=body, mfa=False, headers=net.keyed())
    assert stale.status_code == 403, stale.text
    empty = await net.call(
        "POST", path, partner, body={"decision": "no_action", "rationale": ""}, headers=net.keyed()
    )
    assert empty.status_code == 422, empty.text
    after = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1", site.tenant_id
    )
    assert after == before


async def test_ac18_only_the_partner_reopens_for_reissue(net: Net, seed: Seeder) -> None:
    _partner, manager, _site, item = await _audit(seed)
    refused = await net.call(
        "POST",
        f"{_cases(item)}/{uuid.uuid4()}/reopen-for-reissue",
        manager,
        body={},
        headers=net.keyed(),
    )
    assert refused.status_code == 403, refused.text


async def test_ac15_a_case_opens_only_on_an_archived_audit(net: Net, seed: Seeder) -> None:
    partner, _manager, site, item = await _audit(seed)
    opened = await net.call(
        "POST",
        _cases(item),
        partner,
        body={
            "type": "subsequently_discovered_facts",
            "source_kind": "other",
            "description": "Harborline issued a corrected certification",
        },
        headers=net.keyed(),
    )
    assert opened.status_code == 409, opened.text
    assert opened.json().get("detail") == "not_archived"
    count = await seed.value(
        "SELECT count(*) FROM post_issuance_events WHERE tenant_id = $1", site.tenant_id
    )
    assert count == 0


async def test_ac_another_firm_and_a_client_never_read_the_cases(net: Net, seed: Seeder) -> None:
    _partner, _manager, site, item = await _audit(seed)
    stranger = await seed.person(await seed.firm())
    absent = await net.call("GET", _cases(item), stranger)
    assert absent.status_code == 404, absent.text
    client = await seed.client_contact(site)
    refused = await net.call("GET", _cases(item), client)
    assert refused.status_code in (403, 404), refused.text
    assert site.marker not in refused.text
