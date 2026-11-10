"""A return's issues and checkpoints (T-04-T23; T-04 §3.4, §3.5; SPEC-649 AC-4.1, AC-4.2, AC-4.7,
AC-5.2; TAX-06, TAX-07; ADR P-07, ISSUE-001). PROTECTED (red path: a dependency that only the
system resolves).

Issues are P-04's (`review.api`); this is the tax module's side of them:

- **Sources and category paths** (`category_for`): each issue the tax code raises names where it
  came from (`mismatch`, `self_check`, `engine_diagnostic`, `k1_dependency`) and its queue group
  (TAX-06's category path: `income/k1`, `payments/estimates`, `approvals/k1`, …).
- **The Draft K-1 dependency** (`raise_draft_k1_issue`): Action required, priority High, blocking
  final approval and export, `system_resolved_only` (0800). A person's resolve answers 409
  `system_resolved_only` and the database refuses the event; the `k1_package.released` consumer
  (`on_k1_package_released`) resolves it as the system once the final K-1 is released (AC-4.2).
- **Counts** (`issue_counts`): open by kind (TAX-06's "4 open = 2 Missing information + 1 Action
  required + 1 Review point") and resolved, over P-04's list.
- **CSV export** (`issues_csv`): `export.create` (fresh MFA, the matrix), each cell neutralised
  against formula injection, audited `export.created` with the row count (AC-4.7).
- **The checkpoint chip** (`checkpoint_chip`): TAX-07's "☰ 1 proposed" or "✓ No changes needed",
  and the Current checkpoint's name (AC-5.2).
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import DomainEvent, OutboxEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.review.api import (
    OPEN_STATUSES,
    IssueSource,
    create_issue,
    list_checkpoints,
    list_issues,
    read_issue,
    system_resolve_dependents,
)

TARGET: Final = "tax_return"
EXPORT_ACTION: Final = "export.create"
_FORMULA_LEAD: Final = ("=", "+", "-", "@", "\t", "\r")
KIND_LABELS: Final = {
    "missing_information": "Missing information",
    "action_required": "Action required",
    "review_point": "Review point",
    "waiting_on_client": "Waiting on client",
    "exception": "Exception",
    "engine_diagnostic": "Engine diagnostic",
}
# TAX-06's queue groups by source and code (paths of codes; labels are the screen's).
_CATEGORIES: Final[dict[tuple[str, str], str]] = {
    ("self_check", "box_18a_state"): "income/k1",
    ("self_check", "box_unmapped"): "income/documents",
    ("self_check", "box_low_confidence"): "income/documents",
    ("self_check", "citation_unverified"): "income/documents",
    ("mismatch", "documents"): "income/documents",
    ("mismatch", "estimates"): "payments/estimates",
    ("mismatch", "residency"): "residency/nyc",
    ("engine_diagnostic", "engine"): "engine/diagnostics",
    ("k1_dependency", "draft_k1"): "approvals/k1",
}


def category_for(source: str, code: str) -> str:
    """TAX-06's category path for an issue of `source` and `code` (a source's own root else)."""
    return _CATEGORIES.get((source, code), source.replace("_", ""))


def dependency_ref(package_id: UUID) -> str:
    return f"k1_dependency:{package_id}"


DRAFT_K1_TITLE: Final = (
    "Draft K-1: final approval and export wait for the final K-1 to be released"
)


async def raise_draft_k1_issue(
    ctx: AuthContext,
    *,
    return_id: UUID,
    package_id: UUID,
    assignee_user_id: UUID | None,
) -> UUID:
    """The Draft K-1 dependency on a return that received a draft K-1 (TAX-06b): Action
    required, High, blocking final approval and export, resolved only by the system when the
    package is released. One per return and package (`source_ref`)."""
    return await create_issue(
        ctx,
        record_type=TARGET,
        record_id=return_id,
        kind="action_required",
        priority="high",
        title=DRAFT_K1_TITLE,
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=assignee_user_id,
        assignee_agent=False,
        blocks=("final_approval", "export"),
        source_ref=dependency_ref(package_id),
        work_item_id=return_id,
        source=IssueSource(
            "k1_dependency", category_for("k1_dependency", "draft_k1"), system_resolved_only=True
        ),
    )


class K1PackageReleased(DomainEvent):
    """T-04-T23: a K-1 package moved to `released` (the final K-1 is out); the receiving
    returns' Draft K-1 issues resolve. Identifiers only."""

    event_type: ClassVar[str] = "k1_package.released"

    package_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]


