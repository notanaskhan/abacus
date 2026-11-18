"""C-02-T12: close approvals over C8 (SPEC-700; C-02 §3 F2; DEC-5621). PROTECTED (red).

CAS approvals of a close's proposed entries, behind `adjustments.posting`, on A-06's decision
store (`proposed_entry_decisions`, insert-only, human-only in five layers; decisions.py):

- **The projection** (`close_entries`): each entry re-classified now against the firm's AJE
  thresholds in effect (K-02 `aje_classification_for`), with the class limit, tallies summed by
  code (ADR-050) and the approver's context ("may approve within-threshold batches").
- **Batch within policy** (`approve_batch`): only within-threshold entries of a non-attest client,
  by a person whose engagement role meets each entry's approver level; one approval batch and one
  decision per entry with the batch id and policy version ("Approved by RM under BH AJE
  thresholds v2"). Anything else is refused whole: 409 `over_approval_limit`.
- **Held approval** (`approve_held`): a review-required entry by a manager or partner (or the
  class's own approver level), written at once with a 10-second Undo (DEC-24).
- **Undo** (`undo`): inside 10 seconds and before any effect (no posting batch holds the entry),
  an `approval_undone` decision is appended, never a delete (ADR-007).
- **Withdraw** (`withdraw`): an approved, unposted entry returns to its threshold result with an
  `approval_withdrawn` decision and a reason.
- **Request approval** (`request_approval`): an `entry_approval_requested` notification and the
  HOME-02 gate for the named approver; no decision row (a request decides nothing).
- **Reject** (`reject`): A-06's reject with the person's reason (the CLS-06 issue is raised by
  the closes consumer of `proposed_entry.rejected`, C-02-T19).

No policy-attributed decision exists (DEC-53): every write here is a live person's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel._statuses import ProposedEntryStatus as S
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import DomainEvent, Scope, Target, uow
from abacus.modules.adjustments import decisions as _decisions
from abacus.modules.adjustments.entries import TARGET, engagement_of
from abacus.modules.adjustments.posting_errors import EntryLocked, OverApprovalLimit
from abacus.modules.engagements.api import attest_of, lock_ref
from abacus.modules.identity.api import AuthContext, Forbidden, engagement_role_of, names_of
from abacus.modules.integrations.api import posting_enabled_for
from abacus.modules.methodology.api import EntryClassification, aje_classification_for

UNDO_WINDOW: Final = timedelta(seconds=10)  # DEC-24
# Approver level -> the engagement roles that meet it (K-02 AJE thresholds rows).
_LEVELS: Final[dict[str, frozenset[str]]] = {
    "senior_or_above": frozenset({"senior", "manager", "engagement_partner"}),
    "manager_or_partner": frozenset({"manager", "engagement_partner"}),
    "partner": frozenset({"engagement_partner"}),
}
_ROLE_LABELS: Final = {
    "senior": "Senior",
    "manager": "Manager",
    "engagement_partner": "Partner",
}
_OPEN: Final = frozenset({S.PROPOSED, S.WITHIN_THRESHOLD, S.REVIEW_REQUIRED})
_POSTED: Final = frozenset({S.POSTED, S.FAILED_POST, S.REVERSED})


class EntryApprovalDecided(DomainEvent):
    """A close approval, Undo or withdrawal: HOME-02 recomputes the entry's gate (C-02-T14)."""

    event_type = "proposed_entry.approval_decided"
    proposed_entry_id: UUID
    engagement_id: UUID
    work_item_id: UUID


class EntryApprovalRequested(DomainEvent):
    """C16 `entry_approval_requested` and the HOME-02 gate (identifiers only, DEC-60)."""

    event_type = "proposed_entry.approval_requested"
    proposed_entry_id: UUID
    engagement_id: UUID
    work_item_id: UUID
    recipient_user_ids: list[UUID]
    by_user: UUID


@dataclass(frozen=True)
class ClosedEntry:
    entry_id: UUID
    ref: str
    description: str | None
    amount: Decimal
    status: str
    account_class: str | None
    version: int
    classification: EntryClassification | None
    approval_label: str | None
    # The class limit is the K-02 payload row's; it joins when K-02 exposes it with the outcome.
    limit: Decimal | None = None


@dataclass(frozen=True)
class Tally:
    count: int
    amount: Decimal


