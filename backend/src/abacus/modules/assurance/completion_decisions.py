"""The A-06 decision kinds (A-06-T13; A-06 §3 F2, F5; AUD-15, AUD-16; DEC-2213).

Both are C3 decision cards reserved to the engagement partner, with options computed by code
(never a model: ADR-050) and the decision kind's fresh second factor; C3's decide route requires
the rationale (the card's own rule). The owner applies the decision in the decider's unit of
work (A-04 AC3.4):

- **`deficiency_severity`** (AU-C 265): Deficiency · Significant deficiency · Material weakness.
  Applying it concludes the deficiency with its severity, card and decision; the database's
  guard accepts a concluded severity only from the person's decision on that card (0644).
  Raised by `POST /v1/findings/{id}/request-decision` on a converted, not yet concluded finding.
- **`sum_conclusion`**: Immaterial · Material, over the newest frozen SUM snapshot for the
  conclusion. The card carries the snapshot's id and inputs hash; applying refuses a snapshot
  that changed since (409 `snapshot_changed`).
"""

from __future__ import annotations

from collections.abc import Sequence
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
    DecisionKind,
    raise_decision_card,
    register_decision_kind,
)

SEVERITY_KIND: Final = "deficiency_severity"
SUM_KIND: Final = "sum_conclusion"
_SEVERITIES: Final = (
    ("deficiency", "Deficiency"),
    ("significant_deficiency", "Significant deficiency"),
    ("material_weakness", "Material weakness"),
)
_SUM_OPTIONS: Final = (("immaterial", "Immaterial"), ("material", "Material"))


class NotConcludable(DomainConflict):
    """The finding is not an open deficiency (not converted, or already concluded)."""

    code = "not_concludable"


class NoSnapshot(DomainConflict):
    """The SUM has no frozen snapshot for the conclusion yet."""

    code = "no_snapshot"


class SnapshotChanged(DomainConflict):
    code = "snapshot_changed"


def _deficiency_question(deficiency_id: UUID) -> str:
    return f"deficiency.{deficiency_id.hex}"


def _deficiency_of(question_key: str) -> UUID:
    if not question_key.startswith("deficiency."):
        raise NotFound("deficiency")
    return UUID(question_key.removeprefix("deficiency."))


_DEFICIENCY = text(
    "SELECT d.id, d.finding_id, d.status, d.severity_proposed, d.version, f.ref, f.title "
    "FROM deficiencies d JOIN audit_findings f "
    "ON f.tenant_id = d.tenant_id AND f.id = d.finding_id "
    "WHERE d.id = :id"
)


async def _severity_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    deficiency_id = _deficiency_of(subject.question_key)
    async with tenant_session(tenant) as session:
        found = (
            (await session.execute(_DEFICIENCY, {"id": deficiency_id})).mappings().one_or_none()
        )
    if found is None:
        raise NotFound("deficiency")
    if found["status"] != "proposed":
        raise NotConcludable(facts={"status": cast(str, found["status"])})
    figures = {"deficiency_id": str(deficiency_id), "version": str(found["version"])}
    proposed = cast(str | None, found["severity_proposed"])
    return ComputedCard(
        options=tuple(
            CardOption(key, label, figures, "Proposed" if key == proposed else None)
            for key, label in _SEVERITIES
        ),
        context=(CardContext("finding", "Finding", f"{found['ref']} · {found['title']}"),),
    )


async def _apply_severity(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    deficiency_id = UUID(decided.figures["deficiency_id"])
    moved = await tx.session.scalar(
        text(
            "UPDATE deficiencies SET status = 'concluded', severity_concluded = :sev, "
            "decision_card_id = :card, decision_id = :decision, version = version + 1 "
            "WHERE id = :id AND status = 'proposed' AND version = :v RETURNING id"
        ),
        {
            "sev": decided.option_key,
            "card": decided.card_id,
            "decision": decided.decision_id,
            "id": deficiency_id,
            "v": int(decided.figures["version"]),
        },
    )
    if moved is None:
        raise NotConcludable(facts={"status": "changed"})
    tx.record(
        "deficiency.concluded",
        target=Target("deficiency", deficiency_id),
        after=Ref(decision=decided.decision_id),
        scope=Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id),
    )


