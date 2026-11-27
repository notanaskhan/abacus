"""`tax.return_drafter` mode `amendment` and `decisions.recommender` mode `bba_route` (T-08-T34;
TASK-9007; SPEC-710 AC6.2, AC6.6; ADR-005, ADR-050, ADR-052, ADR-167; DEC-6013). Red zone (an
agent path). Synthetic tenants only until a Bedrock report clears them (DEC-5901, DEC-6001).

Code computes, the model writes words, a person decides. Neither path records an election,
approves, files or touches the original return.

- **amendment** (TAX-16 "Draft with Agent…", `amendment.edit`, a person): code's amendment lines
  (`compute.amendment`: as filed, as amended and the change per line, the total change and the
  refund or balance) are the model's facts; the engagement's documents (masked pages) are its
  untrusted sources, the post-filing evidence among them (the missed Form 1098). The model writes
  the Part II explanation as AgentBlocks (every figure a fact segment) and quotes at least one
  passage. Code settles it (`practice_modes.settle`), verifies each quote as a `document_text`
  citation, and writes (1) one suggestion (`amendment_explanation`, field `part_ii`) and the
  agent's Part II version naming it, and (2) a **proposed checkpoint** "Amendment draft" on the
  amendment's return of the changed lines (old: as filed, new: as amended, cause `amendment`)
  with the verified citations. Nothing changes until a person adopts the draft or approves the
  checkpoint. The §7216 consents (C19) are checked first: 409 `consent_7216_missing`.
- **bba_route** (TAX-16 e "Recommend a route…", `aar.create`): code's two routes and facts (the
  adjustments' total, the engine's imputed underpayment) go to `recommender_modes.recommend_mode`;
  code checks the answer (an offered key, every reason a fact, no claimed act). A checked answer
  becomes the agent's suggestion on the AAR's election and tags the `bba_election` card it raises
  for the signer; the signer still decides (`amendment_gates`). A refused answer raises the card
  untagged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.db import tenant_session
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AgentContext, AuthContext
from abacus.modules.tax import practice_modes as pm
from abacus.modules.tax.compute import amendment as calc

CAPABILITY: Final = "tax.return_drafter"
PROMPT: Final = "tax.return_drafter.amendment@v1"
PART_II_TARGET: Final = "amendment_explanation"
PART_II_FIELD: Final = "part_ii"
ELECTION_TARGET: Final = "aar_election"
CHECKPOINT_NAME: Final = "Amendment draft"


@dataclass(frozen=True)
class DraftRun:
    run_id: UUID
    started_at: datetime
    status: pm.Status
    reason: str | None = None
    checkpoint_id: UUID | None = None


def amendment_facts(found: calc.Amended) -> tuple[list[pm.SubjectIn], list[pm.FactIn]]:
    """Code's facts for Part II: each changed line's as-amended value and change (the change
    alone past five lines: a subject carries at most twelve facts), then the total change and the
    refund or balance (ids by position, never the line's digits)."""
    facts: list[pm.FactIn] = []
    letters = pm._LETTERS  # pyright: ignore[reportPrivateUsage] -- the sibling mode's id alphabet
    changed = [ln for ln in found.lines if ln.change != 0]
    brief = len(changed) > 5
    for n, line in enumerate(changed[:10]):
        tag = f"l{letters[n // 26]}{letters[n % 26]}"
        if not brief:
            facts.append(pm.FactIn(id=f"{tag}_amended", kind="money", value=str(line.as_amended),
                                   basis=f"{line.line_key} as amended"))  # fmt: skip
        facts.append(pm.FactIn(id=f"{tag}_change", kind="money", value=str(line.change),
                               basis=f"{line.line_key} change"))  # fmt: skip
    facts.append(pm.FactIn(id="total_change", kind="money", value=str(found.total_change),
                           basis="total tax change"))  # fmt: skip
    if found.refund_due is not None:
        facts.append(pm.FactIn(id="refund_due", kind="money", value=str(found.refund_due),
                               basis="refund due"))  # fmt: skip
    if found.balance_due is not None:
        facts.append(pm.FactIn(id="balance_due", kind="money", value=str(found.balance_due),
                               basis="balance due"))  # fmt: skip
    subject = pm.SubjectIn(
        key=PART_II_FIELD, label="Part II explanation of changes", fact_ids=[f.id for f in facts]
    )
    return [subject], facts


async def _answer(
    agent: AgentContext, given: pm.ModeInput, subjects: list[object]
) -> pm.ModeOutput:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    builder = ContextBuilder().task(given.model_dump(mode="json"), untrusted=("untrusted",))
    for subject in subjects:
        builder = builder.subjects(subject)  # pyright: ignore[reportArgumentType] -- DataSubject
    result = await call(
        GatewayCall(
            purpose=spec.purpose, prompt=PROMPT, tier=spec.tier, output_schema=pm.ModeOutput,
            budget_usd=spec.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement_id, CAPABILITY,
                                    agent.agent_run_id),
            context=builder.build(), work_class=spec.work_class, essential=spec.essential,
            routes=spec.routes, cheaper_tiers=spec.cheaper_tiers,
            max_output_tokens=spec.limits.max_output_tokens,
            timeout_seconds=spec.limits.max_seconds,
        )
    )  # fmt: skip
    return cast(pm.ModeOutput, result.output)


