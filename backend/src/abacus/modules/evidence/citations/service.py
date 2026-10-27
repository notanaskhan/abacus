"""Writing citations: verified by code, then recorded, inside the writer's unit of work
(P-03-T06; ADR-166 §§1-4, ADR-007; DEC-218). PROTECTED.

`record_citations(tx, anchor=..., claims=..., run_id=...)` verifies every claim with its kind's
registered verifier and writes one insert-only `citations` row each, numbered in the anchor's
stack, with a `citation.created` audit event (ids only). A claim that fails is still written,
`verified=false` with its reason: every reader shows it "Unverified", never as fact. The quote is
never stored: only the hash of the words it resolved to.

Who wrote it comes from the acting principal, never from the caller's say-so, and that principal
must be the one the transaction acts as: a person writes `human` rows, an agent context `agent`
rows with its run and initiator, a system context `system` rows with its run. Every verifier
authorises that principal on the anchor's engagement before reading the source. Agents call this
from their handoff unit of work (P-03-T10).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import transaction_context
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.evidence.citations import ledger_line as _ledger_line  # A-02-T22
from abacus.modules.evidence.citations import verifiers as _builtin  # registers the built-ins
from abacus.modules.evidence.citations.matching import MAX_QUOTE
from abacus.modules.evidence.citations.registry import (
    KINDS,
    Anchor,
    CitationClaim,
    Verdict,
    citable,
    source_of,
    unverifiable,
)
from abacus.modules.evidence.repository import insert_citation, next_citation_n
from abacus.modules.identity.api import Actor, AgentContext, AuthContext

_ = (_builtin, _ledger_line)
MAX_CLAIMS = 200


@dataclass(frozen=True)
class RecordedCitation:
    id: UUID
    n: int
    kind: str
    verified: bool
    verification_reason: str | None
    match_id: str | None


async def verify_claim(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: Anchor
) -> Verdict:
    """The claim's verdict by its kind's verifier, or `locator_invalid` without one. A quote
    longer than `MAX_QUOTE` characters is never searched (`quote_not_found`)."""
    found = citable(claim.kind)
    if found is None:
        return unverifiable(claim)
    if claim.quote is not None and len(claim.quote) > MAX_QUOTE:
        source_type, source_id = source_of(claim)
        return Verdict("quote_not_found", source_type, source_id)
    return await found.verifier(tx, actor, claim, anchor)


def _creator(actor: Actor) -> dict[str, object]:
    """Who wrote the rows, from the acting principal (never from the caller's say-so)."""
    if isinstance(actor, AuthContext):
        return {"created_by_kind": "human", "created_by_user_id": actor.user_id}
    if isinstance(actor, AgentContext):
        return {
            "created_by_kind": "agent",
            "created_by_run_id": actor.agent_run_id,
            "on_behalf_of_user_id": actor.initiator.user_id,
        }
    return {
        "created_by_kind": "system",
        "created_by_run_id": actor.run_id,
        "on_behalf_of_user_id": actor.on_behalf_of,
    }


async def record_citations(
    tx: UnitOfWork,
    *,
    actor: Actor,
    anchor: Anchor,
    claims: Sequence[CitationClaim],
    shadow: bool = False,
) -> list[RecordedCitation]:
    """Verify and write `claims` for `anchor`, in order, as `actor` (whose transaction `tx`
    is: the same firm and actor); returns each row's outcome. Each verifier authorises `actor`
    on the anchor's engagement before reading the cited source. `shadow`: an agent run that
    started in shadow (SPEC-036 AC-5); its rows are never shown. Only an agent writes them."""
    if shadow and not isinstance(actor, AgentContext):
        raise ValueError("only an agent run writes shadow citations")
    if len(claims) > MAX_CLAIMS:
        raise ValueError(f"at most {MAX_CLAIMS} citations at once")
    unknown = sorted({c.kind for c in claims} - KINDS)
    if unknown:
        raise ValueError(f"not citation kinds: {', '.join(unknown)}")
    context = await transaction_context(tx.session)
    acting = actor.tenant
    if (context.tenant_id, context.actor_kind, context.actor_id) != (
        acting.tenant_id,
        acting.actor_kind,
        acting.actor_id,
    ):
        raise ValueError("the actor is not the one this transaction acts as")
    creator = _creator(actor)
    n = await next_citation_n(tx.session, anchor.type, anchor.id)
    recorded: list[RecordedCitation] = []
    for claim in claims:
        verdict = await verify_claim(tx, actor, claim, anchor)
        registered = citable(claim.kind)
        values: dict[str, object] = {
            "tenant_id": context.tenant_id,
            "engagement_id": anchor.engagement_id,
            "work_item_id": anchor.work_item_id,
            "client_id": anchor.client_id,
            "cited_from_type": anchor.type,
            "cited_from_id": anchor.id,
            "cited_from_ref": anchor.ref,
            "cited_from_locator": dict(anchor.locator) if anchor.locator is not None else None,
            "n": n,
            "kind": claim.kind,
            "source_type": verdict.source_type,
            "source_id": verdict.source_id,
            "source_version": verdict.source_version,
            "locator": verdict.locator,
            "match_id": verdict.match_id,
            "quote_sha256": verdict.quote_sha256,
            "value_text": verdict.value_text,
            "verified": verdict.verified,
            "verification_reason": verdict.reason,
            "verifier_version": registered.version if registered is not None else "none",
            "shadow": shadow,
            **creator,
        }
        citation_id = await insert_citation(tx.session, values)
        tx.record(
            "citation.created",
            target=Target("citation", citation_id),
            after=Ref(source=verdict.source_id, n=n, verified=int(verdict.verified)),
            scope=Scope(anchor.engagement_id, anchor.work_item_id),
        )
        recorded.append(
            RecordedCitation(
                citation_id, n, claim.kind, verdict.verified, verdict.reason, verdict.match_id
            )
        )
        n += 1
    return recorded
