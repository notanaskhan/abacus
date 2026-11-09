"""A-07's code-only Accrued Agent capabilities (A-07-T32; A-07 §6, F10; DEC-3109). PROTECTED.

Five capabilities, no model call: each runs code, then records an agent run on the v1 recording
path (`agents.api.record_code_run`) so the P-09 dock shows ToolCards and a narration rendered from
a template as AgentBlocks. Every figure in the narration is a fact code computed; nothing here
decides, approves, sends, signs, locks or concludes (the plan check refuses a reserved verb), and
the writes are drafts, digest snapshots, binder indexes or suggestions only, attributed
"<initiator> via Agent" (INV-5).

| Capability | Run | Writes |
|---|---|---|
| `audit.eqr_digest` | AUD-18 d "Assemble judgments digest" | `eqr_digest_cards` snapshots |
| `audit.completion_readiness` (#4231) | AUD-19 checks | narration only |
| `audit.bring_down` (#4240) | AUD-24 "no new events" | reconfirmation requests (the activity) |
| `audit.letter_compose` | AUD-21 f, AUD-22 Regenerate | draft versions |
| `audit.archive_readiness` (#4302) | AUD-25 dock | `archive_binder_indexes` |
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import uow
from abacus.modules.agents.api import CodeRun, CodeStep, record_code_run
from abacus.modules.agents.blocks import Fact
from abacus.modules.agents.code_runs import blocks, fact, text_part, txt
from abacus.modules.assurance.release import AlsoRequired, register_also_required
from abacus.modules.engagements.api import assurance_item, engagement_type_of, get_ref
from abacus.modules.identity.api import AuthContext, authorise, team_of

EQR_DIGEST: Final = "audit.eqr_digest"
COMPLETION_READINESS: Final = "audit.completion_readiness"
BRING_DOWN: Final = "audit.bring_down"
LETTER_COMPOSE: Final = "audit.letter_compose"
ARCHIVE_READINESS: Final = "audit.archive_readiness"
CAPABILITIES: Final[tuple[str, ...]] = (
    EQR_DIGEST,
    COMPLETION_READINESS,
    BRING_DOWN,
    LETTER_COMPOSE,
    ARCHIVE_READINESS,
)


def _count(fact_id: str, value: int, basis: str) -> Fact:
    return Fact(id=fact_id, kind="count", value=str(value), basis=basis)


async def _record(tenant: TenantContext, run: CodeRun) -> UUID:
    async with uow(tenant) as tx:
        return await record_code_run(tx, tenant.tenant_id, run)


# --- audit.eqr_digest ----------------------------------------------------------------------------


async def eqr_digest(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """Build the digest (code; `eqr.build_digest` authorised by the service), then record the
    run: "I assembled the decided judgments. I have not evaluated them." The EQR reviews."""
    from abacus.modules.assurance import eqr_service

    found = await assurance_item(ctx.tenant, work_item_id)
    built = await eqr_service.build_digest(ctx, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        cards = int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM eqr_digest_cards WHERE work_item_id = :wi "
                    "AND superseded_by IS NULL"
                ),
                {"wi": work_item_id},
            )
            or 0
        )
    facts = {
        "cards": _count("cards", cards, "eqr_digest_cards current"),
        "built": _count("built", built, "cards new or changed this run"),
    }
    return await _record(
        ctx.tenant,
        CodeRun(
            agent_id=EQR_DIGEST,
            engagement_id=found.engagement_id,
            initiator_user_id=ctx.user_id,
            task_scope=("eqr.build_digest", "decision_card.read"),
            steps=(CodeStep("eqr.assemble_digest", "Assemble judgments digest", cards),),
            narration=blocks(
                text_part(
                    txt("I assembled "),
                    fact("cards"),
                    txt(" decided judgments into the digest, "),
                    fact("built"),
                    txt(" of them new or changed. I have not evaluated them."),
                )
            ),
            facts=facts,
            output={"cards": cards, "built": built},
            work_item_id=work_item_id,
        ),
    )


# --- audit.completion_readiness (#4231) ----------------------------------------------------------


async def completion_readiness(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """Check sign-offs, review notes and (EBP) the draft Form 5500's tie-out; narration only."""
    from abacus.modules.assurance import gates as gate_providers

    found = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, found.engagement_id)
    await authorise(ctx, "completion.check_readiness", ref.resource())
    blockers = await gate_providers.g5_blockers(ctx.tenant, found.engagement_id)
    unsigned = sum(1 for b in blockers if b.startswith("unsigned:"))
    notes = sum(1 for b in blockers if b.startswith("review_note:"))
    steps = [
        CodeStep("completion.check_sign_offs", "Check workpaper sign-offs", unsigned),
        CodeStep("completion.check_review_notes", "Check review notes", notes),
    ]
    if await engagement_type_of(ctx.tenant, found.engagement_id) == "ebp_audit":
        steps.append(CodeStep("ebp.read_tie_out", "Read draft Form 5500 for consistency"))
    return await _record(
        ctx.tenant,
        CodeRun(
            agent_id=COMPLETION_READINESS,
            engagement_id=found.engagement_id,
            initiator_user_id=ctx.user_id,
            task_scope=("completion.read", "review_note.read"),
            steps=tuple(steps),
            narration=blocks(
                text_part(
                    fact("unsigned"),
                    txt(" sign-offs are still to come and "),
                    fact("notes"),
                    txt(" review notes are open. The judgment items stay with the team."),
                )
            ),
            facts={
                "unsigned": _count("unsigned", unsigned, "required levels without a sign-off"),
                "notes": _count("notes", notes, "open review notes"),
            },
            output={"unsigned": unsigned, "notes": notes},
            work_item_id=work_item_id,
        ),
    )


