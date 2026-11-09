"""AUD-19's completion checklist: a projector read model (A-07-T22; TASK-6206; DEC-2806; A-07 F2).

Each completion item comes from the firm's published completion checklist for the engagement type
(methodology's `assurance_checklist_templates`, 0741) and lands as one `completion_items` row
(0664). A derived item's status changes only here, from the engagement's own facts: findings,
notes, sign-offs, EQR, FS approval, the representation letter, governance communications,
independence and materiality. A manual item (`derived: false` in the template) reads the same
facts but is the only kind a manager may mark not applicable, with a basis (sealed); the N/A then
sticks. A derived one answers 409 `item_derived`.

- **An outbox consumer** (`on_completion_event`): every subscribed event names its work item; the
  projector recomputes that work item's derived rows. It is idempotent on `event_id`
  (`last_event_id`): a redelivered event changes nothing.
- **Facts come through providers** (`register_completion_fact(key, provider)`), one per item key,
  so the module that owns a fact answers it; an item with no provider stays open and reads "Not
  yet derived" rather than a status nobody computed.
- **Rebuild** (`rebuild`) recomputes every derived row from the facts alone, so a rebuild yields
  identical rows to the projection it replaces (the row's acceptance).
- **Inert until M16**: the subscriber returns at once unless the firm's `assurance_release_mode`
  is `in_app` and its `audits.completion` flag is on (A-07-T33; off by default before M16).

Counts exclude N/A ("12 of 17"). Blockers are the open items, with their gate tag, whether they
depend on the client, and whether they fall due on the report date.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance.release import release_mode
from abacus.modules.engagements.api import assurance_item, assurance_item_id, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.methodology.api import AssuranceChecklistItem, published_checklist

ItemStatus = Literal["done", "open", "not_applicable", "partial"]
NOT_DERIVED: Final = "Not yet derived"
MARK_NA: Final = "completion.update"  # the manual N/A, a manager's (A-07-T04 matrix)
READ: Final = "completion.read"


class ItemDerived(DomainConflict):
    """A derived item's status is the projector's; only a manual item may be marked N/A."""

    code = "item_derived"


class BasisRequired(DomainInvalid):
    code = "basis_required"


@dataclass(frozen=True)
class ItemFact:
    """What a provider answers for one item: its status, a code-worded evidence line (never client
    text) and the screen that clears it."""

    status: ItemStatus
    evidence_text: str | None = None
    link_target: str | None = None


type FactProvider = Callable[[TenantContext, UUID], Awaitable[ItemFact | None]]
_FACTS: dict[str, FactProvider] = {}


def register_completion_fact(key: str, provider: FactProvider) -> None:
    """One provider per item key; the module that owns the fact registers it."""
    found = _FACTS.get(key)
    if found is not None and found is not provider:
        raise ValueError(f"completion item {key!r} already has a fact provider")
    _FACTS[key] = provider


def registered_facts() -> frozenset[str]:
    return frozenset(_FACTS)


def engagement_type_of(assurance_type: str, ebp_plan_kind: str | None) -> str:
    """The template's engagement type: an EBP plan audit, else the assurance type's own."""
    if ebp_plan_kind is not None:
        return "ebp_audit"
    return "fs_audit" if assurance_type == "audit" else assurance_type


async def projector_live(tenant: TenantContext) -> bool:
    """A-07-T33 (DEC-3106): the firm's `audits.completion` flag replaces COMPLETION_LIVE."""
    from abacus.modules.assurance.a07_registrations import live

    return await live(tenant, "audits.completion") and await release_mode(tenant) == "in_app"


@dataclass(frozen=True)
class ProjectedRow:
    item_key: str
    position: int
    status: ItemStatus
    derived: bool
    evidence_text: str | None
    link_target: str | None
    gate_tag: str | None
    depends_on_client: bool
    due_on: date | None


async def derive(
    tenant: TenantContext,
    work_item_id: UUID,
    items: Sequence[AssuranceChecklistItem],
    report_date: date | None,
) -> list[ProjectedRow]:
    """Every derived row's state from the facts alone (pure over the providers)."""
    out: list[ProjectedRow] = []
    for position, item in enumerate(items, start=1):
        # A manual item (`derived: false`) still reads its facts; it differs only in that a
        # manager may mark it not applicable, which then sticks (the upsert keeps it).
        provider = _FACTS.get(item.key)
        fact = None if provider is None else await provider(tenant, work_item_id)
        status: ItemStatus = "open" if fact is None else fact.status
        out.append(
            ProjectedRow(
                item_key=item.key,
                position=position,
                status=status,
                derived=item.derived,
                evidence_text=NOT_DERIVED if fact is None else fact.evidence_text,
                link_target=None if fact is None else fact.link_target,
                gate_tag=item.gate_tag,
                depends_on_client=item.depends_on_client,
                due_on=report_date if item.due_on_report_date else None,
            )
        )
    return out


