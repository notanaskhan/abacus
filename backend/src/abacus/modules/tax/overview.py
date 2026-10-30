"""TAX-02's return record and overview read model, and its record projection (T-02-T13; T-02 §3.3;
SPEC-502; DEC-1368).

- **The record** (`tax_return.read_metadata`): the board's row, the engine id, the policy pin, the
  tabs the pilot shows (Overview and Intake, DV-2) and what the viewer may do.
- **The overview** (`tax_return.read_metadata`, plus content when the viewer holds
  `tax_return.read`): the Team ladder from C3 sign-offs on the return, the pipeline derived from
  its status, the Filing band with the C19 consent summary, and the engine summary from the
  newest *approved* CCH import only (ADR-231; never a pro forma's figure as the estimate). A viewer
  without content rights gets the ladder, pipeline and Filing band and no figure: the TRI fields
  are absent, not masked.
- **Transitions** a person may request (`tax_return.status_change`): `start_preparation` and
  `start_review`, at the row version seen (`transitions.apply_transition`).
- **The record projection** (outbox subscribers, the system): a published binder opens intake
  (`not_started` → `gathering`); the preparer's L1 sign-off on the return marks it prepared
  (`preparing` → `prepared`). A move the table does not hold is skipped, never forced.

The issues top-n and the K-1 dependency rows are empty until C3's issue reads and T-02's K-1
hand-offs reach this module (no invented rows: an empty list draws no band).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._statuses import ReturnStatus
from abacus.kernel.clock import FIRM_ZONE
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import WorkItemFacts, work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    engagement_resource,
    names_of,
)
from abacus.modules.organisations.api import consent_state
from abacus.modules.review.api import Json, content_hash, sign_off_states
from abacus.modules.tax import board
from abacus.modules.tax.returns_contract import (
    EngineSummaryLineOut,
    FilingRowOut,
    LadderStepOut,
    PersonChipOut,
    PipelineStepOut,
    TabCountOut,
    TaxReturnOverviewOut,
    TaxReturnRecordOut,
)
from abacus.modules.tax.status import TransitionRefused
from abacus.modules.tax.transitions import apply_transition

KIND: Final = "tax_return"
METADATA: Final = "tax_return.read_metadata"
CONTENT: Final = "tax_return.read"
ACTIONS: Final = ("tax_return.assign", "tax_return.status_change", "tax_return.approve")
# The ladder's rungs: (step, sign-off level, the assignment functions that hold it).
_RUNGS: Final = (
    ("preparer", 1, ("preparer",)),
    ("detail_review", 2, ("detail_reviewer", "first_level_reviewer")),
    ("manager_review", 3, ("manager_reviewer",)),
    ("final_approval", 4, ("signer",)),
)
_ORDER: Final = [s.value for s in ReturnStatus]

_ONE = text(
    "SELECT work_item_id, form, tax_year, status, review_level, extended, on_hold, sync_status, "
    "original_due_on, extended_due_on, row_version, engine, engine_return_id, "
    "approval_policy_version_id, client_entity_id, jurisdictions FROM tax_returns "
    "WHERE work_item_id = :id"
)
_SUMMARY = text(
    "SELECT engine_version, lines, approved_at FROM return_engine_summaries "
    "WHERE work_item_id = :id AND kind <> 'pro_forma' ORDER BY approved_at DESC LIMIT 1"
)


@dataclass(frozen=True)
class Loaded:
    facts: WorkItemFacts
    row: board.ReturnRow
    row_version: int
    engine: str | None
    engine_return_id: str | None
    policy_version_id: UUID | None
    client_entity_id: UUID
    jurisdictions: tuple[str, ...]


async def _load(ctx: AuthContext, return_id: UUID) -> Loaded:
    """The return as the viewer may see it (404 otherwise, INV-3)."""
    if ctx.client:
        raise NotFound(KIND)
    await authorise(ctx, METADATA, Resource.firm(ctx.tenant_id))
    facts = next(
        (f for f in await work_item_facts(ctx, KIND) if f.work_item_id == return_id), None
    )
    if facts is None:
        raise NotFound(KIND)
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_ONE, {"id": return_id})).first()
    if found is None:
        raise NotFound(KIND)
    return Loaded(
        facts,
        board.ReturnRow(*found[:10]),
        int(found.row_version),
        found.engine,
        found.engine_return_id,
        found.approval_policy_version_id,
        found.client_entity_id,
        tuple(found.jurisdictions or ()),
    )


async def _resource(ctx: AuthContext, loaded: Loaded) -> Resource:
    base = await engagement_resource(ctx.tenant, loaded.facts.engagement_id)
    return replace(base, work_item_id=loaded.facts.work_item_id)


async def record(ctx: AuthContext, return_id: UUID) -> TaxReturnRecordOut:
    loaded = await _load(ctx, return_id)
    people = {u for us in loaded.facts.assignees.values() for u in us}
    names = await names_of(sorted(people)) if people else {}
    may = await allowed_actions(ctx, await _resource(ctx, loaded), ACTIONS)
    return TaxReturnRecordOut(
        row=board.row_out(loaded.row, loaded.facts, names),
        engagement_id=loaded.facts.engagement_id,
        work_item_id=return_id,
        engine_return_id=loaded.engine_return_id,
        approval_policy_version_id=loaded.policy_version_id,
        tabs=[TabCountOut(tab="overview", count=None), TabCountOut(tab="intake", count=None)],
        allowed_actions=sorted(may),
    )


# --- the overview -------------------------------------------------------------------------------


def _day(at: datetime | date) -> str:
    on = at.astimezone(FIRM_ZONE).date() if isinstance(at, datetime) else at
    return f"{on:%b} {on.day}"


def _initials(name: str) -> str:
    return "".join(p[0] for p in name.split()[:2] if p)


async def _summary(
    tenant: TenantContext, return_id: UUID
) -> tuple[str, list[object], datetime] | None:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_SUMMARY, {"id": return_id})).first()
    if found is None:
        return None
    return str(found.engine_version), list(found.lines), found.approved_at


def _amount(raw: object) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _lines(lines: Sequence[object]) -> list[EngineSummaryLineOut]:
    out: list[EngineSummaryLineOut] = []
    for raw in lines:
        if not isinstance(raw, dict):
            continue
        line = cast(Mapping[str, object], raw)
        key, label = line.get("line_key"), line.get("label")
        if not isinstance(key, str) or not isinstance(label, str):
            continue
        ref = line.get("line_ref")
        total = line.get("total")
        out.append(
            EngineSummaryLineOut(
                line_key=key,
                label=label,
                amount=_amount(line.get("amount")),
                line_ref=ref if isinstance(ref, str) else None,
                indent=line.get("indent") is True,
                total="total" if total == "total" else "grand" if total == "grand" else None,
            )
        )
    return out


def _ladder(
    loaded: Loaded,
    states: Mapping[int, tuple[UUID | None, datetime | None, bool]],
    names: Mapping[UUID, str],
) -> list[LadderStepOut]:
    status = loaded.row.status
    out: list[LadderStepOut] = []
    current_found = False
    for step, level, functions in _RUNGS:
        holder = next((u for f in functions for u in loaded.facts.assignees.get(f, ())), None)
        name = names.get(holder) if holder else None
        signed_by, signed_at, stale = states.get(level, (None, None, True))
        done = signed_by is not None and not stale
        in_progress = (
            not done
            and not current_found
            and (
                (step == "preparer" and status == "preparing")
                or (step != "preparer" and status in ("in_review", "action_required"))
            )
        )
        current_found = current_found or in_progress
        if done and signed_at is not None:
            verb = "submitted" if step == "preparer" else "signed off"
            signer = names.get(signed_by) if signed_by else None
            note = f"{signer or name or ''} · {verb} {_day(signed_at)}".strip(" ·")
        elif in_progress and name:
            note = f"{name} · in progress"
        elif step == "final_approval" and name:
            note = f"{name} · signer"
        elif name:
            note = f"{_initials(name)} · not started"
        else:
            note = None
        out.append(
            LadderStepOut(
                role="preparer" if step == "preparer" else "signer" if level == 4 else "reviewer",
                person=PersonChipOut(user_id=holder, initials=_initials(name), name=name)
                if holder and name
                else None,
                signed_off_at=signed_at if done else None,
                step=step,  # type: ignore[arg-type] -- one of LadderStep
                state="done" if done else "in_progress" if in_progress else "not_started",
                note=note,
            )
        )
    return out


def _pipeline(status: str) -> list[PipelineStepOut]:
    at = _ORDER.index(status) if status in _ORDER else 0
    stages = (
        ("gather", ReturnStatus.GATHERING, ReturnStatus.PREPARING),
        ("prepare", ReturnStatus.PREPARING, ReturnStatus.PREPARED),
        ("review", ReturnStatus.PREPARED, ReturnStatus.APPROVED),
        ("deliver", ReturnStatus.APPROVED, ReturnStatus.ACCEPTED),
    )
    out: list[PipelineStepOut] = []
    for step, starts, ends in stages:
        begun = at >= _ORDER.index(starts.value)
        finished = at >= _ORDER.index(ends.value) and (step != "deliver" or status == "accepted")
        out.append(
            PipelineStepOut(
                step=step,  # type: ignore[arg-type] -- one of PipelineStep
                state="done" if finished else "in_progress" if begun else "not_started",
                sub="",
            )
        )
    return out


async def _filing(ctx: AuthContext, loaded: Loaded) -> tuple[list[FilingRowOut], bool | None]:
    row = loaded.row
    rows: list[FilingRowOut] = []
    due = row.extended_due_on if row.extended else row.original_due_on
    if due is not None:
        suffix = " (extended)" if row.extended else ""
        rows.append(FilingRowOut(key="due", value=f"{due:%b} {due.day}, {due.year}{suffix}"))
    if loaded.jurisdictions:
        rows.append(FilingRowOut(key="jurisdictions", value=" · ".join(loaded.jurisdictions)))
    if loaded.engine_return_id:
        rows.append(FilingRowOut(key="engine", value=f"CCH Axcess · {loaded.engine_return_id}"))
    states = [
        s
        for purpose in ("use", "ai_disclosure")
        for s in await consent_state(ctx.tenant, [loaded.client_entity_id], purpose, row.tax_year)
    ]
    ok = all(s.status == "signed" for s in states) if states else None
    if ok:
        rows.append(
            FilingRowOut(
                key="consents",
                value="",
                pill="Signed",
                detail="Use · AI disclosure (2 consents)",
            )
        )
    return rows, ok


async def overview(ctx: AuthContext, return_id: UUID) -> TaxReturnOverviewOut:
    loaded = await _load(ctx, return_id)
    resource = await _resource(ctx, loaded)
    may = await allowed_actions(ctx, resource, (*ACTIONS, CONTENT))
    content = CONTENT in may
    found = await _summary(ctx.tenant, return_id) if content else None
    value_hash = content_hash(cast(Json, {"lines": found[1]})) if found else ""
    sign_offs = (await sign_off_states(ctx.tenant, KIND, [return_id], {return_id: value_hash}))[
        return_id
    ]
    states = {s.level: (s.signed_by, s.signed_at, s.stale) for s in sign_offs}
    people = {u for us in loaded.facts.assignees.values() for u in us} | {
        s.signed_by for s in sign_offs if s.signed_by
    }
    names = await names_of(sorted(people)) if people else {}
    filing, consent_ok = await _filing(ctx, loaded)
    return TaxReturnOverviewOut(
        return_id=return_id,
        ladder=_ladder(loaded, states, names),
        engine_version=found[0] if found else None,
        engine_summary=_lines(found[1]) if found else [],
        open_issues=0,
        k1_dependencies=[],
        consent_ok=consent_ok,
        allowed_actions=sorted(a for a in may if a != CONTENT),
        filing=filing,
        pipeline=_pipeline(loaded.row.status),
        engine_synced_on=found[2].astimezone(FIRM_ZONE).date() if found else None,
    )


# --- transitions and the record projection ------------------------------------------------------


async def transition(
    ctx: AuthContext, return_id: UUID, event: str, seen_version: int
) -> TaxReturnRecordOut:
    """`start_preparation` or `start_review`, a person's request at the version seen."""
    loaded = await _load(ctx, return_id)
    await authorise(ctx, "tax_return.status_change", await _resource(ctx, loaded))
    await apply_transition(ctx.tenant, return_id, event, seen_version=seen_version)
    return await record(ctx, return_id)


async def _project(tenant_id: UUID, return_id: UUID, event: str, reason: str) -> None:
    tenant = TenantContext(tenant_id, "system", f"tax:projection:{reason}")
    async with tenant_session(tenant) as session:
        found = (await session.execute(_ONE, {"id": return_id})).first()
    if found is None:
        return  # not a tax return
    try:
        await apply_transition(tenant, return_id, event, seen_version=int(found.row_version))
    except TransitionRefused:
        return  # already further on: a projection never forces a move


async def on_binder_published(event: OutboxEvent) -> None:
    item = event.payload.get("work_item_id")
    if isinstance(item, str):
        await _project(event.tenant_id, UUID(item), "intake_opened", "binder")


async def on_sign_off_recorded(event: OutboxEvent) -> None:
    p = event.payload
    if (
        p.get("target_type") == KIND
        and p.get("level") == 1
        and isinstance(p.get("target_id"), str)
    ):
        await _project(event.tenant_id, UUID(str(p["target_id"])), "prepared", "sign_off")


__all__ = [
    "on_binder_published",
    "on_sign_off_recorded",
    "overview",
    "record",
    "transition",
]
