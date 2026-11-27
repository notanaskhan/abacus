"""T-08-T31 (TASK-9032; DEC-6037): TAX-14's run read on the migrated Postgres. The run names
its version ("1065 Review Checklist v1"; TAX-14's v4 in the fixture), its check count and who
started it; each row carries the return's preparer and reviewer, its status and review level,
its office and when its checks finished; each check reads as its checklist item's words. Rows
the viewer cannot see are absent. Found on Postgres: the run query's untyped `:r IS NULL`
parameters answered 500 for every read."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import cast

import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow

from .support import Net, Seeder

pytestmark = pytest.mark.asyncio
ITEMS = [{"key": f"c-{i:02d}", "section": "Checks", "text": f"Check {i}"} for i in (1, 2, 3)]


async def test_t08t31_run_rows_name_version_people_status_and_check_words(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    manager = await seed.person(tenant)
    # `firm_manager` is derived from a manager-level membership (DEC-373).
    await seed.run(
        "UPDATE memberships SET level = 'manager' WHERE tenant_id = $1 AND user_id = $2",
        tenant, manager.user_id,
    )  # fmt: skip
    preparer = await seed.person(tenant)
    reviewer = await seed.person(tenant)
    site = await seed.site(tenant, manager.user_id, "Ridgeline")
    await seed.member(site, manager, "manager")
    await seed.member(site, preparer, "staff")
    await seed.member(site, reviewer, "reviewer")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.standards_runs', 'true', 'test-seed', 'T-08-T31')",
        tenant,
    )
    forget_flags()
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            tenant, site.engagement_id, site.client_id, site.entity_id,
            f"2025 Form 1065 {site.marker}", manager.user_id,
        ),
    )  # fmt: skip
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1065', 2025)",
        tenant, item, site.engagement_id, site.entity_id,
    )  # fmt: skip
    await seed.run_untriggered(
        "UPDATE tax_returns SET status = 'in_review', review_level = 'partner' "
        "WHERE work_item_id = $1",
        item,
    )
    for who, function in ((preparer, "preparer"), (reviewer, "manager_reviewer")):
        await seed.run(
            "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
            "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $6)",
            tenant, item, site.engagement_id, who.user_id, function, manager.user_id,
        )  # fmt: skip
    payload = json.dumps(
        {"kind": "review_checklist", "applies_to": {"form": "1065", "tax_year": 2025},
         "items": ITEMS}
    )  # fmt: skip
    parent = await seed.value(
        "INSERT INTO firm_standards (tenant_id, kind, key, name, owner_id, created_by) "
        "VALUES ($1, 'review_checklist', 'bh-1065-review-checklist', '1065 Review Checklist', "
        "$2, $2) RETURNING id",
        tenant, manager.user_id,
    )  # fmt: skip
    version = await seed.value(
        "INSERT INTO firm_standard_versions (tenant_id, parent_id, version, payload, "
        "payload_hash, drafted_by) VALUES ($1, $2, 1, $3::jsonb, $4, $5) RETURNING id",
        tenant, parent, payload, "sha256:" + hashlib.sha256(payload.encode()).hexdigest(),
        manager.user_id,
    )  # fmt: skip
    await seed.run_untriggered(  # a person publishes it (K-02); the seed stands in for them
        "UPDATE firm_standard_versions SET status = 'published', effective_from = '2026-01-01', "
        "published_by = $2, published_actor_kind = 'human', published_at = now() WHERE id = $1",
        version, manager.user_id,
    )  # fmt: skip
    run = await seed.value(
        "INSERT INTO standards_runs (tenant_id, standard_version_id, form, started_by, status) "
        "VALUES ($1, $2, '1065', $3, 'running') RETURNING id",
        tenant, version, manager.user_id,
    )  # fmt: skip
    run_item = await seed.value(
        "INSERT INTO standards_run_items (tenant_id, engagement_id, work_item_id, run_id, status, "
        "checks_total, checks_passed, completed_at) VALUES ($1, $2, $3, $4, 'exceptions', 3, 2, "
        "now()) RETURNING id",
        tenant, site.engagement_id, item, run,
    )  # fmt: skip
    # The run's system actor writes its results (insert-only), through the kernel's unit of work.
    async with uow(TenantContext(tenant, "system", "tax:standards_run")) as tx:
        for key, outcome in (("1065-v1/C-01", "pass"), ("1065-v1/C-02", "exception")):
            await tx.session.execute(
                text(
                    "INSERT INTO standards_check_results (tenant_id, run_item_id, check_key, "
                    "outcome) VALUES (:t, :i, :k, :o)"
                ),
                {"t": tenant, "i": run_item, "k": key, "o": outcome},
            )
        tx.record("standards_run.probed", target=Target("standards_run", cast(uuid.UUID, run)))

    got = await net.call("GET", f"/v1/standards-runs/{run}", manager)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["standard_label"] == "1065 Review Checklist v1"
    assert (body["version_no"], body["checks_count"]) == (1, 3)
    assert body["started_by"] == await seed.value(
        "SELECT display_name FROM users WHERE id = $1", manager.user_id
    )
    row = body["items"][0]
    assert (row["return_status"], row["review_level"]) == ("in_review", "partner")
    assert row["preparer"]["user_id"] == str(preparer.user_id)
    assert row["reviewer"]["user_id"] == str(reviewer.user_id)
    assert row["completed_at"] is not None and row["exceptions"] == 1
    checks = await net.call("GET", f"/v1/standards-runs/{run}/items/{item}/checks", manager)
    assert checks.status_code == 200, checks.text
    assert [(c["display_code"], c["title"], c["outcome"]) for c in checks.json()["items"]] == [
        ("C-01", "Check 1", "pass"),
        ("C-02", "Check 2", "exception"),
    ]
    outsider = await seed.person(tenant)
    hidden = await net.call("GET", f"/v1/standards-runs/{run}", outsider)
    assert hidden.status_code in (403, 404) or hidden.json()["items"] == [], hidden.text