_REPORT_DATE = text(
    "SELECT report_date FROM audit_reports WHERE work_item_id = :wi "
    "ORDER BY updated_at DESC LIMIT 1"
)
_UPSERT = text(
    """
    INSERT INTO completion_items (tenant_id, engagement_id, work_item_id, item_key,
        template_version_id, position, status, derived, evidence_text, link_target, gate_tag,
        depends_on_client, due_on, last_event_id)
    VALUES (:tenant, :engagement, :wi, :key, :template, :position,
        :status, :derived, :evidence, :link, :gate, :client, :due, :event)
    ON CONFLICT (tenant_id, work_item_id, item_key) DO UPDATE SET
        status = CASE WHEN completion_items.status = 'not_applicable'
                      THEN completion_items.status ELSE EXCLUDED.status END,
        evidence_text = CASE WHEN completion_items.status = 'not_applicable'
                             THEN completion_items.evidence_text ELSE EXCLUDED.evidence_text END,
        link_target = EXCLUDED.link_target,
        gate_tag = EXCLUDED.gate_tag,
        depends_on_client = EXCLUDED.depends_on_client,
        due_on = EXCLUDED.due_on,
        last_event_id = EXCLUDED.last_event_id,
        version = completion_items.version + 1,
        updated_at = clock_timestamp()
    WHERE completion_items.last_event_id IS DISTINCT FROM EXCLUDED.last_event_id
    RETURNING item_key
    """
)


async def store_items(
    tenant: TenantContext, work_item_id: UUID, event_id: UUID, *, live_check: bool = True
) -> int:
    """Project one work item for one event: the rows that changed. Idempotent on `event_id`."""
    if live_check and not await projector_live(tenant):
        return 0
    item = await assurance_item(tenant, work_item_id)
    checklist = await published_checklist(
        tenant, "completion", engagement_type_of(item.assurance_type, item.ebp_plan_kind)
    )
    if checklist is None:
        return 0  # the firm has no published completion checklist for this type: nothing listed
    async with tenant_session(tenant) as session:
        report_date = await session.scalar(_REPORT_DATE, {"wi": work_item_id})
    rows = await derive(tenant, work_item_id, checklist.items, report_date)
    changed = 0
    async with uow(tenant) as tx:
        for row in rows:
            found = await tx.session.scalar(
                _UPSERT,
                {
                    "tenant": tenant.tenant_id,
                    "engagement": item.engagement_id,
                    "wi": work_item_id,
                    "key": row.item_key,
                    "template": checklist.version_id,
                    "position": row.position,
                    "status": row.status,
                    "derived": row.derived,
                    "evidence": row.evidence_text,
                    "link": row.link_target,
                    "gate": row.gate_tag,
                    "client": row.depends_on_client,
                    "due": row.due_on,
                    "event": event_id,
                },
            )
            changed += found is not None
        if changed:
            tx.record(
                "completion.item_changed",
                target=Target("work_item", work_item_id),
                after=Ref(event=event_id, rows=changed),
                scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
            )
    return changed


async def rebuild(tenant: TenantContext, work_item_id: UUID) -> int:
    """Recompute every derived row from the facts (an operator's rebuild, or after a template
    change). Manual N/A rows keep their status and basis."""
    return await store_items(tenant, work_item_id, uuid4(), live_check=False)


# The events that can move a derived item (A-07 F2): findings and the SUM (decision cards), notes,
# sign-offs, the EQR, the rep letter's envelope, independence and materiality. Each carries its
# work item or its engagement; the projector finds the engagement's assurance work item.
SUBSCRIBED: Final = (
    "decision.decided",
    "review_note.raised",
    "review_note.cleared",
    "review_note.reopened",
    "review_note.withdrawn",
    "sign_off.recorded",
    "sign_off.went_stale",
    "eqr.concurred_v2",
    "envelope.completed",
    "independence.confirmed",
    "independence.concluded",
    "materiality.decided",
    "materiality.revised",
    "deliverable.published",
)


async def on_completion_event(event: OutboxEvent) -> None:
    """The outbox consumer: returns at once while A-07 is dark (no firm before M16)."""
    tenant = TenantContext(event.tenant_id, "system", "completion_projector")
    if not await projector_live(tenant):
        return
    payload = event.payload
    raw = payload.get("work_item_id")
    if raw is not None:
        work_item_id: UUID | None = UUID(str(raw))
    else:
        engagement = payload.get("engagement_id")
        work_item_id = (
            None if engagement is None else await assurance_item_id(tenant, UUID(str(engagement)))
        )
    if work_item_id is None:
        return
    if await store_items(tenant, work_item_id, event.event_id):
        await _readiness_after_burst(event.tenant_id, work_item_id)


