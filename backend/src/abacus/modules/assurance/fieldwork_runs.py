"""Fieldwork runs (A-08-T24; A-08 §3 F2, F5, F8, F9; SPEC-657 AC-9.1 to AC-9.3; AUD-12 d,
AUD-13 b, AUD-26 a; DEC-5403; amber).

A person starts every run; each agent run is "<initiator> via Agent" (INV-5), on the section
drafter (`workpapers.section_drafter`, A-08-T23's modes), behind `audits.fieldwork_agents`:

- **AUD-12 Begin / Re-run**: one `fieldwork_attribute` run per sampled item (section `item:<n>`),
  on the test's own working paper.
- **AUD-13 / AUD-26 Run**: three run rows. "Compare the trial balance to the ledger and source
  documents, and show what doesn't tie" is code (`ledger.tie_out`: the layer's debits against
  credits, recorded, no model). "Figure out why … changed" is one `flux_explain` run per
  over-threshold line still Unexplained (section `line:<n>`) on the engagement's analytics paper
  (`AN-1`). "Prepare client questions for unexplained movements" is code templating (DV-4): the
  lines a person may ask about; the wording comes from the firm's template on the Ask client
  sheet.
- **AUD-14 Reconcile**: one `confirmation_reconcile` run for a confirmation whose response
  differs, on the engagement's confirmations paper (`CF-1`).

**DF-04**: where the section drafter is not cleared for the firm's client data, the drafter's
start refuses with 409 `drafting_not_enabled` before any run is recorded, so no model call is
ever made; the screen shows DF-04. Progress is the runs' own C6 v2 state (the SSE stream; the
run-rows read is the polling fallback). Nothing here accepts, adopts or sends.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import AUDITS_FIELDWORK_AGENTS
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, names_of

RowKind = Literal[
    "fieldwork_attribute", "flux_explain", "tie_out", "client_questions", "confirmation_reconcile"
]
LABELS: Final[dict[str, str]] = {
    "tie_out": (
        "Compare the trial balance to the ledger and source documents, and show what doesn't tie"
    ),
    "flux_explain": (
        "Figure out why these lines changed from last year and trace it back to the source"
    ),
    "client_questions": "Prepare client questions for unexplained movements",
    "fieldwork_attribute": "Test each sampled item against its attributes",
    "confirmation_reconcile": "Reconcile the response to the books",
}
ANALYTICS_PAPER: Final = ("AN-1", "Analytics")
CONFIRMATIONS_PAPER: Final = ("CF-1", "Confirmations")
MAX_ITEMS: Final = 200

_INSERT: Final = text(
    "INSERT INTO fieldwork_run_rows (tenant_id, engagement_id, work_item_id, target_kind, "
    "target_id, kind, run_ids, items, initiator_user_id, code_result, idempotency_key) VALUES "
    "(:t, :e, :w, :tk, :target, :k, :runs, :n, :by, CAST(:result AS jsonb), :key) "
    "ON CONFLICT (tenant_id, target_id, kind, idempotency_key) DO NOTHING RETURNING id"
)
_ROWS: Final = text(
    "SELECT DISTINCT ON (kind) id, kind, run_ids, items, initiator_user_id, code_result, "
    "created_at FROM fieldwork_run_rows WHERE target_id = :target "
    "ORDER BY kind, created_at DESC, id DESC"
)


@dataclass(frozen=True)
class RunRow:
    kind: RowKind
    label: str
    run_ids: tuple[UUID, ...]
    items: int
    states: dict[str, int]  # C6 v2 state -> runs in it
    attribution: str  # "Simone Baptiste via Agent"; a code row "Code"
    code_result: dict[str, object] | None
    started_at: datetime


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _on(tenant: TenantContext) -> None:
    if not await flag_enabled(tenant, AUDITS_FIELDWORK_AGENTS):
        raise NotFound(AUDITS_FIELDWORK_AGENTS.name)


async def _paper(ctx: AuthContext, engagement_id: UUID, code: str, title: str) -> UUID:
    """The engagement's run paper (`AN-1`, `CF-1`), opened once by the person running."""
    from abacus.modules.workpapers.api import create_workpaper, workpapers_for

    found = next((p for p in await workpapers_for(ctx, engagement_id) if p.code == code), None)
    if found is not None:
        return found.id
    return await create_workpaper(ctx, engagement_id, code, title, None)