@dataclass(frozen=True)
class CloseEntries:
    entries: tuple[ClosedEntry, ...]
    proposed: Tally
    within_threshold: Tally
    review_required: Tally
    approved: int
    role: str | None
    policy_label: str | None
    policy_version_id: UUID | None
    may_batch_within_threshold: bool
    attest: bool
    display_name: str = ""


@dataclass(frozen=True)
class Decided:
    decision_id: UUID
    entry_id: UUID
    status: str
    approval_label: str | None
    undo_until: datetime | None


def meets(role: str | None, level: str) -> bool:
    """Whether an engagement role meets an approver level (unknown roles never do)."""
    return role is not None and role in _LEVELS.get(level, frozenset())


def _tally(rows: Sequence[ClosedEntry]) -> Tally:
    return Tally(len(rows), sum((r.amount for r in rows), Decimal("0")))


async def _classify(
    ctx: AuthContext, amount: Decimal, account_class: str | None, attest: bool
) -> EntryClassification | None:
    return await aje_classification_for(
        ctx.tenant_id,
        account_class=account_class or "",
        amount_usd=int(amount),
        attest_client=attest,
        as_of=await clock.today(ctx.tenant),
    )


async def _rows(ctx: AuthContext, work_item_id: UUID) -> list[dict[str, object]]:
    async with tenant_session(ctx.tenant) as session:
        result = await session.execute(
            text(
                "SELECT id, kind, number, description, amount, account_class, status, version "
                "FROM proposed_entries WHERE work_item_id = :w ORDER BY kind, number"
            ),
            {"w": work_item_id},
        )
        return [dict(r) for r in result.mappings()]


async def _labels(ctx: AuthContext, entry_ids: Sequence[UUID]) -> dict[UUID, str]:
    """The latest standing approval per entry, as its row label ("Approved by RM under …")."""
    if not entry_ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        result = await session.execute(
            text(
                "SELECT DISTINCT ON (d.entry_id) d.entry_id, d.decision, b.label "
                "FROM proposed_entry_decisions d "
                "LEFT JOIN approval_batches b ON b.id = d.approval_batch_id "
                "WHERE d.entry_id = ANY(:ids) ORDER BY d.entry_id, d.created_at DESC"
            ),
            {"ids": list(entry_ids)},
        )
        return {
            UUID(str(r["entry_id"])): str(r["label"])
            for r in result.mappings()
            if r["decision"] == "approved" and r["label"] is not None
        }


async def close_entries(ctx: AuthContext, work_item_id: UUID) -> CloseEntries:
    """CLS-07's list: entries, classification now, tallies by code and the approver's context."""
    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    attest = await attest_of(ctx.tenant, engagement_id) is True
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    rows = await _rows(ctx, work_item_id)
    labels = await _labels(ctx, [UUID(str(r["id"])) for r in rows])
    entries: list[ClosedEntry] = []
    policy_label: str | None = None
    policy_version: UUID | None = None
    for r in rows:
        amount = Decimal(str(r["amount"]))
        cls = await _classify(ctx, amount, _str(r["account_class"]), attest)
        if cls is not None:
            policy_label, policy_version = cls.policy.name, cls.policy.version_id
        entry_id = UUID(str(r["id"]))
        entries.append(
            ClosedEntry(
                entry_id=entry_id,
                ref=f"{str(r['kind']).upper()}-{int(str(r['number'])):02d}",
                description=_str(r["description"]),
                amount=amount,
                status=str(r["status"]),
                account_class=_str(r["account_class"]),
                version=int(str(r["version"])),
                classification=cls,
                approval_label=labels.get(entry_id),
            )
        )
    live = [e for e in entries if e.status != S.REJECTED]
    within = [
        e for e in live if e.classification and e.classification.outcome == "within_threshold"
    ]
    review = [e for e in live if e not in within]
    return CloseEntries(
        entries=tuple(entries),
        proposed=_tally(live),
        within_threshold=_tally(within),
        review_required=_tally(review),
        approved=sum(1 for e in live if e.status == S.APPROVED or e.status in _POSTED),
        role=role,
        policy_label=policy_label,
        policy_version_id=policy_version,
        may_batch_within_threshold=not attest and meets(role, "senior_or_above"),
        attest=attest,
        display_name=await _display(ctx),
    )


def _str(value: object) -> str | None:
    return None if value is None else str(value)


