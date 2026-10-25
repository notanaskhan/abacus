"""A-01-T08 to T10 against Postgres (SPEC-330 AC-19, AC-21, AC-22, AC-25, AC-27; DEC-311 to
DEC-313): walls hold with no counts, metadata-only readers see metadata tags only, the rail
renders registered rows only (a missing or failing provider hides its row), and the C5 v1.1
request facts are filled for the firm and never for a client.

The services run as the app role (grants and row-level security); seed rows go through the
superuser."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow
from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance import cockpit, index, sections
from abacus.modules.assurance.sections import IndexTag, SectionState
from abacus.modules.evidence import inbox
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.identity.authz import recording_checks
from abacus.modules.requests import binders
from abacus.modules.requests.api import pbc_counts, source_documents
from abacus.modules.requests.contract import BinderRequestRowOut, for_viewer

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

assert assurance_api.ROUTERS  # registers A-01's segments, Overview rows and tags


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@dataclass(frozen=True)
class World:
    seed: Seeder
    tenant: uuid.UUID
    admin: AuthContext
    partner: AuthContext
    partner_person: Person
    open_item: uuid.UUID  # Northwind-like work item with a published PBC binder
    walled_item: uuid.UUID  # another client's work item
    walled_client: uuid.UUID
    binder: uuid.UUID
    requested: uuid.UUID
    uploaded: uuid.UUID
    version: uuid.UUID
    inbox_file: uuid.UUID


async def _assurance_item(seed: Seeder, engagement: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    admin = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        admin.user_id,
    )
    partner = await seed.person(tenant)
    engagements: list[uuid.UUID] = []
    for name in ("Open plan", "Walled plan"):
        entity = await seed.entity(tenant, name)
        engagement = await seed.engagement(tenant, entity, partner.user_id)
        await seed.member(engagement, partner, "engagement_partner")
        engagements.append(engagement)
    open_item = await _assurance_item(seed, engagements[0])
    walled_item = await _assurance_item(seed, engagements[1])
    walled_client = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagements[1]),
    )
    dana = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
            "('https://identity.abacus.local', $1, $2, 'Dana Kowalski') RETURNING id",
            f"sub-{uuid.uuid4().hex}",
            f"dana-{uuid.uuid4().hex[:6]}@example.test",
        ),
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status, kind) VALUES ($1, $2, 'active', "
        "'client')",
        tenant,
        dana,
    )
    await seed.run(
        "INSERT INTO client_access_grants (id, tenant_id, user_id, role, scope_kind, scope_id, "
        "granted_by, status) VALUES ($1, $2, $3, 'owner', 'engagement', $4, $5, 'active')",
        uuid.uuid4(),
        tenant,
        dana,
        engagements[0],
        partner.user_id,
    )
    binder = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, created_at, kind, status, "
            "published_at, published_by) VALUES ($1, $2, clock_timestamp(), 'pbc', 'published', "
            "clock_timestamp(), $3) RETURNING id",
            tenant,
            engagements[0],
            partner.user_id,
        ),
    )
    categories = [
        cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO request_categories (tenant_id, request_list_id, name, position, "
                "family) VALUES ($1, $2, $3, $4, 'audit_area') RETURNING id",
                tenant,
                binder,
                name,
                position,
            ),
        )
        for position, name in enumerate(("Plan documents", "Cash"))
    ]

    async def request(title: str, status: str, category: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, title, audit_area, category_id, status, created_by, created_at, "
                "client_visible, client_assignee_user_id, due_on, requested_at) VALUES ($1, $2, "
                "$3, $4, $4, 'Area', $5, $6, $7, clock_timestamp(), true, $8, '2026-09-18', "
                "clock_timestamp()) RETURNING id",
                tenant,
                engagements[0],
                binder,
                title,
                category,
                status,
                partner.user_id,
                dana,
            ),
        )

    requested = await request("IRS opinion letter", "requested", categories[0])
    uploaded = await request("Certified trust report", "uploaded", categories[0])
    await request("Summary plan description", "received", categories[0])
    await request("Bank statements", "requested", categories[1])
    evidence_item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Harborline Certification PY2025 signed.pdf', "
        "'human', 'seed') RETURNING id",
        tenant,
        engagements[0],
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
            tenant,
            engagements[0],
            evidence_item,
            fingerprint,
            f"tenants/{tenant}/sha256/{fingerprint}",
        ),
    )
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagements[0],
        uploaded,
        version,
    )
    inbox_file = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO inbox_files (tenant_id, engagement_id, file_name, media_type, "
            "size_bytes, fingerprint, storage_key, storage_version_id, uploaded_by, "
            "uploaded_by_staff, status, assigned_item_id, assigned_version_id, decided_by, "
            "decided_at) VALUES ($1, $2, 'cert.pdf', 'application/pdf', 10, $3, $4, 'v1', $5, "
            "true, 'assigned', $6, $7, $5, clock_timestamp()) RETURNING id",
            tenant,
            engagements[0],
            fingerprint,
            f"tenants/{tenant}/sha256/{fingerprint}",
            partner.user_id,
            uploaded,
            version,
        ),
    )
    admin_ctx = replace(admin.context(), firm_role="firm_admin")
    return World(
        seed,
        tenant,
        admin_ctx,
        partner.context(),
        partner,
        open_item,
        walled_item,
        walled_client,
        binder,
        requested,
        uploaded,
        version,
        inbox_file,
    )


async def _wall(world: World) -> None:
    await world.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        world.tenant,
        world.partner.user_id,
        world.walled_client,
        world.admin.user_id,
    )


# --- AC-19: walls ------------------------------------------------------------------------------


async def test_ac19_a_walled_audit_is_absent_everywhere_and_the_totals_foot(world: World) -> None:
    before, _ = await index.audits_index(
        world.partner, index.IndexFilters(), cursor=None, limit=50
    )
    assert before.total == 2
    await _wall(world)
    page, summary = await index.audits_index(
        world.partner, index.IndexFilters(), cursor=None, limit=50
    )
    assert [r.work_item_id for r in page.items] == [world.open_item]
    assert page.total == 1 and sum(page.counts.values()) == 1
    assert sum(f.n for f in page.facets["segment"]) == 1
    assert summary.fs_audit + summary.ebp + summary.review + summary.compilation_preparation == 1
    with pytest.raises(Forbidden) as denied:  # the app answers a wall 404 (DEC-43)
        await cockpit.audit_cockpit(world.partner, world.walled_item)
    assert denied.value.layer == "wall"
    assert world.walled_item not in await pbc_counts(world.partner, [world.walled_item])


async def test_ac19_the_index_cursor_walks_every_row_once(world: World) -> None:
    first, _ = await index.audits_index(world.admin, index.IndexFilters(), cursor=None, limit=1)
    assert len(first.items) == 1 and first.next_cursor is not None
    second, _ = await index.audits_index(
        world.admin, index.IndexFilters(), cursor=first.next_cursor, limit=1
    )
    assert {first.items[0].work_item_id, second.items[0].work_item_id} == {
        world.open_item,
        world.walled_item,
    }
    assert second.next_cursor is None


# --- AC-21: metadata and content tags -----------------------------------------------------------


async def _content_tag(
    tenant: TenantContext, ids: Sequence[uuid.UUID]
) -> Mapping[uuid.UUID, Sequence[IndexTag]]:
    del tenant
    return {i: [IndexTag("pending", "Materiality decision pending")] for i in ids}


async def _metadata_tag(
    tenant: TenantContext, ids: Sequence[uuid.UUID]
) -> Mapping[uuid.UUID, Sequence[IndexTag]]:
    del tenant
    return {i: [IndexTag("seen", "Seen")] for i in ids}


async def test_ac21_a_metadata_only_reader_never_sees_a_content_tag(world: World) -> None:
    sections.register_index_tag("test_content", _content_tag, "content")
    sections.register_index_tag("test_metadata", _metadata_tag, "metadata")
    try:
        admin, _ = await index.audits_index(
            world.admin, index.IndexFilters(), cursor=None, limit=50
        )
        partner, _ = await index.audits_index(
            world.partner, index.IndexFilters(), cursor=None, limit=50
        )
    finally:
        sections._TAGS.pop("test_content", None)  # pyright: ignore[reportPrivateUsage] -- test cleanup of a slot
        sections._TAGS.pop("test_metadata", None)  # pyright: ignore[reportPrivateUsage] -- test cleanup of a slot
    for row in admin.items:
        assert [t.code for t in row.tags if t.source.startswith("test_")] == ["seen"]
    for row in partner.items:
        assert sorted(t.code for t in row.tags if t.source.startswith("test_")) == [
            "pending",
            "seen",
        ]


# --- AC-22: registered rows only ----------------------------------------------------------------


async def _trial_balance(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
    del tenant, work_item_id
    return SectionState(None, "sub_line", sub_line="Not started")


async def _hidden(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
    del tenant, work_item_id
    return None


async def _broken(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
    del tenant, work_item_id
    raise RuntimeError("provider down")


async def test_ac22_a_later_epic_registers_a_row_and_unanswered_rows_never_render(
    world: World,
) -> None:
    sections.register_audit_section(
        "trial_balance", "planning", 0, "AUD-06", _trial_balance, title="Trial Balance"
    )
    sections.register_audit_section("hidden_row", "planning", 1, "AUD-07", _hidden)
    sections.register_audit_section("broken_row", "fieldwork", 0, "AUD-11", _broken)
    try:
        view = await cockpit.audit_cockpit(world.partner, world.open_item)
    finally:
        for key in ("trial_balance", "hidden_row", "broken_row"):
            sections._SECTIONS.pop(key, None)  # pyright: ignore[reportPrivateUsage] -- test cleanup of a slot
    planning = next(b for b in view.bands if b.key == "planning")
    assert [(r.key, r.title, r.sub_line) for r in planning.rows] == [
        ("trial_balance", "Trial Balance", "Not started")
    ]
    fieldwork = next(b for b in view.bands if b.key == "fieldwork")
    assert fieldwork.rows == []
    assert [b.key for b in view.bands] == [
        "overview",
        "planning",
        "fieldwork",
        "completion",
        "reporting",
    ]
    overview = next(b for b in view.bands if b.key == "overview")
    assert {r.key: r.sub_line for r in overview.rows}["source_documents"] == "1 of 4 received"


async def test_ac24_the_metadata_only_cockpit_has_no_bands_dock_or_actions(world: World) -> None:
    view = await cockpit.audit_cockpit(world.admin, world.open_item)
    assert view.overview.name == "Open plan"
    assert (view.bands, view.dock_tabs, view.allowed_actions) == ([], [], [])
    partner = await cockpit.audit_cockpit(world.partner, world.open_item)
    assert partner.dock_tabs == ["agent", "viewer"]
    assert "assurance.record_phase" in partner.allowed_actions


# --- AC-25 to AC-27: C5 v1.1 facts, Source Documents, PBC counts --------------------------------


async def test_ac25_the_firm_reads_owed_by_latest_upload_match_and_linked(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def picks(
        tenant: TenantContext, files: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[uuid.UUID, int]]]:
        del tenant
        return {f: [(world.uploaded, 94)] for f in files if f == world.inbox_file}

    monkeypatch.setattr(inbox, "_picks", picks)
    page = await binders.binder_requests(world.partner, world.binder, None, None)
    rows = {r.id: r for r in page.items}
    asked = rows[world.requested]
    assert asked.owed_by is not None
    assert (asked.owed_by.kind, asked.owed_by.display) == ("client_contact", "Dana Kowalski")
    assert asked.latest_upload is None and asked.linked_count is None
    up = rows[world.uploaded]
    assert up.owed_by is None  # an upload awaiting review owes nothing
    assert up.latest_upload is not None
    assert up.latest_upload.evidence_version_id == world.version
    assert up.latest_upload.path_label == "Harborline Certification PY2025 signed.pdf"
    assert up.latest_upload.uploader_kind == "client"
    assert (up.match_confidence, up.linked_count) == (94, 1)
    out = BinderRequestRowOut.model_validate(up, from_attributes=True)
    assert out.match_confidence == 94 and out.latest_upload is not None
    client = replace(world.partner, client=True)
    hidden = for_viewer(out, client)
    assert (hidden.owed_by, hidden.latest_upload, hidden.match_confidence) == (None, None, None)


async def test_ac26_source_documents_group_and_sort_missing_first(world: World) -> None:
    docs = await source_documents(world.partner, world.open_item)
    assert (docs.total, docs.received, docs.needs_review, docs.requested) == (4, 1, 1, 2)
    assert [(g.label, g.received, g.total) for g in docs.groups] == [
        ("Plan documents", 1, 3),
        ("Cash", 0, 1),
    ]
    assert [r.status for r in docs.groups[0].rows] == ["uploaded", "requested", "received"]
    later = await source_documents(world.partner, world.open_item, sort="received_first")
    assert [r.status for r in later.groups[0].rows] == ["received", "uploaded", "requested"]
    found = await source_documents(world.partner, world.open_item, q="trust")
    assert [r.title for g in found.groups for r in g.rows] == ["Certified trust report"]
    assert found.total == 4  # `q` narrows the rows, never the totals


async def test_ac27_pbc_counts_need_a_published_binder(world: World) -> None:
    counts = await pbc_counts(world.admin, [world.open_item, world.walled_item])
    assert counts == {world.open_item: (1, 4)}  # the other item has no binder: "—"
    await world.seed.run("UPDATE request_lists SET status = 'draft' WHERE id = $1", world.binder)
    assert await pbc_counts(world.admin, [world.open_item]) == {}


# --- Security review (DEC-311 to DEC-313) --------------------------------------------------------


async def _badge(
    tenant: TenantContext, ids: Sequence[uuid.UUID]
) -> Mapping[uuid.UUID, sections.RunSummary]:
    del tenant
    return {
        i: sections.RunSummary(i, 1, datetime.now(UTC), i, "Marcus Delaney", 1, 14, "partner")
        for i in ids
    }


async def test_review_the_run_badge_reaches_content_readers_only(world: World) -> None:
    sections.register_run_summary(_badge)
    try:
        admin, _ = await index.audits_index(
            world.admin, index.IndexFilters(), cursor=None, limit=50
        )
        partner, _ = await index.audits_index(
            world.partner, index.IndexFilters(), cursor=None, limit=50
        )
    finally:
        sections._run_summary.clear()  # pyright: ignore[reportPrivateUsage] -- test cleanup of a slot
    assert all(r.run_badge is None for r in admin.items)  # metadata only: no run progress
    assert all(r.run_badge is not None for r in partner.items)


async def _plain(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
    del tenant, work_item_id
    return SectionState(None, "link", sub_line="firm content")


async def test_review_a_providers_required_action_is_checked_for_the_reader(world: World) -> None:
    staff = await world.seed.person(world.tenant)
    engagement = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT engagement_id FROM work_items WHERE id = $1", world.open_item
        ),
    )
    await world.seed.member(engagement, staff, "staff")
    sections.register_audit_section(
        "firm_row",
        "overview",
        90,
        "KNW-03",
        _plain,
        required_action="methodology.read",
        action_scope="firm",
    )
    try:
        as_staff = await cockpit.audit_cockpit(staff.context(), world.open_item)
        as_partner = await cockpit.audit_cockpit(world.partner, world.open_item)
    finally:
        sections._SECTIONS.pop("firm_row", None)  # pyright: ignore[reportPrivateUsage] -- test cleanup of a slot

    def keys(view: cockpit.Cockpit) -> list[str]:
        return [r.key for b in view.bands if b.key == "overview" for r in b.rows]

    assert as_staff.bands and "firm_row" not in keys(as_staff)  # staff hold no methodology.read
    assert "firm_row" in keys(as_partner)


async def test_review_a_withdrawn_upload_shows_no_label_or_match(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-298: a client's withdrawn (detached-key) upload is as if it never arrived, so its
    label and the matcher's pick for it are never shown."""
    engagement = await world.seed.value(
        "SELECT engagement_id FROM evidence_versions WHERE id = $1", world.version
    )
    item = await world.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Withdrawn statement.pdf', 'human', 'seed') RETURNING id",
        world.tenant,
        engagement,
    )
    version = uuid.uuid4()
    fingerprint = hashlib.sha256(version.bytes).hexdigest()
    await world.seed.run(
        "INSERT INTO evidence_versions (id, tenant_id, engagement_id, evidence_item_id, "
        "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
        "source, method, storage_mode) VALUES ($1, $2, $3, $4, 1, $5, $6, 'v1', 10, "
        "'application/pdf', 'client_upload', 'uploaded', 'detached_key')",
        version,
        world.tenant,
        engagement,
        item,
        fingerprint,
        f"tenants/{world.tenant}/v/{version}",
    )
    await world.seed.run(
        "INSERT INTO evidence_object_keys (tenant_id, evidence_version_id, key_id, wrapped_key) "
        "VALUES ($1, $2, 'test-key', $3)",
        world.tenant,
        version,
        b"0" * 32,
    )
    await world.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id, created_at) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed', clock_timestamp() + interval '1 minute')",
        world.tenant,
        engagement,
        world.uploaded,
        version,
    )
    inbox_file = await world.seed.value(
        "INSERT INTO inbox_files (tenant_id, engagement_id, file_name, media_type, "
        "size_bytes, fingerprint, storage_key, storage_version_id, uploaded_by, "
        "uploaded_by_staff, status, assigned_item_id, assigned_version_id, decided_by, "
        "decided_at) VALUES ($1, $2, 'withdrawn.pdf', 'application/pdf', 10, $3, $4, 'v1', $5, "
        "true, 'assigned', $6, $7, $5, clock_timestamp()) RETURNING id",
        world.tenant,
        engagement,
        fingerprint,
        f"tenants/{world.tenant}/v/{version}",
        world.partner.user_id,
        world.uploaded,
        version,
    )

    async def picks(
        tenant: TenantContext, files: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[uuid.UUID, int]]]:
        del tenant
        return {f: [(world.uploaded, 88)] for f in files if f == inbox_file}

    monkeypatch.setattr(inbox, "_picks", picks)
    before = await binders.binder_requests(world.partner, world.binder, None, None)
    row = next(r for r in before.items if r.id == world.uploaded)
    assert row.latest_upload is not None and row.latest_upload.evidence_version_id == version
    assert row.match_confidence == 88
    await world.seed.as_actor(  # a withdrawal is the session's own person's (ADR-162)
        world.tenant,
        ("human", str(world.partner.user_id)),
        "INSERT INTO evidence_withdrawals (tenant_id, evidence_version_id, engagement_id, "
        "request_item_id, withdrawn_by_user_id, withdrawn_at, erase_after) VALUES ($1, $2, $3, "
        "$4, $5, clock_timestamp(), clock_timestamp() + interval '30 days')",
        world.tenant,
        version,
        engagement,
        world.uploaded,
        world.partner.user_id,
    )
    page = await binders.binder_requests(world.partner, world.binder, None, None)
    up = next(r for r in page.items if r.id == world.uploaded)
    assert (up.latest_upload, up.match_confidence) == (None, None)


