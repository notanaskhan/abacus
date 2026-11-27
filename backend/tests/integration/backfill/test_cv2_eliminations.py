# ac-test-author: ayushkbhatia
"""CV-2 (TASK-9001; DEC-6003; A-09-T20; SPEC-658 F4; AUD-33; DEC-5313): consolidation
eliminations on the migrated Postgres. Main CI measured `adjustments/eliminations.py` at 30%: the
unit suite held the pure parts, the service never ran against the database.

A person proposes an elimination (lines by caption and entity, at one level), edits it while
proposed, approves it only when it balances, and posts it to Accrued's consolidation layer only
(no posting batch, no write to any client system); a second is rejected with a reason; a locked
consolidation refuses every change; an agent or a staff member never approves."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D
from typing import cast

import pytest

from abacus.modules.adjustments import eliminations as el
from abacus.modules.identity.api import AuthContext, Forbidden, member_context

from .support import Person, Seeder, Site

pytestmark = pytest.mark.asyncio


async def _ctx(tenant: uuid.UUID, who: Person) -> AuthContext:
    found = await member_context(tenant, who.user_id)
    assert found is not None
    return replace(found, mfa_at=datetime.now(UTC))


async def _group(seed: Seeder) -> tuple[Site, uuid.UUID, uuid.UUID, Person, Person, uuid.UUID]:
    tenant = await seed.firm()
    partner, staff = await seed.person(tenant), await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Harlow Pike")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, staff, "staff")
    item = await seed.value(
        "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 "
        "AND kind = 'assurance'",
        tenant,
        site.engagement_id,
    )
    work_item = cast(
        uuid.UUID,
        item
        or await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'assurance', 'FY2026 group audit', $4) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            partner.user_id,
        ),
    )
    component = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
            "'Pike Logistics') RETURNING id",
            tenant,
            site.client_id,
        ),
    )
    await seed.run(
        "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role) "
        "VALUES ($1, $2, $3, 'component')",
        tenant,
        site.engagement_id,
        component,
    )
    consolidation = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consolidations (tenant_id, engagement_id, work_item_id, name, year_end, "
            "reporting_currency, created_by) VALUES ($1, $2, $3, 'FY2026 group consolidation', "
            "'2026-12-31', 'USD', $4) RETURNING id",
            tenant,
            site.engagement_id,
            work_item,
            partner.user_id,
        ),
    )
    root = await seed.value(
        "INSERT INTO consolidation_entities (tenant_id, consolidation_id, client_entity_id, "
        "parent_id, level, ownership_pct) VALUES ($1, $2, $3, NULL, 1, 100) RETURNING id",
        tenant,
        consolidation,
        site.entity_id,
    )
    await seed.run(
        "INSERT INTO consolidation_entities (tenant_id, consolidation_id, client_entity_id, "
        "parent_id, level, ownership_pct) VALUES ($1, $2, $3, $4, 2, 100)",
        tenant,
        consolidation,
        component,
        root,
    )
    return site, work_item, consolidation, partner, staff, component


def _lines(
    parent: uuid.UUID, component: uuid.UUID, credit: str = "1200.00"
) -> list[el.EliminationLine]:
    return [
        el.EliminationLine("Intercompany payable", component, D("1200.00"), D("0")),
        el.EliminationLine("Intercompany receivable", parent, D("0"), D(credit)),
    ]


async def test_cv2_an_elimination_is_proposed_edited_approved_and_posted(seed: Seeder) -> None:
    site, item, cid, partner, _staff, component = await _group(seed)
    ctx = await _ctx(site.tenant_id, partner)
    off = await el.propose_elimination(
        ctx,
        engagement_id=site.engagement_id,
        work_item_id=item,
        consolidation_id=cid,
        level=1,
        description="  Intercompany balances  ",
        lines=_lines(site.entity_id, component, "1100.00"),
    )
    assert (off.display_code, off.status, off.description, off.level) == (
        "E1",
        "review_required",
        "Intercompany balances",
        1,
    )
    assert (off.total_debit, off.total_credit, off.off_by) == (
        D("1200.00"),
        D("1100.00"),
        D("100.00"),
    )
    with pytest.raises(el.UnbalancedEntry):
        await el.approve(ctx, [off.id])

    version = cast(
        int, await seed.value("SELECT version FROM proposed_entries WHERE id = $1", off.id)
    )
    with pytest.raises(el.EliminationStale):
        await el.edit_elimination(
            ctx,
            off.id,
            level=1,
            description="x",
            lines=_lines(site.entity_id, component),
            seen_version=version + 5,
        )
    fixed = await el.edit_elimination(
        ctx,
        off.id,
        level=1,
        description="Intercompany balances at Dec 31",
        lines=_lines(site.entity_id, component),
        seen_version=version,
    )
    assert fixed.off_by == 0 and fixed.description == "Intercompany balances at Dec 31"
    assert [(ln.caption, ln.debit, ln.credit) for ln in fixed.lines] == [
        ("Intercompany payable", D("1200.00"), D("0.00")),
        ("Intercompany receivable", D("0.00"), D("1200.00")),
    ]  # the replaced lines, not the old ones beside them

    [approved] = await el.approve(ctx, [off.id])
    assert approved.status == "approved"
    with pytest.raises(el.NotProposed):
        await el.approve(ctx, [off.id])
    posted = await el.post(ctx, off.id)
    assert posted.status == "posted"
    with pytest.raises(el.NotProposed):
        await el.post(ctx, off.id)
    with pytest.raises(el.NotProposed):
        await el.reject_elimination(ctx, off.id, "too late")
    row = (
        await seed.rows(
            "SELECT posting_target, posting_batch_id, consolidation_id FROM proposed_entries "
            "WHERE id = $1",
            off.id,
        )
    )[0]
    assert (row["posting_target"], row["posting_batch_id"], row["consolidation_id"]) == (
        "consolidation_layer",
        None,
        cid,
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM posting_batches WHERE tenant_id = $1", site.tenant_id
        )
        == 0
    )

    second = await el.propose_elimination(
        ctx,
        engagement_id=site.engagement_id,
        work_item_id=item,
        consolidation_id=cid,
        level=2,
        description="Management fee",
        lines=_lines(site.entity_id, component),
    )
    assert second.display_code == "E2"
    rejected = await el.reject_elimination(ctx, second.id, "Recorded at the component")
    assert rejected.status == "rejected"
    listed = await el.eliminations_of(ctx.tenant, cid)
    assert [(e.display_code, e.status) for e in listed] == [("E1", "posted"), ("E2", "rejected")]
    actions = await seed.actions(site.tenant_id)
    for action in ("elimination.proposed", "elimination.approved", "elimination.posted"):
        assert action in actions


async def test_cv2_a_locked_consolidation_refuses_every_change(seed: Seeder) -> None:
    site, item, cid, partner, _staff, component = await _group(seed)
    ctx = await _ctx(site.tenant_id, partner)
    entry = await el.propose_elimination(
        ctx,
        engagement_id=site.engagement_id,
        work_item_id=item,
        consolidation_id=cid,
        level=1,
        description="Intercompany",
        lines=_lines(site.entity_id, component),
    )
    await seed.run_untriggered(  # finalized, then locked (the consolidation's own order)
        "UPDATE consolidations SET status = 'finalized', finalized_at = now(), "
        "finalized_by = created_by, lock_state = 'locked', locked_by = created_by, "
        "locked_at = now(), locked_actor_kind = 'human' WHERE id = $1",
        cid,
    )
    with pytest.raises(el.ConsolidationLocked):
        await el.propose_elimination(
            ctx,
            engagement_id=site.engagement_id,
            work_item_id=item,
            consolidation_id=cid,
            level=1,
            description="More",
            lines=_lines(site.entity_id, component),
        )
    with pytest.raises(el.ConsolidationLocked):
        await el.approve(ctx, [entry.id])
    assert (await el.view(ctx.tenant, entry.id)).status == "review_required"


async def test_cv2_only_a_partner_or_manager_approves_and_never_an_agent(seed: Seeder) -> None:
    site, item, cid, partner, staff, component = await _group(seed)
    ctx = await _ctx(site.tenant_id, partner)
    entry = await el.propose_elimination(
        ctx,
        engagement_id=site.engagement_id,
        work_item_id=item,
        consolidation_id=cid,
        level=1,
        description="Intercompany",
        lines=_lines(site.entity_id, component),
    )
    with pytest.raises(Forbidden):
        await el.approve(await _ctx(site.tenant_id, staff), [entry.id])
    agent = replace(ctx, tenant=replace(ctx.tenant, actor_kind="agent"))
    for attempt in (el.approve(agent, [entry.id]), el.post(agent, entry.id)):
        with pytest.raises(Forbidden):
            await attempt
    from abacus.kernel.errors import NotFound

    with pytest.raises(NotFound):
        await el.approve(ctx, [uuid.uuid4()])
    with pytest.raises(NotFound):
        await el.post(ctx, uuid.uuid4())
    assert (await el.view(ctx.tenant, entry.id)).status == "review_required"


async def test_cv2_the_database_refuses_an_unbalanced_elimination_past_draft(seed: Seeder) -> None:
    """1031: a draft may be off balance (AC-4.3); approved or posted, never (whoever writes)."""
    import asyncpg

    site, item, cid, partner, _staff, component = await _group(seed)
    ctx = await _ctx(site.tenant_id, partner)
    off = await el.propose_elimination(
        ctx,
        engagement_id=site.engagement_id,
        work_item_id=item,
        consolidation_id=cid,
        level=1,
        description="Off by 10,000",
        lines=_lines(site.entity_id, component, "11200.00"),
    )
    assert off.off_by == D("-10000.00")
    for status in ("approved", "posted"):
        with pytest.raises(asyncpg.CheckViolationError, match="unbalanced_entry"):
            await seed.run("UPDATE proposed_entries SET status = $2 WHERE id = $1", off.id, status)
    # A plain AJE still balances at every commit, draft or not (0643 unchanged for it).
    with pytest.raises(asyncpg.CheckViolationError, match="unbalanced_entry"):
        await seed.run(
            "WITH e AS (INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, "
            "kind, number, ref, threshold_result, is_attest_client, status, created_by_kind, "
            "created_by_id) VALUES ($1, $2, $3, 'aje', 1, 'AJE-1', 'review_required', true, "
            "'review_required', 'human', $4) RETURNING id) INSERT INTO proposed_entry_lines "
            "(tenant_id, engagement_id, work_item_id, entry_id, line_no, account_code, debit, "
            "credit) SELECT $1, $2, $3, e.id, 1, '1000', 5, 0 FROM e",
            site.tenant_id,
            site.engagement_id,
            item,
            str(partner.user_id),
        )
