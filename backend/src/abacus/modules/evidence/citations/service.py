"""Writing citations: verified by code, then recorded, inside the writer's unit of work
(P-03-T06; ADR-166 §§1-4, ADR-007; DEC-218). PROTECTED.

`record_citations(tx, anchor=..., claims=..., run_id=...)` verifies every claim with its kind's
registered verifier and writes one insert-only `citations` row each, numbered in the anchor's
stack, with a `citation.created` audit event (ids only). A claim that fails is still written,
`verified=false` with its reason: every reader shows it "Unverified", never as fact. The quote is
never stored: only the hash of the words it resolved to.

Who wrote it comes from the transaction itself, never from the caller: a person's transaction
writes `human` rows with their user id, an agent's writes `agent` rows (and must name its run),
the system's writes `system` rows. Agents call this from their handoff unit of work (P-03-T10).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import transaction_context
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.evidence.citations import verifiers as _builtin  # registers the built-ins
from abacus.modules.evidence.citations.registry import (
    KINDS,
    Anchor,
    CitationClaim,
    Verdict,
    citable,
    unverifiable,
)
from abacus.modules.evidence.repository import insert_citation, next_citation_n

_ = _builtin
MAX_CLAIMS = 200


@dataclass(frozen=True)
class RecordedCitation:
    id: UUID
    n: int
    kind: str
    verified: bool
    verification_reason: str | None
    match_id: str | None


async def verify_claim(tx: UnitOfWork, claim: CitationClaim, anchor: Anchor) -> Verdict:
    """The claim's verdict by its kind's verifier, or `locator_invalid` without one."""
    found = citable(claim.kind)
    if found is None:
        return unverifiable(claim)
    return await found.verifier(tx, claim, anchor)


def _creator(actor_kind: str, actor_id: str, run_id: UUID | None) -> dict[str, object]:
    if actor_kind == "human":
        return {"created_by_kind": "human", "created_by_user_id": UUID(actor_id)}
    if actor_kind == "agent":
        if run_id is None:
            raise ValueError("an agent's citations name its run")
        return {"created_by_kind": "agent", "created_by_run_id": run_id}
    return {"created_by_kind": "system", "created_by_run_id": run_id}


async def record_citations(
    tx: UnitOfWork,
    *,
    anchor: Anchor,
    claims: Sequence[CitationClaim],
    run_id: UUID | None = None,
    on_behalf_of_user_id: UUID | None = None,
) -> list[RecordedCitation]:
    """Verify and write `claims` for `anchor`, in order; returns each row's outcome."""
    if len(claims) > MAX_CLAIMS:
        raise ValueError(f"at most {MAX_CLAIMS} citations at once")
    unknown = sorted({c.kind for c in claims} - KINDS)
    if unknown:
        raise ValueError(f"not citation kinds: {', '.join(unknown)}")
    context = await transaction_context(tx.session)
    creator = _creator(context.actor_kind, context.actor_id, run_id)
    if on_behalf_of_user_id is None:  # the person an agent or the platform acts for (0108)
        behalf = (
            await tx.session.execute(text("SELECT current_setting('app.on_behalf_of', true)"))
        ).scalar_one_or_none()
        on_behalf_of_user_id = UUID(str(behalf)) if behalf else None
    n = await next_citation_n(tx.session, anchor.type, anchor.id)
    recorded: list[RecordedCitation] = []
    for claim in claims:
        verdict = await verify_claim(tx, claim, anchor)
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
            "on_behalf_of_user_id": on_behalf_of_user_id,
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
