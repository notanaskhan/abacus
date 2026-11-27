"""Red paths for amendments (T-08-T33; TASK-9006; SPEC-710 AC6.3, AC6.5, AC6.6; BH-TAX-02;
INV-1; DEC-6012; red).

- **Eligibility** (`tax/approval.py`'s final approval, through its blocker slot): an amendment's
  return is approved like any return, by BH-TAX-02's signer for the client, a live person at
  level 4 (the five layers: the matrix, the route, `_human`, `function_in(signer)`, the
  database's human-only CHECK). Its own blockers: an amended return needs its Part II
  explanation (`amendment_explanation_missing`); an AAR needs its BBA election decided
  (`bba_election_undecided`).
- **The `amendment_approval` gate** (HOME-02): met when every amendment on the engagement is
  approved or further on.
- **`bba_election`** (C3 decision kind, reserved to the **signer**): the two routes, "Pay the
  imputed underpayment" or "Push out to the reviewed-year partners", with the imputed underpayment
  from the AAR's engine import (`aar.imputed_underpayment`; T-08-T36 adds the labelled shadow
  tie-out) and the adjustments' total, computed by code (ADR-050). The decision's applier writes
  the insert-only `aar_elections` row in the decider's unit of work; the CHECK holds it human.
  The agent may recommend a route (T-08-T34's `bba_route`), never decide it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import (
    AppliedDecision,
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
)
from abacus.modules.tax.approval import BLOCKER_WORDS, Blocker

ELECTION_KIND: Final = "bba_election"
GATE_KIND: Final = "amendment_approval"
IU_KEY: Final = "aar.imputed_underpayment"
ROUTES: Final = (
    ("pay_imputed_underpayment", "Pay the imputed underpayment"),
    ("push_out", "Push out to the reviewed-year partners"),
)
BLOCKER_WORDS.update(
    {
        "amendment_explanation_missing": "The amendment's Part II explanation is not written.",
        "bba_election_undecided": "The signing partner has not decided the BBA election.",
    }
)


class ImputedUnderpaymentUnavailable(DomainConflict):
    code = "imputed_underpayment_unavailable"


def question_key(amendment_id: UUID) -> str:
    """C3 question keys are `[a-z][a-z0-9_.]`: the AAR's id goes in as hex."""
    return f"aar.election.{amendment_id.hex}"


# --- eligibility ---------------------------------------------------------------------------------

_OF_RETURN: Final = text(
    "SELECT a.id, a.kind, (SELECT count(*) FROM amendment_explanation_versions v "
    "WHERE v.amendment_id = a.id) AS explained, (SELECT count(*) FROM aar_elections e "
    "WHERE e.amendment_id = a.id) AS elected FROM amendments a WHERE a.work_item_id = :w"
)


async def amendment_blockers(tenant: TenantContext, return_id: UUID) -> list[Blocker]:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_OF_RETURN, {"w": return_id})).first()
    if row is None:
        return []  # not an amendment's return
    if row.kind == "amended_return" and not row.explained:
        return [Blocker("amendment_explanation_missing", cast(UUID, row.id))]
    if row.kind == "bba_aar" and not row.elected:
        return [Blocker("bba_election_undecided", cast(UUID, row.id))]
    return []


_STATUSES: Final = text(
    "SELECT t.status FROM amendments a JOIN tax_returns t ON t.work_item_id = a.work_item_id "
    "WHERE a.engagement_id = :e"
)
_DONE: Final = frozenset({"approved", "awaiting_signature", "filed", "accepted"})


async def amendment_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        found = [str(r[0]) for r in await session.execute(_STATUSES, {"e": engagement_id})]
    return bool(found) and all(s in _DONE for s in found)


# --- the BBA election ----------------------------------------------------------------------------

_AAR: Final = text(
    "SELECT a.id, a.kind, a.work_item_id, (SELECT coalesce(sum(amount), 0) FROM aar_adjustments "
    "j WHERE j.amendment_id = a.id) AS adjustments FROM amendments a WHERE a.id = :a"
)
_SUMMARY: Final = text(
    "SELECT lines FROM return_engine_summaries WHERE work_item_id = :w AND kind <> 'pro_forma' "
    "ORDER BY approved_at DESC LIMIT 1"
)