async def test_review_an_archived_work_item_is_read_only(world: World) -> None:
    await world.seed.run(
        "UPDATE work_items SET status = 'archived' WHERE id = $1", world.open_item
    )
    view = await cockpit.audit_cockpit(world.partner, world.open_item)
    assert (view.read_only_reason, view.allowed_actions) == ("archived", [])
    page, _ = await index.audits_index(world.partner, index.IndexFilters(), cursor=None, limit=50)
    row = next(r for r in page.items if r.work_item_id == world.open_item)
    assert row.archive is not None and row.archive.state == "archived"


@pytest.mark.parametrize("q", ["%", "_", "\\"])
async def test_review_the_search_treats_wildcards_as_text(world: World, q: str) -> None:
    page, _ = await index.audits_index(world.admin, index.IndexFilters(q=q), cursor=None, limit=50)
    assert page.total == 0  # "Open plan" and "Walled plan" hold none of them


# --- Security review: G2 on the cockpit's content checks (ADR-164) -----------------------------


async def _pending_manager_on_an_ebp_audit(world: World) -> tuple[AuthContext, uuid.UUID]:
    """An active EBP audit (its client becomes an attest client, DEC-128) with a manager asked to
    confirm independence who has not."""
    entity = await world.seed.entity(world.tenant, "Attest plan")
    client = await world.seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    engagement = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by, type, status) VALUES ($1, $2, "
            "$3, 'Attest plan PY2025', '2025-01-01', '2025-12-31', $4, 'ebp_audit', 'prospect') "
            "RETURNING id",
            world.tenant,
            client,
            entity,
            world.partner.user_id,
        ),
    )
    await world.seed.open(world.tenant, engagement)
    async with uow(world.partner.tenant) as tx:  # the attest trigger reads under the tenant
        await tx.session.execute(
            text("UPDATE engagements SET status = 'active' WHERE id = :id"), {"id": engagement}
        )
        tx.record("engagement.probed", target=Target("engagement", engagement))
    await world.seed.member(engagement, world.partner_person, "engagement_partner")
    manager = await world.seed.person(world.tenant)
    await world.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        world.tenant,
        engagement,
        manager.user_id,
    )
    await world.seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status) "
        "VALUES ($1, $2, $3, 'requested') ON CONFLICT DO NOTHING",
        world.tenant,
        engagement,
        manager.user_id,
    )
    return manager.context(), await _assurance_item(world.seed, engagement)


