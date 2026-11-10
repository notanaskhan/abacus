"""One `tax.return_drafter` run, as the agent (T-04-T25; `drafter.py` has the rules). PROTECTED.

`draft(agent, client_entity_id, tax_year)` runs the steps in order, each read and the proposal
through C17 (`agents.api.call_tool`, so C19's §7216 gate and the run's scope hold on every call):

1. `tax.read_return` (step 1): `consent_required` → the run waits on `consent_7216`, no model call.
2. `tax.list_documents` (step 2), then each document's boxes (`evidence.api.extracted_fields_of`,
   code; the documents are the return's, read under the run's gate just passed).
3. `tax.read_worksheet` per worksheet of code's set that exists (steps 3…), for its fields.
4. The model's judgment of TSJ and notes (`tax.return_drafter@v1`), dropped for code's defaults
   where it strays; a refused gateway call leaves code's defaults (the draft still proposes).
5. Box citations verified and written as the agent (`evidence.api.record_citations`), on each
   target field's own `field` anchor; an unverified one is a gap, never a proposed row.
6. `tax.propose_field_changes` (one proposal), the self-check issues on the return
   (`review.api.create_issue`, the agent's task scope), and the Proposed checkpoint "Initial
   draft" naming the proposal (`review.api.propose_checkpoint`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
from abacus.ai_gateway.context import DataSubject
from abacus.kernel.uow import uow
from abacus.modules.agents.api import ToolCallIn, call_tool, spec_v2
from abacus.modules.evidence.api import CitationAnchor, extracted_fields_of, record_citations
from abacus.modules.identity.api import AgentContext
from abacus.modules.review.api import ProposedChange, create_issue, propose_checkpoint
from abacus.modules.tax.drafter import (
    CHECKPOINT_NAME,
    DRAFTER,
    Box,
    DraftResult,
    Gap,
    Mapped,
    ReturnDraftJudgment,
    TargetField,
    WorksheetPlan,
    as_money,
    draft_hash,
    judged_set,
    map_boxes,
    worksheet_set,
)
from abacus.modules.tax.form_line_citations import box_claim

FIELD_ANCHOR: Final = "field"  # the field's own citing record (review's `field` target)
# The self-check issues' fixed wording (code, never model text): kind, priority, title.
_ISSUES: Final[Mapping[str, tuple[str, str, str]]] = {
    "box_18a_state": (
        "missing_information",
        "medium",
        "K-1 box 18A tax-exempt interest: confirm the obligations' state for IT-201 line 20",
    ),
    "box_unmapped": ("review_point", "medium", "A document box has no field on this return"),
    "box_low_confidence": ("review_point", "low", "A document box was read with low confidence"),
    "citation_unverified": (
        "review_point",
        "medium",
        "A box value could not be verified on its page; it was not proposed",
    ),
}


class _Steps:
    """The run's C17 step numbers (each call its own idempotency key)."""

    def __init__(self) -> None:
        self.seq = 0

    def next(self) -> int:
        self.seq += 1
        return self.seq


async def _tool(agent: AgentContext, steps: _Steps, name: str, arguments: dict[str, object]):  # noqa: ANN202 -- ToolOutcome
    return await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id,
            step_seq=steps.next(),
            attempt=1,
            name=name,
            arguments=arguments,
        ),
    )


async def _judge(
    agent: AgentContext, client_entity_id: UUID, tax_year: int, offered: Sequence[str]
) -> ReturnDraftJudgment | None:
    spec = spec_v2(DRAFTER)
    context = (
        ContextBuilder()
        .task({"worksheets": list(offered), "tax_year": tax_year, "tsj": ["T", "S", "J"]})
        .subjects(DataSubject(client_entity_id, tax_year))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=ReturnDraftJudgment,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, DRAFTER, agent.agent_run_id
                ),
                context=context,
                work_class=spec.work_class,
                essential=spec.essential,
                routes=spec.routes,
                cheaper_tiers=spec.cheaper_tiers,
                max_output_tokens=spec.limits.max_output_tokens,
                timeout_seconds=spec.limits.max_seconds,
            )
        )
    except Exception:  # a refused gateway call (consent, terms, budget): code's defaults stand
        return None
    return result.output


async def _cite(
    agent: AgentContext, mapped: Sequence[Mapped]
) -> tuple[list[tuple[Mapped, UUID]], list[Gap]]:
    kept: list[tuple[Mapped, UUID]] = []
    gaps: list[Gap] = []
    async with uow(agent.tenant) as tx:
        for m in mapped:
            [recorded] = await record_citations(
                tx,
                actor=agent,
                anchor=CitationAnchor(
                    type=FIELD_ANCHOR,
                    id=m.target.field_id,
                    ref=m.target.field_key,
                    engagement_id=agent.engagement_id,
                ),
                claims=[
                    box_claim(
                        m.box.evidence_version_id, m.box.page_no, m.box.bbox, m.box.value_text
                    )
                ],
            )
            if recorded.verified:
                kept.append((m, recorded.id))
            else:
                gaps.append(Gap("citation_unverified", m.box.field_key, m.box.evidence_version_id))
    return kept, gaps