def _amendment_of(subject: CardSubject) -> UUID:
    prefix = "aar.election."
    if not subject.question_key.startswith(prefix):
        raise NotFound("amendment")
    return UUID(hex=subject.question_key.removeprefix(prefix))


async def election_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The two routes and their figures, by code: the AAR's adjustments total and the imputed
    underpayment the engine computed (no rate is ever applied here)."""
    from abacus.modules.tax.amendments import amounts

    amendment_id = _amendment_of(subject)
    async with tenant_session(tenant) as session:
        row = (await session.execute(_AAR, {"a": amendment_id})).first()
        lines = None if row is None else await session.scalar(_SUMMARY, {"w": row.work_item_id})
    if row is None or row.kind != "bba_aar":
        raise NotFound("amendment")
    iu = amounts(lines).get(IU_KEY)
    if iu is None:
        raise ImputedUnderpaymentUnavailable(facts={"amendment": str(amendment_id)})
    figures = {
        "imputed_underpayment": f"{iu:.2f}",
        "adjustments": f"{Decimal(row.adjustments):.2f}",
        "iu_source": "engine",
    }
    return ComputedCard(
        options=tuple(CardOption(key, label, figures) for key, label in ROUTES),
        context=(
            CardContext("adjustments", "Adjustments (reviewed year)", figures["adjustments"]),
            CardContext(
                "imputed_underpayment", "Imputed underpayment", figures["imputed_underpayment"]
            ),
        ),
    )


_ELECT: Final = text(
    "INSERT INTO aar_elections (tenant_id, amendment_id, decision_id, route, "
    "imputed_underpayment, iu_source, decided_by) VALUES (:t, :a, :d, :route, :iu, :src, :by)"
)


async def apply_election(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    """The signer's decision becomes the AAR's election, in the decider's unit of work."""
    if decided.option_key not in dict(ROUTES):
        raise NotFound("route")
    amendment_id = UUID(hex=decided.question_key.removeprefix("aar.election."))
    await tx.session.execute(
        _ELECT,
        {"t": ctx.tenant_id, "a": amendment_id, "d": decided.decision_id,
         "route": decided.option_key, "iu": Decimal(decided.figures["imputed_underpayment"]),
         "src": decided.figures.get("iu_source", "engine"), "by": ctx.user_id},
    )  # fmt: skip
    tx.record(
        "aar.elected",
        target=Target("amendment", amendment_id),
        after=Ref(decision=decided.decision_id),
        scope=Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id),
    )


async def raise_election(ctx: AuthContext, amendment_id: UUID) -> UUID:
    """The election's card on the AAR, reserved to the client's signer (BH-TAX-02)."""
    from abacus.modules.review.api import raise_decision_card
    from abacus.modules.tax.approval import signer_for

    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT a.engagement_id, a.work_item_id, e.client_id FROM amendments a "
                    "JOIN engagements e ON e.id = a.engagement_id WHERE a.id = :a "
                    "AND a.kind = 'bba_aar'"
                ),
                {"a": amendment_id},
            )
        ).first()
    if row is None:
        raise NotFound("amendment")
    signer = await signer_for(ctx.tenant_id, cast(UUID, row.client_id))
    if signer is None:
        raise NotFound("signer")
    return await raise_decision_card(
        ctx,
        engagement_id=row.engagement_id,
        kind=ELECTION_KIND,
        question_key=question_key(amendment_id),
        work_item_id=row.work_item_id,
        reserved_user_id=signer,
        raised_under="aar.create",  # the AAR's own action (DEC-2392), partner or manager
    )


def register() -> None:
    from abacus.modules.review.api import DecisionKind, register_decision_kind, register_gate_kind
    from abacus.modules.tax.approval import register_final_approval_blocker

    register_final_approval_blocker("amendment", amendment_blockers)
    register_gate_kind(GATE_KIND, amendment_gate)
    register_decision_kind(
        DecisionKind(
            code=ELECTION_KIND,
            reserved_role="signer",
            options=election_card,
            apply=apply_election,
        )
    )


__all__ = [
    "ELECTION_KIND",
    "GATE_KIND",
    "ImputedUnderpaymentUnavailable",
    "amendment_blockers",
    "amendment_gate",
    "apply_election",
    "election_card",
    "question_key",
    "raise_election",
    "register",
]