async def test_review_g2_off_a_pending_manager_reads_content_but_records_nothing(
    world: World,
) -> None:
    manager, item = await _pending_manager_on_an_ebp_audit(world)
    view = await cockpit.audit_cockpit(manager, item)
    assert view.bands and view.dock_tabs == ["agent", "viewer"]  # reads are not gated
    assert "assurance.record_phase" not in view.allowed_actions  # a decision is (ADR-164)
    page, _ = await index.audits_index(manager, index.IndexFilters(), cursor=None, limit=50)
    assert [r.work_item_id for r in page.items] == [item]


async def test_review_g2_blocks_view_on_gates_the_documents_not_the_cockpit_host(
    world: World,
) -> None:
    """`g2_blocks_view` gates reads marked `independence: required` (ADR-164 item 3):
    `evidence.read` is, `engagement.read` and `engagement.read_metadata` are not. So with it on a
    pending manager still gets the cockpit's bar, bands and dock (no document content), the
    viewer's `evidence.read` is refused, and no decision is offered until they confirm."""
    manager, item = await _pending_manager_on_an_ebp_audit(world)
    await world.seed.run(
        "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
        "VALUES ($1, 'g2_blocks_view', true, $2)",
        world.tenant,
        world.partner.user_id,
    )
    view = await cockpit.audit_cockpit(manager, item)
    assert view.bands and view.dock_tabs == ["agent", "viewer"]
    assert "assurance.record_phase" not in view.allowed_actions
    engagement = cast(
        uuid.UUID,
        await world.seed.value("SELECT engagement_id FROM work_items WHERE id = $1", item),
    )
    on = Resource.engagement(world.tenant, engagement, archived=False)
    with recording_checks(), pytest.raises(Forbidden) as denied:
        await authorise(manager, "evidence.read", on)
    assert denied.value.layer == "independence"
    page, _ = await index.audits_index(manager, index.IndexFilters(), cursor=None, limit=50)
    assert [r.work_item_id for r in page.items] == [item]
    await world.seed.run(
        "UPDATE independence_confirmations SET status = 'confirmed', answered_at = now(), "
        "statement_version = 'v1' WHERE engagement_id = $1 AND user_id = $2",
        engagement,
        manager.user_id,
    )
    view = await cockpit.audit_cockpit(manager, item)
    assert "assurance.record_phase" in view.allowed_actions
