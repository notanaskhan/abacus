"""The engagement graph (SPEC-008 AC-6 to AC-9; TASK-023 D1): one deterministic view of how an
engagement fits together, computed on read from the owning modules' APIs (Q2).

Areas come from the pinned methodology version, plus any `audit_area` used by request items.
Accounts of the latest ledger snapshot map to areas by the version's rules, first match in rule
order (ADR-050: code, never a model). Agents read the same view as people.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.db import tenant_session
from abacus.modules.agents.repository import latest_results
from abacus.modules.engagements.api import (
    EngagementMetadata,
    TemplateVersionSummary,
    area_for,
    engagement_metadata,
    get_ref,
    version_detail,
)
from abacus.modules.evidence.api import engagement_snapshots
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.ledger.api import SnapshotView, snapshot_view
from abacus.modules.requests.api import request_items_for


@dataclass(frozen=True)
class GraphItem:
    id: UUID
    description: str
    status: str
    retrievability_tier: str | None
    evidence_version_id: UUID | None
    # The latest screening action on that version, if screened.
    screening_action: str | None


@dataclass(frozen=True)
class GraphAccount:
    code: str
    name: str
    balance: Decimal  # debit minus credit, as in the snapshot


@dataclass(frozen=True)
class GraphArea:
    code: str | None  # None for an area used by request items but not in the template
    name: str
    items: tuple[GraphItem, ...]
    accounts: tuple[GraphAccount, ...]


@dataclass(frozen=True)
class CoverageGaps:
    areas_without_requests: tuple[str, ...]
    areas_with_accounts_without_requests: tuple[str, ...]
    unmapped_accounts: tuple[GraphAccount, ...]
    items_without_evidence: tuple[UUID, ...]


@dataclass(frozen=True)
class EngagementGraph:
    metadata: EngagementMetadata
    methodology: TemplateVersionSummary | None
    snapshot_id: UUID | None
    areas: tuple[GraphArea, ...]
    unmapped_accounts: tuple[GraphAccount, ...]
    gaps: CoverageGaps


async def _latest_snapshot(ctx: AuthContext, engagement_id: UUID) -> SnapshotView | None:
    views = [
        await snapshot_view(ctx.tenant, i)
        for i in await engagement_snapshots(ctx.tenant, engagement_id)
    ]
    return max(views, key=lambda v: (v.period_end, v.pulled_at, str(v.id)), default=None)


async def engagement_graph(ctx: AuthContext, engagement_id: UUID) -> EngagementGraph:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read", ref.resource())
    metadata = await engagement_metadata(ctx, engagement_id)
    items = await request_items_for(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        actions = {
            r.evidence_version_id: r.action
            for r in await latest_results(session, ctx, engagement_id)
        }
    methodology = (
        await version_detail(ctx.tenant, ref.methodology_version_id)
        if ref.methodology_version_id is not None
        else None
    )
    snapshot = await _latest_snapshot(ctx, engagement_id)

    # Areas: the template's, in its order, then any other `audit_area` in first-use order.
    names: dict[str, str | None] = {}
    code_name: dict[str, str] = {}
    if methodology is not None:
        for area in methodology.areas:
            names[area.name] = area.code
            code_name[area.code] = area.name
    for item in items:
        names.setdefault(item.audit_area, None)

    by_area: dict[str, list[GraphItem]] = {name: [] for name in names}
    for item in items:
        version = item.evidence_version_id
        by_area[item.audit_area].append(
            GraphItem(
                item.id,
                item.description,
                item.status,
                item.retrievability_tier,
                version,
                actions.get(version) if version is not None else None,
            )
        )

    accounts: dict[str, list[GraphAccount]] = {name: [] for name in names}
    unmapped: list[GraphAccount] = []
    rules = methodology.rules if methodology is not None else ()
    for line in snapshot.lines if snapshot is not None else ():
        account = GraphAccount(line.account_code, line.account_name, line.debit - line.credit)
        code = area_for(line.account_code, rules)
        if code is None:
            unmapped.append(account)
        else:
            accounts[code_name[code]].append(account)

    areas = tuple(
        GraphArea(code, name, tuple(by_area[name]), tuple(accounts[name]))
        for name, code in names.items()
    )
    threshold = settings().unmapped_gap_min_abs_usd
    gaps = CoverageGaps(
        areas_without_requests=tuple(a.name for a in areas if not a.items),
        areas_with_accounts_without_requests=tuple(
            a.name for a in areas if a.accounts and not a.items
        ),
        unmapped_accounts=tuple(
            a for a in unmapped if a.balance != 0 and abs(a.balance) >= threshold
        ),
        items_without_evidence=tuple(i.id for i in items if i.evidence_version_id is None),
    )
    return EngagementGraph(
        metadata,
        methodology.summary if methodology is not None else None,
        snapshot.id if snapshot is not None else None,
        areas,
        tuple(unmapped),
        gaps,
    )