async def approve_batch(ctx: AuthContext, work_item_id: UUID, entry_ids: Sequence[UUID]) -> UUID:
    """Within-policy batch approval (AC: Raj approves AJE-01..04). Every entry is re-classified
    now; one outside its class limit, an attest client or a role below an entry's level refuses
    the whole batch (409 `over_approval_limit`)."""
    view = await close_entries(ctx, work_item_id)
    chosen = [e for e in view.entries if e.entry_id in set(entry_ids)]
    if len(chosen) != len(set(entry_ids)):
        raise NotFound(TARGET)
    for e in chosen:
        cls = e.classification
        if (
            view.attest
            or cls is None
            or cls.outcome != "within_threshold"
            or not cls.batch
            or not meets(view.role, cls.approver_level)
        ):
            raise OverApprovalLimit(facts={"entry_id": str(e.entry_id)})
    policy = chosen[0].classification if chosen else None
    if policy is None:
        raise OverApprovalLimit(facts={"entries": 0})
    initials = "".join(p[0] for p in (await _display(ctx)).split() if p)
    label = f"Approved by {initials} under {policy.policy.name}"
    return await _decisions.create_batch(
        ctx, work_item_id, [e.entry_id for e in chosen], policy.policy.version_id, label
    )


async def _display(ctx: AuthContext) -> str:
    return (await names_of([ctx.user_id])).get(ctx.user_id, "")