_AGENT_VERSION: Final = text(
    "INSERT INTO amendment_explanation_versions (tenant_id, amendment_id, version_no, text, "
    "author_kind, suggestion_id, created_by) VALUES (:t, :a, (SELECT coalesce(max(version_no), "
    "0) + 1 FROM amendment_explanation_versions WHERE amendment_id = :a), :text, 'agent', :s, "
    ":u) RETURNING version_no"
)


async def draft_amendment(ctx: AuthContext, amendment_id: UUID) -> DraftRun:
    """The module docstring's amendment mode."""
    from abacus.ai_gateway import DataSubject, is_synthetic
    from abacus.modules.agents.api import (
        create_suggestion,
        end_capability_run,
        start_capability_run,
        starts_in_shadow,
    )
    from abacus.modules.review.api import ProposedChange, propose_checkpoint
    from abacus.modules.tax import amendments
    from abacus.modules.tax.practice_tools_errors import Consent7216Missing

    found = await amendments.view(ctx, amendment_id, "federal")
    entity, year = await pm.return_subject(ctx.tenant, found.work_item_id)
    if not await pm._consented(ctx.tenant, entity, (year,)):  # pyright: ignore[reportPrivateUsage] -- the sibling mode's C19 check
        raise Consent7216Missing(facts={"client_entity_id": str(entity)})
    if not await is_synthetic(ctx.tenant):
        raise pm.AgentNotAvailable(facts={"capability": CAPABILITY})
    changed = [ln for ln in found.amended.lines if ln.change != 0]
    if not changed:
        raise pm.OutputRefused(facts={"reason": "nothing_changed"})
    engagement = await amendments.engagement_of(ctx.tenant, amendment_id)
    started = system_now()
    agent = await start_capability_run(ctx, CAPABILITY, engagement)
    if agent is None:
        raise pm.AgentNotAvailable(facts={"reason": "run_not_recorded"})
    async with tenant_session(agent.tenant) as session:
        shadow = bool(await starts_in_shadow(session, agent.tenant, CAPABILITY))
    sources = await pm._sources(ctx, engagement)  # pyright: ignore[reportPrivateUsage] -- the sibling mode's masked sources
    if not sources.given:
        await end_capability_run(agent, status="escalated", output={"reason": "no_sources"})
        return DraftRun(agent.agent_run_id, started, "escalated", "no_sources")
    subjects, facts = amendment_facts(found.amended)
    given = pm.ModeInput(mode="amendment", subjects=subjects, facts=facts,
                         sources=sources.given, untrusted=sources.untrusted)  # fmt: skip
    try:
        settled = pm.settle(given, await _answer(agent, given, [DataSubject(entity, year)]))
    except pm.OutputRefused as refused:
        reason = str((refused.facts or {}).get("reason"))[:60]
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return DraftRun(agent.agent_run_id, started, "escalated", reason)
    except Exception as exc:  # the boundary, budget or schema refused: DF-04
        reason = pm._reason(exc)  # pyright: ignore[reportPrivateUsage] -- the sibling mode's DF-04 code
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return DraftRun(agent.agent_run_id, started, "escalated", reason)
    part = settled[0]
    cites = await pm._verified(  # pyright: ignore[reportPrivateUsage] -- the sibling mode's citation check
        agent, PART_II_TARGET, amendment_id, PART_II_FIELD, part, sources.versions,
        shadow=shadow, work_item_id=found.work_item_id,
    )  # fmt: skip
    if cites is None:
        await end_capability_run(
            agent, status="escalated", output={"reason": "citation_unverified"}
        )
        return DraftRun(agent.agent_run_id, started, "escalated", "citation_unverified")
    if shadow:
        await end_capability_run(agent, status="succeeded", output={"suggestions": 0})
        return DraftRun(agent.agent_run_id, started, "shadow")
    body = pm.render(part.blocks, facts, limit=4000)
    suggestion = await create_suggestion(
        agent, engagement_id=engagement, target_type=PART_II_TARGET, target_id=amendment_id,
        field_key=PART_II_FIELD, proposed_value={"t": "text", "v": body},
        citation_ids=cites, rationale_ref=None,
    )  # fmt: skip
    async with uow(agent.tenant) as tx:
        version = await tx.session.scalar(
            _AGENT_VERSION,
            {"t": ctx.tenant_id, "a": amendment_id, "text": body, "s": suggestion,
             "u": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "amendment.explanation_proposed",
            target=Target("amendment", amendment_id),
            after=Ref(version=int(cast(int, version)), citations=len(cites)),
            scope=Scope(engagement_id=engagement, work_item_id=found.work_item_id),
        )
    changes = [
        ProposedChange(
            field_key=ln.line_key, old={"t": "decimal", "v": str(ln.as_filed)},
            new={"t": "decimal", "v": str(ln.as_amended)}, cause="amendment",
            citation_ids=tuple(cites), delta_facts={"change": str(ln.change)},
        )
        for ln in changed
    ]  # fmt: skip
    digest = json.dumps(sorted((c.field_key, str(c.new)) for c in changes))
    from hashlib import sha256

    checkpoint = await propose_checkpoint(
        agent, "tax_return", found.work_item_id, changes, author_kind="agent", cause="amendment",
        content_hash=sha256(digest.encode()).hexdigest(), name=CHECKPOINT_NAME,
    )  # fmt: skip
    await end_capability_run(agent, status="succeeded", output={"suggestions": 1})
    return DraftRun(agent.agent_run_id, started, "succeeded", None, checkpoint)


async def apply_part_ii(tx: object, ctx: AuthContext, value: object) -> None:
    """Adopting the draft is the person's own Part II version of it (insert-only)."""
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.agents.api import AdoptedValue
    from abacus.modules.tax import amendments

    adopted = cast(AdoptedValue, value)
    unit = cast(UnitOfWork, tx)
    await amendments.authorise_edit(ctx, adopted.target_id)
    body = str(adopted.value.get("v") or "")[:4000]
    version = await unit.session.scalar(
        text(
            "INSERT INTO amendment_explanation_versions (tenant_id, amendment_id, version_no, "
            "text, author_kind, created_by) VALUES (:t, :a, (SELECT coalesce(max(version_no), 0) "
            "+ 1 FROM amendment_explanation_versions WHERE amendment_id = :a), :text, 'human', "
            ":u) RETURNING version_no"
        ),
        {"t": ctx.tenant_id, "a": adopted.target_id, "text": body, "u": ctx.user_id},
    )
    unit.record(
        "amendment.explained",
        target=Target("amendment", adopted.target_id),
        after=Ref(version=int(cast(int, version)), adopted=1),
    )


# --- bba_route -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommended:
    card_id: UUID
    run_id: UUID | None
    started_at: datetime
    option_key: str | None


async def recommend_bba_route(ctx: AuthContext, amendment_id: UUID) -> Recommended:
    """The recommendation (when code accepts it) and the signer's card."""
    from abacus.ai_gateway import is_synthetic
    from abacus.modules.agents.api import (
        create_suggestion,
        end_capability_run,
        recommend_mode,
        start_capability_run,
    )
    from abacus.modules.agents.recommender_modes import attribution_for
    from abacus.modules.review.api import CardSubject
    from abacus.modules.tax import amendment_gates, amendments
    from abacus.modules.tax.recommendation_facts import bba_route_facts

    await amendments.authorise_edit(ctx, amendment_id, action="aar.create")
    engagement = await amendments.engagement_of(ctx.tenant, amendment_id)
    card = await amendment_gates.election_card(
        ctx.tenant,
        CardSubject(engagement, None, amendment_gates.question_key(amendment_id)),
    )
    figures = card.options[0].figures
    recommended: str | None = None
    suggestion: UUID | None = None
    run_id: UUID | None = None
    started = system_now()
    if await is_synthetic(ctx.tenant):
        agent = await start_capability_run(ctx, "decisions.recommender", engagement)
        if agent is not None:
            run_id = agent.agent_run_id
            outcome = await recommend_mode(
                attribution_for(agent.tenant, engagement, agent.agent_run_id),
                bba_route_facts(
                    Decimal(figures["adjustments"]), Decimal(figures["imputed_underpayment"])
                ),
            )
            if outcome.suggestion is not None:
                recommended = outcome.suggestion.recommended_option_key
                suggestion = await create_suggestion(
                    agent, engagement_id=engagement, target_type=ELECTION_TARGET,
                    target_id=amendment_id, field_key="route",
                    proposed_value={"t": "text", "v": recommended}, citation_ids=[],
                    rationale_ref=None,
                )  # fmt: skip
            await end_capability_run(
                agent,
                status="succeeded" if outcome.suggestion is not None else "escalated",
                output={"reason": outcome.refused or "recommended"},
            )
    card_id = await amendment_gates.raise_election(
        ctx, amendment_id, recommended_option_key=recommended,
        recommendation_suggestion_id=suggestion,
    )  # fmt: skip
    return Recommended(card_id, run_id, started, recommended)


async def apply_election_suggestion(tx: object, ctx: AuthContext, value: object) -> None:
    """Adopting the recommendation records only that it was read: the route is the signer's
    decision on the card (INV-1), never an adoption."""
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.agents.api import AdoptedValue

    adopted = cast(AdoptedValue, value)
    cast(UnitOfWork, tx).record(
        "aar.recommendation_read", target=Target("amendment", adopted.target_id)
    )


def register() -> None:
    from abacus.modules.agents.api import register_suggestion_applier
    from abacus.modules.tax import amendments

    register_suggestion_applier(
        PART_II_TARGET, apply_part_ii, engagement_of=amendments.engagement_of
    )
    register_suggestion_applier(
        ELECTION_TARGET, apply_election_suggestion, engagement_of=amendments.engagement_of
    )


__all__ = [
    "CAPABILITY",
    "CHECKPOINT_NAME",
    "PROMPT",
    "DraftRun",
    "Recommended",
    "amendment_facts",
    "apply_part_ii",
    "draft_amendment",
    "recommend_bba_route",
    "register",
]