async def request_severity_decision(ctx: AuthContext, finding_id: UUID) -> UUID:
    """The `deficiency_severity` card on a converted finding's open deficiency."""
    async with tenant_session(ctx.tenant) as session:
        found = (
            (
                await session.execute(
                    text(
                        "SELECT id, engagement_id, work_item_id, status FROM deficiencies "
                        "WHERE finding_id = :f"
                    ),
                    {"f": finding_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if found is None or found["status"] != "proposed":
        raise NotConcludable(facts={"status": "none" if found is None else str(found["status"])})
    return await raise_decision_card(
        ctx,
        engagement_id=cast(UUID, found["engagement_id"]),
        kind=SEVERITY_KIND,
        question_key=_deficiency_question(cast(UUID, found["id"])),
        work_item_id=cast(UUID, found["work_item_id"]),
    )


_SNAPSHOT = text(
    "SELECT id, version_no, inputs_hash, totals FROM sum_snapshots WHERE work_item_id = :w "
    "AND purpose = 'conclusion' ORDER BY version_no DESC LIMIT 1"
)


async def _sum_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    if subject.work_item_id is None:
        raise NoSnapshot
    async with tenant_session(tenant) as session:
        found = (
            (await session.execute(_SNAPSHOT, {"w": subject.work_item_id}))
            .mappings()
            .one_or_none()
        )
    if found is None:
        raise NoSnapshot
    figures = {"snapshot_id": str(found["id"]), "inputs_hash": cast(str, found["inputs_hash"])}
    return ComputedCard(
        options=tuple(CardOption(key, label, figures) for key, label in _SUM_OPTIONS),
        context=(CardContext("snapshot", "SUM snapshot", f"v{found['version_no']}"),),
    )


async def _apply_sum(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    snapshot_id = UUID(decided.figures["snapshot_id"])
    found = await tx.session.scalar(
        text("SELECT inputs_hash FROM sum_snapshots WHERE id = :id"), {"id": snapshot_id}
    )
    if found != decided.figures["inputs_hash"]:
        raise SnapshotChanged
    tx.record(
        "sum.concluded",
        target=Target("sum_snapshot", snapshot_id),
        after=Ref(decision=decided.decision_id),
        scope=Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id),
    )


async def request_sum_conclusion(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID
) -> UUID:
    """The `sum_conclusion` card over the newest frozen conclusion snapshot (409 `no_snapshot`)."""
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(_SNAPSHOT, {"w": work_item_id})
    if found is None:
        raise NoSnapshot
    return await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=SUM_KIND,
        question_key="sum.conclusion",
        work_item_id=work_item_id,
    )


def register_completion_decision_kinds() -> None:
    register_decision_kind(
        DecisionKind(
            code=SEVERITY_KIND,
            reserved_role="engagement_partner",
            options=_severity_card,
            questions={"deficiency": "Severity of the deficiency"},
            apply=_apply_severity,
        )
    )
    register_decision_kind(
        DecisionKind(
            code=SUM_KIND,
            reserved_role="engagement_partner",
            options=_sum_card,
            questions={"sum.conclusion": "Uncorrected misstatements, taken together"},
            apply=_apply_sum,
        )
    )


_AUDIT_OWNERS: Final = {
    "deficiency": text("SELECT id, engagement_id FROM deficiencies WHERE id = ANY(:ids)"),
    "sum_snapshot": text("SELECT id, engagement_id FROM sum_snapshots WHERE id = ANY(:ids)"),
}
AUDIT_KINDS: Final = frozenset(_AUDIT_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """The trail places these rows on their engagement (SPEC-304; DEC-121)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_AUDIT_OWNERS[kind], {"ids": list(ids)})
        return {found: owned for found, owned in rows}