async def _record(
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    target_kind: str,
    target_id: UUID,
    kind: RowKind,
    run_ids: Sequence[UUID],
    items: int,
    code_result: dict[str, object] | None,
    key: str,
) -> None:
    async with uow(ctx.tenant) as tx:
        made = await tx.session.scalar(
            _INSERT,
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": work_item_id,
                "tk": target_kind,
                "target": target_id,
                "k": kind,
                "runs": list(run_ids),
                "n": items,
                "by": ctx.user_id,
                "result": None if code_result is None else json.dumps(code_result, sort_keys=True),
                "key": key,
            },
        )
        if made is not None:
            tx.record(
                "fieldwork_run.started",
                target=Target(target_kind, target_id),
                after=Ref(n=items, m=len(run_ids)),
            )


async def _fan_out(
    ctx: AuthContext,
    engagement_id: UUID,
    workpaper_id: UUID,
    mode: str,
    sections: Sequence[str],
    key: str,
) -> list[UUID]:
    """One drafter run per section; the first start refuses DF-04 before anything is recorded."""
    from abacus.modules.agents.api import start_section_draft

    runs: list[UUID] = []
    for section in sections[:MAX_ITEMS]:
        runs.append(
            await start_section_draft(
                ctx, engagement_id, workpaper_id, mode, section, f"{key}:{section}"
            )
        )
    return runs


async def _initiator(user_id: UUID) -> str:
    name = (await names_of([user_id])).get(user_id, "")
    return f"{name} via Agent" if name else "via Agent"


# --- AUD-12 --------------------------------------------------------------------------------------


async def run_test(ctx: AuthContext, test_id: UUID, key: str) -> object:
    """`POST /v1/tests/{id}/runs` (the route authorised `test.run`)."""
    from abacus.modules.workpapers.api import FieldworkRun, fieldwork_run_facts

    _person(ctx, "test.run")
    await _on(ctx.tenant)
    facts = await fieldwork_run_facts(ctx, test_id)
    sections = [f"item:{p}" for p in facts.positions]
    runs = await _fan_out(
        ctx, facts.engagement_id, facts.workpaper_id, "fieldwork_attribute", sections, key
    )
    await _record(
        ctx,
        engagement_id=facts.engagement_id,
        work_item_id=facts.work_item_id,
        target_kind="attribute_test",
        target_id=test_id,
        kind="fieldwork_attribute",
        run_ids=runs,
        items=len(runs),
        code_result=None,
        key=key,
    )
    if not runs:
        raise NotFound("sample_item")
    name = (await names_of([ctx.user_id])).get(ctx.user_id, "")
    return FieldworkRun(runs[0], len(runs), name)


def register() -> None:
    from abacus.modules.workpapers.api import register_test_runner

    register_test_runner(run_test)  # type: ignore[arg-type] -- returns a FieldworkRun


# --- AUD-13 / AUD-26 -----------------------------------------------------------------------------