async def on_k1_package_released(event: OutboxEvent) -> None:
    """AC-4.2: the Draft K-1 issues naming the package resolve, as the system."""
    package = UUID(str(event.payload["package_id"]))
    system = TenantContext(event.tenant_id, "system", "tax:k1-dependency")
    await system_resolve_dependents(system, dependency_ref(package))


SUBSCRIPTIONS: Final = {K1PackageReleased.event_type: on_k1_package_released}


@dataclass(frozen=True)
class IssueCounts:
    open_total: int
    open_by_kind: dict[str, int]  # labels, as TAX-06 reads them
    resolved: int


async def issue_counts(ctx: AuthContext, return_id: UUID) -> IssueCounts:
    page = await list_issues(
        ctx,
        record_type=TARGET,
        record_id=return_id,
        engagement_id=None,
        status=None,
        kind=None,
        limit=500,
    )
    open_rows = [r for r in page.rows if r.status in OPEN_STATUSES]
    by_kind = Counter(KIND_LABELS.get(r.kind, r.kind) for r in open_rows)
    resolved = sum(1 for r in page.rows if r.status in ("resolved", "verified"))
    return IssueCounts(len(open_rows), dict(by_kind), resolved)


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_LEAD) else text


EXPORT_COLUMNS: Final = (
    "Title",
    "Kind",
    "Priority",
    "Status",
    "Category",
    "Blocks",
    "Raised",
)


async def issues_csv(ctx: AuthContext, return_id: UUID) -> str:
    """AC-4.7: the return's issues as CSV for a person who may export (`export.create`, fresh
    MFA): titles opened (each read logged by P-04), formula-leading cells escaped."""
    page = await list_issues(
        ctx,
        record_type=TARGET,
        record_id=return_id,
        engagement_id=None,
        status=None,
        kind=None,
        limit=500,
    )
    engagement_id = page.rows[0].engagement_id if page.rows else None
    from abacus.modules.engagements.api import engagement_resource_of

    if engagement_id is not None:
        await authorise(
            ctx, EXPORT_ACTION, await engagement_resource_of(ctx.tenant, engagement_id)
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    for row in page.rows:
        _, texts, _ = await read_issue(ctx, row.id)
        writer.writerow(
            [
                _cell(texts.title),
                _cell(KIND_LABELS.get(row.kind, row.kind)),
                _cell(row.priority),
                _cell(row.status),
                _cell(row.category_path),
                _cell(" ".join(row.blocks)),
                _cell(row.created_at.date().isoformat()),
            ]
        )
    async with uow(ctx.tenant) as tx:
        tx.record(
            "export.created",
            target=Target(TARGET, return_id),
            after=Ref(row_count=len(page.rows)),
        )
    return buffer.getvalue()


ChipState = Literal["proposed", "no_changes"]


@dataclass(frozen=True)
class CheckpointChip:
    state: ChipState
    proposed: int
    current_name: str | None


async def checkpoint_chip(ctx: AuthContext, return_id: UUID) -> CheckpointChip:
    """TAX-07's chip: "☰ n proposed" while any checkpoint waits, else "✓ No changes needed"."""
    listed = await list_checkpoints(ctx, TARGET, return_id, "all")
    proposed = sum(1 for c in listed.items if c.status == "proposed")
    current = next((c for c in listed.items if c.current), None)
    return CheckpointChip(
        "proposed" if proposed else "no_changes",
        proposed,
        current.name if current is not None else None,
    )


__all__ = [
    "DRAFT_K1_TITLE",
    "SUBSCRIPTIONS",
    "CheckpointChip",
    "IssueCounts",
    "K1PackageReleased",
    "category_for",
    "checkpoint_chip",
    "dependency_ref",
    "issue_counts",
    "issues_csv",
    "on_k1_package_released",
    "raise_draft_k1_issue",
]