# --- audit.bring_down (#4240) --------------------------------------------------------------------


async def record_bring_down(
    tenant: TenantContext,
    work_item_id: UUID,
    engagement_id: UUID,
    *,
    procedures: int,
    performed: int,
    reconfirmations: int,
) -> UUID | None:
    """After the bring-down activity: the run, as the engagement partner via Agent (the timer has
    no person; the EP set the report date). None when the engagement has no EP."""
    partners = [
        m
        for m, role in await team_of(tenant.tenant_id, engagement_id)
        if role == "engagement_partner"
    ]
    if not partners:
        return None
    acting = TenantContext(
        tenant.tenant_id, "system", "bring_down", on_behalf_of_user_id=partners[0]
    )
    return await _record(
        acting,
        CodeRun(
            agent_id=BRING_DOWN,
            engagement_id=engagement_id,
            initiator_user_id=partners[0],
            task_scope=("procedure.read", "independence.request"),
            steps=(
                CodeStep("completion.refresh_procedures", "Refresh procedures", procedures),
                CodeStep(
                    "independence.request_reconfirmation",
                    "Request independence reconfirmations",
                    reconfirmations,
                ),
            ),
            narration=blocks(
                text_part(
                    fact("performed"),
                    txt(" of "),
                    fact("procedures"),
                    txt(" procedures are performed through the report date, and "),
                    fact("requests"),
                    txt(" people were asked to reconfirm independence."),
                )
            ),
            facts={
                "performed": _count("performed", performed, "procedures through the report date"),
                "procedures": _count("procedures", procedures, "procedures on the work item"),
                "requests": _count("requests", reconfirmations, "reconfirmation requests"),
            },
            output={"procedures": procedures, "performed": performed},
            work_item_id=work_item_id,
        ),
    )