async def run_analytics(ctx: AuthContext, set_id: UUID, key: str) -> list[RunRow]:
    """The three run rows: the tie-out (code), `flux_explain` per Unexplained line, questions
    (code templating)."""
    from abacus.modules.assurance import analytics

    _person(ctx, "analytics.explain")
    await _on(ctx.tenant)
    view = await analytics.set_view(ctx, set_id)
    if view.status != "current":
        raise analytics.SetNotCurrent(facts={"status": view.status})
    from abacus.modules.identity.api import authorise

    await authorise(
        ctx,
        "analytics.explain",
        await analytics._resource(  # pyright: ignore[reportPrivateUsage] -- the module's own
            ctx, view.engagement_id
        ),
    )
    unexplained = [x for x in view.lines if x.status == "unexplained"]
    paper = await _paper(ctx, view.engagement_id, *ANALYTICS_PAPER)
    runs = await _fan_out(
        ctx,
        view.engagement_id,
        paper,
        "flux_explain",
        [f"line:{x.position}" for x in unexplained],
        key,
    )
    common = {
        "engagement_id": view.engagement_id,
        "work_item_id": view.work_item_id,
        "target_kind": "analytics_set",
        "target_id": set_id,
        "key": key,
    }
    await _record(
        ctx,
        kind="tie_out",
        run_ids=(),
        items=view.tallies.lines,
        code_result={"tb_balanced": view.tallies.tb_balanced, "engine": "ledger.tie_out"},
        **common,  # type: ignore[arg-type] -- the row's scope
    )
    await _record(
        ctx,
        kind="flux_explain",
        run_ids=runs,
        items=len(runs),
        code_result=None,
        **common,  # type: ignore[arg-type] -- the row's scope
    )
    await _record(
        ctx,
        kind="client_questions",
        run_ids=(),
        items=len(unexplained),
        code_result={"positions": [x.position for x in unexplained]},
        **common,  # type: ignore[arg-type] -- the row's scope
    )
    return await run_rows(ctx, set_id)


# --- AUD-14 --------------------------------------------------------------------------------------


async def run_reconcile(ctx: AuthContext, confirmation_id: UUID, key: str) -> list[RunRow]:
    """A response that differs from the books: one `confirmation_reconcile` run (the agent
    proposes reconciling items; a person accepts them)."""
    _person(ctx, "confirmation.read")
    await _on(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT engagement_id, work_item_id FROM confirmations WHERE id = :id"),
                {"id": confirmation_id},
            )
        ).first()
    if found is None:
        raise NotFound("confirmation")
    from abacus.modules.engagements.api import engagement_resource_of
    from abacus.modules.identity.api import authorise

    await authorise(
        ctx, "confirmation.read", await engagement_resource_of(ctx.tenant, found.engagement_id)
    )
    paper = await _paper(ctx, found.engagement_id, *CONFIRMATIONS_PAPER)
    runs = await _fan_out(
        ctx,
        found.engagement_id,
        paper,
        "confirmation_reconcile",
        [f"confirmation:{confirmation_id}"],
        key,
    )
    await _record(
        ctx,
        engagement_id=found.engagement_id,
        work_item_id=found.work_item_id,
        target_kind="confirmation",
        target_id=confirmation_id,
        kind="confirmation_reconcile",
        run_ids=runs,
        items=len(runs),
        code_result=None,
        key=key,
    )
    return await run_rows(ctx, confirmation_id)


# --- the polling fallback ------------------------------------------------------------------------


async def run_rows(ctx: AuthContext, target_id: UUID) -> list[RunRow]:
    """The latest row of each kind for the target, with its runs' C6 v2 states counted."""
    from abacus.modules.agents.api import run_v2_status

    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ROWS, {"target": target_id})).mappings().all()
    out: list[RunRow] = []
    order = list(LABELS)
    for r in sorted(rows, key=lambda r: order.index(str(r["kind"]))):
        run_ids = tuple(cast("list[UUID]", r["run_ids"] or []))
        states: dict[str, int] = {}
        for run_id in run_ids:
            # A run the reader cannot see (RLS) or that has no v2 state yet is not counted.
            state = await run_v2_status(ctx.tenant, run_id)
            if state is not None:
                states[state] = states.get(state, 0) + 1
        kind = cast(RowKind, r["kind"])
        code = kind in ("tie_out", "client_questions")
        result = r["code_result"]
        out.append(
            RunRow(
                kind=kind,
                label=LABELS[kind],
                run_ids=run_ids,
                items=int(r["items"]),
                states=states,
                attribution="Code"
                if code
                else await _initiator(cast(UUID, r["initiator_user_id"])),
                code_result=(
                    None
                    if result is None
                    else (json.loads(result) if isinstance(result, str) else dict(result))
                ),
                started_at=cast(datetime, r["created_at"]),
            )
        )
    return out