async def draft(agent: AgentContext, client_entity_id: UUID, tax_year: int) -> DraftResult:
    """The run's steps (module docstring). The caller has the run in a v2 state."""
    steps = _Steps()
    taxpayer: dict[str, object] = {"client_entity_id": str(client_entity_id), "tax_year": tax_year}
    read = await _tool(agent, steps, "tax.read_return", taxpayer)
    if not read.ok:
        if read.code == "consent_required":
            return DraftResult("waiting_on_inputs", needs=("consent_7216",), code=read.code)
        return DraftResult("refused", code=read.code)
    tax_return = cast(dict[str, object], read.result)
    return_id = UUID(str(tax_return["id"]))
    docs = await _tool(agent, steps, "tax.list_documents", taxpayer)
    if not docs.ok:
        return DraftResult("refused", code=docs.code)
    boxes: list[Box] = []
    for doc in cast(list[dict[str, object]], cast(dict[str, object], docs.result)["documents"]):
        version = UUID(str(doc["id"]))
        for f in await extracted_fields_of(agent.tenant, version):
            boxes.append(
                Box(
                    f.id,
                    version,
                    f.form_type,
                    f.field_key,
                    f.value_text,
                    f.page_no,
                    f.bbox,
                    f.low_confidence,
                )
            )
    offered = worksheet_set(boxes)
    fields: dict[tuple[str, str], TargetField] = {}
    for key in offered:
        sheet = await _tool(agent, steps, "tax.read_worksheet", {**taxpayer, "worksheet_key": key})
        if not sheet.ok:
            continue  # a worksheet the return does not have yet (proposed in the set, no fields)
        body = cast(dict[str, object], sheet.result)
        worksheet_id = UUID(str(body["worksheet_id"]))
        for row in cast(list[dict[str, object]], body["fields"]):
            fields[(key, str(row["field_key"]))] = TargetField(
                key,
                worksheet_id,
                UUID(str(row["id"])),
                str(row["field_key"]),
                as_money(row.get("value")),
                str(row.get("derivation") or "input"),
            )
    plans: tuple[WorksheetPlan, ...] = judged_set(
        offered, "J", await _judge(agent, client_entity_id, tax_year, offered)
    )
    mapped = map_boxes(tax_year, boxes, fields)
    kept, unverified = await _cite(agent, mapped.changes)
    gaps = (*mapped.gaps, *unverified)
    issue_ids = [
        await create_issue(
            agent,
            record_type="tax_return",
            record_id=return_id,
            kind=_ISSUES[g.code][0],
            priority=_ISSUES[g.code][1],
            title=_ISSUES[g.code][2],
            internal_note=None,
            client_wording=None,
            client_contact_id=None,
            assignee_user_id=None,
            assignee_agent=False,
            blocks=(),
            source_ref=f"drafter:{g.code}:{g.field_key}:{g.evidence_version_id}",
        )
        for g in gaps
    ]
    if not kept:
        return DraftResult(
            "nothing_to_propose", worksheets=plans, gaps=gaps, issue_ids=tuple(issue_ids)
        )
    proposed = await _tool(
        agent,
        steps,
        "tax.propose_field_changes",
        {
            **taxpayer,
            "changes": [
                {
                    "worksheet_id": str(m.target.worksheet_id),
                    "field_key": m.target.field_key,
                    "after": str(m.value),
                    "citation_ids": [str(cid)],
                }
                for m, cid in kept
            ],
        },
    )
    if not proposed.ok:
        return DraftResult("refused", code=proposed.code, gaps=gaps, issue_ids=tuple(issue_ids))
    proposal_id = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    checkpoint_id = await propose_checkpoint(
        agent,
        "tax_return",
        return_id,
        [
            ProposedChange(
                field_key=m.target.field_key,
                old=None
                if m.target.current is None
                else {"t": "decimal", "v": str(m.target.current)},
                new={"t": "decimal", "v": str(m.value)},
                cause="agent_run",
                citation_ids=(cid,),
                delta_facts={m.target.field_key: str(m.value - (m.target.current or Decimal(0)))},
            )
            for m, cid in kept
        ],
        author_kind="agent",
        cause="agent_run",
        content_hash=draft_hash([m for m, _ in kept]),
        proposal_id=proposal_id,
        name=CHECKPOINT_NAME,
    )
    return DraftResult(
        "proposed",
        proposal_id=proposal_id,
        checkpoint_id=checkpoint_id,
        worksheets=plans,
        changes=len(kept),
        gaps=gaps,
        issue_ids=tuple(issue_ids),
    )


__all__ = ["draft"]