async def _entry(ctx: AuthContext, entry_id: UUID) -> dict[str, object]:
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT id, engagement_id, work_item_id, amount, account_class, status, "
                        "version FROM proposed_entries WHERE id = :id"
                    ),
                    {"id": entry_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise NotFound(TARGET)
    return dict(row)


async def approve_held(ctx: AuthContext, entry_id: UUID, seen_version: int) -> Decided:
    """A review-required entry approved by a person whose role meets its approver level, with a
    10-second Undo (CLS-07c). An attest client's entry needs a manager or partner too."""
    row = await _entry(ctx, entry_id)
    engagement_id = UUID(str(row["engagement_id"]))
    work_item_id = UUID(str(row["work_item_id"]))
    attest = await attest_of(ctx.tenant, engagement_id) is True
    cls = await _classify(ctx, Decimal(str(row["amount"])), _str(row["account_class"]), attest)
    level = "manager_or_partner" if cls is None else cls.approver_level
    if cls is not None and cls.outcome == "review_required" and level == "senior_or_above":
        level = "manager_or_partner"  # review required is never a senior's alone
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    if not meets(role, level):
        raise OverApprovalLimit(facts={"entry_id": str(entry_id)})
    if str(row["status"]) not in _OPEN:
        raise EntryLocked(facts={"status": str(row["status"])})
    decision_id = await _write(
        ctx, engagement_id, work_item_id, entry_id, "approved", seen_version, S.APPROVED
    )
    return Decided(
        decision_id, entry_id, S.APPROVED, None, await clock.now(ctx.tenant) + UNDO_WINDOW
    )


async def _write(
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    entry_id: UUID,
    decision: str,
    seen_version: int,
    status: str,
    *,
    reason_code: str | None = None,
    note: str | None = None,
) -> UUID:
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        current = (
            await tx.session.execute(
                text("SELECT version FROM proposed_entries WHERE id = :id FOR UPDATE"),
                {"id": entry_id},
            )
        ).scalar_one()
        if int(current) != seen_version:
            raise _decisions.EntriesMoved(facts={"version": int(current)})
        await _decisions.write_decision(
            tx, ctx, engagement_id, work_item_id, entry_id, decision=decision,
            seen_version=seen_version, reason_code=reason_code, note=note,
        )  # fmt: skip
        await _decisions.set_status(tx, [entry_id], status)
        decision_id = (
            await tx.session.execute(
                text(
                    "SELECT id FROM proposed_entry_decisions WHERE entry_id = :id "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"id": entry_id},
            )
        ).scalar_one()
        tx.emit(
            EntryApprovalDecided(
                proposed_entry_id=entry_id, engagement_id=engagement_id, work_item_id=work_item_id
            )
        )
        tx.record(
            f"proposed_entry.{decision}",
            target=Target(TARGET, entry_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return UUID(str(decision_id))


async def _in_batch(ctx: AuthContext, entry_id: UUID) -> bool:
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT 1 FROM posting_results WHERE proposed_entry_id = :id LIMIT 1"),
                {"id": entry_id},
            )
        ).first()
    return found is not None


async def undo(ctx: AuthContext, decision_id: UUID) -> Decided:
    """Undo inside 10 seconds of the person's own approval and before any effect started."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT d.entry_id, d.decision, d.created_at, d.actor_id, e.version, "
                        "e.engagement_id, e.work_item_id, e.amount, e.account_class "
                        "FROM proposed_entry_decisions d JOIN proposed_entries e ON e.id = "
                        "d.entry_id WHERE d.id = :id"
                    ),
                    {"id": decision_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise NotFound("proposed_entry_decision")
    entry_id = UUID(str(row["entry_id"]))
    if str(row["actor_id"]) != str(ctx.user_id):
        raise Forbidden("proposed_entry.undo_approval", "role")
    created = row["created_at"]
    if (
        row["decision"] != "approved"
        or not isinstance(created, datetime)
        or await clock.now(ctx.tenant) > created + UNDO_WINDOW
        or await _in_batch(ctx, entry_id)
    ):
        raise _decisions.UndoWindowClosed
    status = await _threshold_status(ctx, dict(row))
    new_id = await _write(
        ctx, UUID(str(row["engagement_id"])), UUID(str(row["work_item_id"])), entry_id,
        "approval_undone", int(str(row["version"])), status,
    )  # fmt: skip
    return Decided(new_id, entry_id, status, None, None)


async def _threshold_status(ctx: AuthContext, row: dict[str, object]) -> str:
    attest = await attest_of(ctx.tenant, UUID(str(row["engagement_id"]))) is True
    cls = await _classify(ctx, Decimal(str(row["amount"])), _str(row["account_class"]), attest)
    return S.REVIEW_REQUIRED if cls is None else cls.outcome


async def withdraw(
    ctx: AuthContext, entry_id: UUID, reason_code: str, note: str | None
) -> Decided:
    """An approved, unposted entry returns to its threshold result (`approval_withdrawn`)."""
    row = await _entry(ctx, entry_id)
    if str(row["status"]) != S.APPROVED or await _in_batch(ctx, entry_id):
        raise EntryLocked(facts={"status": str(row["status"])})
    status = await _threshold_status(ctx, row)
    decision_id = await _write(
        ctx, UUID(str(row["engagement_id"])), UUID(str(row["work_item_id"])), entry_id,
        "approval_withdrawn", int(str(row["version"])), status, reason_code=reason_code,
        note=note,
    )  # fmt: skip
    return Decided(decision_id, entry_id, status, None, None)


async def request_approval(ctx: AuthContext, entry_id: UUID, approver_user_id: UUID) -> Decided:
    """Route a held entry to a named approver whose role meets its level (HOME-02 + bell)."""
    row = await _entry(ctx, entry_id)
    engagement_id = UUID(str(row["engagement_id"]))
    work_item_id = UUID(str(row["work_item_id"]))
    role = await engagement_role_of(ctx.tenant, engagement_id, approver_user_id)
    if not meets(role, "manager_or_partner"):
        raise OverApprovalLimit(facts={"approver": str(approver_user_id)})
    async with uow(ctx.tenant) as tx:
        tx.emit(
            EntryApprovalRequested(
                proposed_entry_id=entry_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                recipient_user_ids=[approver_user_id],
                by_user=ctx.user_id,
            )
        )
        tx.record(
            "proposed_entry.approval_requested",
            target=Target(TARGET, entry_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return Decided(entry_id, entry_id, str(row["status"]), None, None)


async def reject(ctx: AuthContext, entry_id: UUID, reason_code: str, note: str | None) -> Decided:
    """Rejected with the person's reason (DF-23); the CLS-06 issue follows from the event."""
    if note is None:
        await _decisions.reject(ctx, entry_id, reason_code)
    else:
        await _decisions.reject_with_note(ctx, entry_id, reason_code, note)
    return Decided(entry_id, entry_id, S.REJECTED, None, None)


def role_label(role: str | None) -> str:
    return _ROLE_LABELS.get(role or "", "")


async def posting_enabled(ctx: AuthContext, work_item_id: UUID) -> bool:
    """Whether the close's engagement may post (W1 on); off shows "Export approved entries"."""
    return await posting_enabled_for(ctx.tenant, await engagement_of(ctx.tenant, work_item_id))