async def _readiness_after_burst(tenant_id: UUID, work_item_id: UUID) -> None:
    """#4231 (DEC-3138): the first change of a burst starts the 60-second readiness run; later
    changes attach to it while it waits; a finished one lets the next burst start anew."""
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from abacus.kernel.dispatch import dispatch
    from abacus.modules.assurance.completion_readiness_workflow import (
        CompletionReadinessWorkflow,
        ReadinessInput,
        workflow_id,
    )

    await dispatch(
        CompletionReadinessWorkflow,
        ReadinessInput(str(tenant_id), str(work_item_id)),
        id=workflow_id(tenant_id, work_item_id),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


# --- the read and the manual N/A -----------------------------------------------------------------


@dataclass(frozen=True)
class CompletionRow:
    id: UUID
    item_key: str
    position: int
    status: ItemStatus
    derived: bool
    evidence_text: str | None
    link_target: str | None
    gate_tag: str | None
    depends_on_client: bool
    due_on: date | None


@dataclass(frozen=True)
class CompletionChecklist:
    rows: tuple[CompletionRow, ...]
    done: int
    not_applicable: int
    open: int
    blockers: tuple[CompletionRow, ...]

    @property
    def counted(self) -> int:
        """The summary's denominator: N/A excluded ("12 of 17")."""
        return len(self.rows) - self.not_applicable


def summarise(rows: Sequence[CompletionRow]) -> CompletionChecklist:
    done = sum(1 for r in rows if r.status == "done")
    na = sum(1 for r in rows if r.status == "not_applicable")
    blockers = tuple(r for r in rows if r.status in ("open", "partial"))
    return CompletionChecklist(tuple(rows), done, na, len(blockers), blockers)


_ROWS = text(
    "SELECT id, item_key, position, status, derived, evidence_text, link_target, gate_tag, "
    "depends_on_client, due_on FROM completion_items WHERE work_item_id = :wi ORDER BY position"
)


async def rows_of(tenant: TenantContext, work_item_id: UUID) -> list[CompletionRow]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_ROWS, {"wi": work_item_id})).all()
    return [
        CompletionRow(
            r.id, r.item_key, r.position, r.status, r.derived, r.evidence_text, r.link_target,
            r.gate_tag, r.depends_on_client, r.due_on,
        )
        for r in found
    ]  # fmt: skip


async def checklist_for(ctx: AuthContext, work_item_id: UUID) -> CompletionChecklist:
    item = await assurance_item(ctx.tenant, work_item_id)
    await authorise(ctx, READ, (await get_ref(ctx, item.engagement_id)).resource())
    return summarise(await rows_of(ctx.tenant, work_item_id))


async def _na(tx: UnitOfWork, item_id: UUID) -> tuple[UUID, UUID, bool]:
    row = (
        await tx.session.execute(
            text(
                "SELECT engagement_id, work_item_id, derived FROM completion_items "
                "WHERE id = :id FOR UPDATE"
            ),
            {"id": item_id},
        )
    ).first()
    if row is None:
        raise NotFound("completion_item")
    return row.engagement_id, row.work_item_id, bool(row.derived)


async def mark_not_applicable(ctx: AuthContext, item_id: UUID, basis: str) -> None:
    """A manager marks a manual item N/A with a basis (sealed, Restricted); a derived item is
    409 `item_derived`. A person's act: never an agent's or the system's."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(MARK_NA, "role")
    if not basis.strip():
        raise BasisRequired(facts={"field": "basis"})
    async with uow(ctx.tenant) as tx:
        engagement_id, work_item_id, derived = await _na(tx, item_id)
        await authorise(ctx, MARK_NA, (await get_ref(ctx, engagement_id)).resource())
        if derived:
            raise ItemDerived
        sealed = await seal(ctx.tenant_id, basis.strip().encode(), f"completion_item:{item_id}")
        await tx.session.execute(
            text(
                "UPDATE completion_items SET status = 'not_applicable', na_basis_sealed = :b, "
                "na_by = :by, version = version + 1, updated_at = clock_timestamp() "
                "WHERE id = :id"
            ),
            {"b": sealed, "by": ctx.user_id, "id": item_id},
        )
        tx.record(
            "completion.item_changed",
            target=Target("completion_item", item_id),
            after=Ref(status="not_applicable"),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


__all__ = [
    "SUBSCRIBED",
    "BasisRequired",
    "CompletionChecklist",
    "CompletionRow",
    "FactProvider",
    "ItemDerived",
    "ItemFact",
    "checklist_for",
    "derive",
    "engagement_type_of",
    "mark_not_applicable",
    "on_completion_event",
    "projector_live",
    "rebuild",
    "register_completion_fact",
    "registered_facts",
    "rows_of",
    "store_items",
    "summarise",
]
