"""C-01-T15 (TASK-8033; SPEC-655 AC-14 to AC-22) against Postgres: the close plan.

The task's acceptance: "Publishing v4 with effective_from 2026-09 leaves August on v3, a Senior's
publish answers 403 while request-publish raises one HOME-02 gate, and tallies foot to
23 = 8 + 15."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import pytest

from abacus.kernel.clock import FIRM_ZONE, frozen
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.closes import gate_sources, plans, service
from abacus.modules.closes.contract import (
    PlanDraftIn,
    PlanRowIn,
    PlanRowPatchIn,
    PublishIn,
    UnadoptedRows,
)
from abacus.modules.closes.service import StaleClose
from abacus.modules.identity.api import Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- C-01-T14's firm seeder
)

pytestmark = pytest.mark.asyncio

# CLS-09 a: v3's review levels, 8 Manager approvals and 15 Senior sign-offs, 21 accounts and
# the two income-statement procedures (the figure book's plan, C-01-T13).
_MANAGER = {
    "Inventory",
    "Roasting Equipment",
    "Furniture & Fixtures",
    "Leasehold Improvements",
} | {
    "Accumulated Depreciation",
    "Accrued Expenses",
    "Deferred Revenue — Subscriptions",
}


def _rows() -> list[PlanRowIn]:
    accounts = [
        "Operating Checking ••4410", "Payroll Checking ••4428", "Business Savings ••4436",
        "Accounts Receivable", "Undeposited Funds", "Square Clearing", "Shopify Clearing",
        "Inventory", "Prepaid Insurance", "Roasting Equipment", "Furniture & Fixtures",
        "Leasehold Improvements", "Accumulated Depreciation", "Amex Business Card ••1009",
        "Accounts Payable", "Accrued Payroll", "Accrued Expenses",
        "Deferred Revenue — Subscriptions", "Sales Tax Payable", "Payroll Liabilities",
        "Equipment Loan (Front Range Bank)",
    ]  # fmt: skip
    rows = [
        PlanRowIn(
            account_external_id=str(n + 1),
            account_name=name,
            account_class="Balance sheet",
            procedure="reconciliation",
            method="Statement → GL",
            source="client_upload",
            review_level="manager_approval" if name in _MANAGER else "senior_signoff",
        )
        for n, name in enumerate(accounts)
    ]
    rows.append(
        PlanRowIn(
            account_name="Revenue & expenses",
            account_class="Income statement",
            procedure="recategorize",
            method="Coding review",
            source="quickbooks_online",
            review_level="senior_signoff",
        )
    )
    rows.append(
        PlanRowIn(
            account_name="Revenue & expenses",
            account_class="Income statement",
            procedure="flux",
            method="Month over month vs threshold",
            source="quickbooks_online",
            review_level="manager_approval",
        )
    )
    return rows


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    # Fresh pools on this test's loop (the identity engine, for names_of, rebuilds from the
    # settings), disposed after it: no connection outlives its loop.
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _published(firm: _Firm, client: uuid.UUID, effective: str, n: int) -> int:
    """Draft, fill and publish one version; its row version is read back each step."""
    draft = await plans.create_draft(firm.ctx(), client, PlanDraftIn())
    seen = draft.row_version
    if not draft.rows:
        for row in _rows():
            await plans.add_row(firm.ctx(), client, draft.version, row, str(seen))
            seen += 1
    published = await plans.publish(
        firm.ctx(), client, draft.version, PublishIn(effective_from=effective), str(seen)
    )
    assert published.version == n
    return n


async def test_ac14_tally_foots_23_is_manager_8_plus_senior_15(firm: _Firm) -> None:
    _, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    await _published(firm, client, "2026-01", 1)
    plan = await plans.get_plan(firm.ctx(), client, None)
    assert (plan.tally.procedures, plan.tally.manager, plan.tally.senior) == (23, 8, 15)


async def test_ac17_ac18_v4_effective_september_leaves_august_on_v3(firm: _Firm) -> None:
    engagement, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    closes = await service.generate_closes(firm.ctx(), engagement, 2026)
    # v1 to v3 went out before August's BD1 (Tue Sep 1); v4 is published at E0 (QC-2).
    with frozen(datetime(2026, 8, 14, 9, 0, tzinfo=FIRM_ZONE)):
        for n, effective in ((1, "2026-01"), (2, "2026-03"), (3, "2026-06")):
            await _published(firm, client, effective, n)
    august = closes[7]
    v3 = await firm.seed.value(
        "SELECT v.id FROM close_plan_versions v JOIN close_plans p ON p.id = v.plan_id "
        "WHERE p.tenant_id = $1 AND v.version = 3",
        firm.tenant,
    )
    with frozen(datetime(2026, 9, 14, 9, 24, tzinfo=FIRM_ZONE)):
        await _published(firm, client, "2026-09", 4)
    pinned = await firm.seed.value(
        "SELECT close_plan_version_id FROM closes WHERE work_item_id = $1", august
    )
    assert pinned == v3  # August passed BD1 (Sep 1) before v4 published
    assert (await service.close_for(firm.ctx().tenant, august)).plan_version == 3
    with pytest.raises(plans.VersionNotDraft):
        await plans.patch_row(firm.ctx(), client, 4, uuid.uuid4(), PlanRowPatchIn(method="x"), "1")


async def test_ac16_a_seniors_publish_is_403_and_request_publish_raises_one_gate(
    firm: _Firm,
) -> None:
    engagement, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    await _published(firm, client, "2026-01", 1)
    raj = await firm.user("Raj Malhotra")
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'senior')",
        firm.tenant,
        engagement,
        raj,
    )
    draft = await plans.create_draft(firm.ctx(raj), client, PlanDraftIn(from_version=1))
    with pytest.raises(Forbidden):
        await plans.publish(
            firm.ctx(raj), client, draft.version, PublishIn(effective_from="2026-09"),
            str(draft.row_version),
        )  # fmt: skip
    asked = await plans.request_publish(firm.ctx(raj), client, draft.version)
    assert asked.publish_requested and asked.status == "draft"
    again = await plans.request_publish(firm.ctx(raj), client, draft.version)
    assert again.publish_requested
    due = await gate_sources.publications_due(firm.ctx().tenant, engagement)
    assert len(due) == 1 and due[0].engagement_id == engagement


async def test_ac22_publish_refuses_an_unadopted_drafted_row(firm: _Firm) -> None:
    _, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    await _published(firm, client, "2026-01", 1)
    draft = await plans.create_draft(firm.ctx(), client, PlanDraftIn(from_version=1))
    await firm.seed.run(
        "UPDATE close_plan_rows SET drafted_suggestion_id = gen_random_uuid() "
        "WHERE id = (SELECT r.id FROM close_plan_rows r JOIN close_plan_versions v "
        "ON v.id = r.version_id WHERE v.tenant_id = $1 AND v.version = 2 LIMIT 1)",
        firm.tenant,
    )
    with pytest.raises(UnadoptedRows):
        await plans.publish(
            firm.ctx(), client, draft.version, PublishIn(effective_from="2026-09"),
            str(draft.row_version),
        )  # fmt: skip
    adopted = await plans.adopt(firm.ctx(), client, draft.version, None, str(draft.row_version))
    assert adopted.adopted == 1
    published = await plans.publish(
        firm.ctx(), client, draft.version, PublishIn(effective_from="2026-09"),
        str(adopted.row_version),
    )  # fmt: skip
    assert published.status == "published"


async def test_ac19_a_stale_if_match_is_409_stale_version(firm: _Firm) -> None:
    _, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    await _published(firm, client, "2026-01", 1)
    draft = await plans.create_draft(firm.ctx(), client, PlanDraftIn(from_version=1))
    row = draft.rows[0].row_id
    await plans.patch_row(
        firm.ctx(), client, draft.version, row, PlanRowPatchIn(method="Statement → GL; aged"),
        str(draft.row_version),
    )  # fmt: skip
    with pytest.raises(StaleClose) as stale:
        await plans.patch_row(
            firm.ctx(), client, draft.version, row, PlanRowPatchIn(method="again"),
            str(draft.row_version),
        )  # fmt: skip
    assert stale.value.facts["editor_user_id"] == str(firm.partner)


async def test_ac15_history_attributes_each_version(firm: _Firm) -> None:
    _, client, _ = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    await _published(firm, client, "2026-01", 1)
    history = await plans.plan_history(firm.ctx(), client)
    assert [i.attribution for i in history.items] == [
        "v1 published · Priya Raman",
        "v1 drafted · Priya Raman",
    ]