async def bring_down_item(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> AlsoRequired:
    """AUD-24's also-required "bring-down": a completed `audit.bring_down` run on the engagement
    (A-07-T30's slot; DEC-3109)."""
    del work_item_id
    async with tenant_session(tenant) as session:
        at = await session.scalar(
            text(
                "SELECT max(finished_at) FROM agent_runs WHERE engagement_id = :e "
                "AND agent_id = :a AND status = 'completed'"
            ),
            {"e": engagement_id, "a": BRING_DOWN},
        )
    return AlsoRequired("bring_down", at is not None, None if at is None else at.isoformat())


# --- audit.letter_compose ------------------------------------------------------------------------


async def letter_compose(
    ctx: AuthContext, work_item_id: UUID, *, communication_id: UUID | None = None
) -> UUID:
    """Compose the representation letter's next draft, or regenerate one governance letter, then
    record the run. Drafts only: a manager edits, the EP approves, a person sends."""
    from abacus.modules.assurance import governance_comms as gc
    from abacus.modules.assurance import rep_letters

    found = await assurance_item(ctx.tenant, work_item_id)
    if communication_id is None:
        version = await rep_letters.start_letter(ctx, work_item_id)
        label, kind = "Compose representation letter", "rep_letter"
        drafted = getattr(version, "version_no", 1)
    else:
        await gc.regenerate(ctx, work_item_id, communication_id)
        label, kind = "Regenerate governance letter", "governance_letter"
        drafted = 1
    return await _record(
        ctx.tenant,
        CodeRun(
            agent_id=LETTER_COMPOSE,
            engagement_id=found.engagement_id,
            initiator_user_id=ctx.user_id,
            task_scope=("rep_letter.draft", "governance_comm.draft"),
            steps=(CodeStep(f"{kind}.compose_draft", label),),
            narration=blocks(
                text_part(
                    txt("I composed draft "),
                    fact("version"),
                    txt(" from the firm's template and the file's facts. A person edits it, "),
                    txt("the engagement partner decides on it."),
                )
            ),
            facts={"version": _count("version", int(drafted), "the draft's version number")},
            output={"kind": kind},
            work_item_id=work_item_id,
        ),
    )


# --- audit.archive_readiness (#4302) -------------------------------------------------------------


async def archive_readiness(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """Build the binder index (code), then record the run with the section counts."""
    from abacus.modules.assurance import archive_gate as ag

    found = await assurance_item(ctx.tenant, work_item_id)
    version = await ag.build_binder_index(ctx, work_item_id)
    state = await ag.archive_state(ctx.tenant, work_item_id)
    papers = sum(b.workpapers for b in state.binder)
    documents = sum(b.source_documents for b in state.binder)
    runs = sum(b.run_logs for b in state.binder)
    return await _record(
        ctx.tenant,
        CodeRun(
            agent_id=ARCHIVE_READINESS,
            engagement_id=found.engagement_id,
            initiator_user_id=ctx.user_id,
            task_scope=("archive.build_index", "evidence.read"),
            steps=(
                CodeStep("archive.build_index", "Build the binder index", papers + documents),
                CodeStep("archive.check_items", "Check the nine items", len(state.items)),
            ),
            narration=blocks(
                text_part(
                    txt("The binder index lists "),
                    fact("papers"),
                    txt(" workpapers, "),
                    fact("documents"),
                    txt(" source documents and "),
                    fact("runs"),
                    txt(" run logs; "),
                    fact("done"),
                    txt(" of "),
                    fact("total"),
                    txt(" items hold. The lock stays with the manager or the partner."),
                )
            ),
            facts={
                "papers": _count("papers", papers, "binder sections A to E"),
                "documents": _count("documents", documents, "binder section F"),
                "runs": _count("runs", runs, "binder section G"),
                "done": _count("done", state.done, "archive items met"),
                "total": _count("total", len(state.items), "archive items"),
            },
            output={"index_version": version},
            work_item_id=work_item_id,
        ),
    )


def register() -> None:
    """At import (assurance/api.py): the bring-down's also-required provider."""
    register_also_required("bring_down", bring_down_item)


__all__ = [
    "CAPABILITIES",
    "archive_readiness",
    "completion_readiness",
    "eqr_digest",
    "letter_compose",
    "record_bring_down",
]
