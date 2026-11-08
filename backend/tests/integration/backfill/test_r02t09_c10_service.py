# ac-test-author: ayushkbhatia
"""R-02-T09 (TASK-6205; R-02 §3.5 AC-17 to AC-20; SPEC-646; DEC-2805): the C10 registry service.

Row acceptance: "Publishing the same release twice yields one version, Meera Shah's read model
lists only her Ridgeline K-1, a draft without a watermarked render is refused, and a
folder-provider test shows Northwind's FIL-01 Deliverables folder listing the same released
deliverables with walled items absent." (Meera's read model is the unit suite
`tests/unit/reporting/test_r02t09_portal_rail.py`.)

Boundary: the service inside a unit of work as the publishing partner, against the migrated test
database; the folder over HTTP as the signed-in viewer.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.reporting.api import (
    DeliverableAudience,
    DeliverableSpec,
    DraftWithoutWatermark,
    publish_deliverable,
    withdraw_deliverable,
)

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio


async def _work_item(net: Net, site: Site, by: Person) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'audit', 'PY2025 plan audit', $4) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            by.user_id,
        ),
    )


async def _version(net: Net, site: Site, work_item: uuid.UUID, name: str) -> uuid.UUID:
    item = await net.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, work_item_id, folder_kind, title, "
        "created_by_kind, created_by_id) VALUES ($1, $2, $3, 'source_documents', $4, 'system', "
        "'seed') RETURNING id",
        site.tenant_id,
        site.engagement_id,
        work_item,
        name,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    return cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method, display_name) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 2048, "
            "'application/pdf', 'upload', 'uploaded', $6) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            item,
            fingerprint,
            f"tenants/{site.tenant_id}/sha256/{fingerprint}",
            name,
        ),
    )


def _spec(
    site: Site, work_item: uuid.UUID, version: uuid.UUID, by: Person, **over: Any
) -> DeliverableSpec:
    fields: dict[str, Any] = {
        "client_id": site.client_id,
        "kind": "auditor_report",
        "title": "Independent auditor's report",
        "source_module": "assurance",
        "source_ref": f"release:{work_item}",
        "evidence_version_id": version,
        "render_hash": hashlib.sha256(version.bytes).hexdigest(),
        "page_count": 3,
        "audiences": [DeliverableAudience("work_item", work_item)],
        "published_by_user_id": by.user_id,
        "engagement_id": site.engagement_id,
        "work_item_id": work_item,
    }
    fields.update(over)
    return DeliverableSpec(**fields)


def _as(by: Person) -> TenantContext:
    return TenantContext(by.tenant_id, "human", str(by.user_id))


async def _northwind(net: Net) -> tuple[Site, Person, Person, uuid.UUID]:
    tenant = await net.seed.firm()
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'files.browser', 'true', 'test-seed', 'R-02-T09')",
        tenant,
    )
    forget_flags()
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Northwind Robotics 401(k) Plan")
    margaret = await net.seed.person(tenant)
    await net.seed.member(site, margaret, "engagement_partner")
    return site, admin, margaret, await _work_item(net, site, admin)


async def test_ac17_publishing_the_same_release_twice_yields_one_version(net: Net) -> None:
    site, _admin, margaret, work_item = await _northwind(net)
    version = await _version(net, site, work_item, "Independent auditor's report.pdf")
    async with uow(_as(margaret)) as tx:
        first = await publish_deliverable(tx, _spec(site, work_item, version, margaret))
    async with uow(_as(margaret)) as tx:
        again = await publish_deliverable(tx, _spec(site, work_item, version, margaret))
    assert first.created and not again.created
    assert (again.deliverable_id, again.version_id, again.version_no) == (
        first.deliverable_id,
        first.version_id,
        1,
    )
    assert (
        await net.seed.value(
            "SELECT count(*) FROM deliverable_versions WHERE deliverable_id = $1",
            first.deliverable_id,
        )
        == 1
    )
    assert (
        await net.seed.value(
            "SELECT count(*) FROM deliverable_events WHERE deliverable_version_id = $1 "
            "AND kind = 'published'",
            first.version_id,
        )
        == 1
    )


async def test_ac18_a_draft_without_a_watermarked_render_is_refused(net: Net) -> None:
    site, _admin, margaret, work_item = await _northwind(net)
    version = await _version(net, site, work_item, "Financial statements draft v3.pdf")
    draft = _spec(
        site,
        work_item,
        version,
        margaret,
        kind="fs_draft",
        title="Financial statements and supplemental schedules",
        source_ref=f"statement_version:{uuid.uuid4()}",
        is_draft=True,
        page_comments=True,
    )
    with pytest.raises(DraftWithoutWatermark):
        async with uow(_as(margaret)) as tx:
            await publish_deliverable(tx, draft)
    assert await net.seed.value("SELECT count(*) FROM deliverables") == 0


async def test_ac19_a_newer_version_supersedes_and_a_withdrawal_needs_a_reason(net: Net) -> None:
    site, _admin, margaret, work_item = await _northwind(net)
    v1 = await _version(net, site, work_item, "report v1.pdf")
    v2 = await _version(net, site, work_item, "report v2.pdf")
    async with uow(_as(margaret)) as tx:
        first = await publish_deliverable(tx, _spec(site, work_item, v1, margaret))
    async with uow(_as(margaret)) as tx:
        second = await publish_deliverable(tx, _spec(site, work_item, v2, margaret))
    assert second.version_no == 2 and second.deliverable_id == first.deliverable_id
    kinds = await net.seed.fetch(
        "SELECT kind FROM deliverable_events WHERE deliverable_version_id = $1 ORDER BY kind",
        first.version_id,
    )
    assert [r["kind"] for r in kinds] == ["published", "superseded"]
    async with uow(_as(margaret)) as tx:
        await withdraw_deliverable(tx, second.version_id, "wrong_file", margaret.user_id, "x")
    withdrawn = await net.seed.fetch(
        "SELECT reason_code, note_sealed IS NOT NULL AS sealed FROM deliverable_events "
        "WHERE deliverable_version_id = $1 AND kind = 'withdrawn'",
        second.version_id,
    )
    assert [(r["reason_code"], r["sealed"]) for r in withdrawn] == [("wrong_file", True)]


async def test_the_deliverables_folder_lists_released_deliverables_and_walls_hide_them(
    net: Net,
) -> None:
    site, admin, margaret, work_item = await _northwind(net)
    hannah = await net.seed.person(site.tenant_id)
    await net.seed.member(site, hannah, "senior")
    report = await _version(net, site, work_item, "Independent auditor's report.pdf")
    await _version(
        net, site, work_item, "Bank statement.pdf"
    )  # a source document, not a deliverable
    async with uow(_as(margaret)) as tx:
        await publish_deliverable(tx, _spec(site, work_item, report, margaret))
    path = f"/v1/files/folders/folder:{work_item}:deliverables/items"
    listed = await net.call("GET", path, hannah)
    assert listed.status_code == 200, listed.text
    names = [r["display_name"] for r in listed.json()["items"]]
    assert names == ["Independent auditor's report.pdf"]
    await net.wall(admin, hannah, site)
    walled = await net.call("GET", path, hannah)
    assert walled.status_code in (200, 404)
    if walled.status_code == 200:
        assert walled.json()["items"] == []
