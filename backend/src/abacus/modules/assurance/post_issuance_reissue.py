"""Reissue and intake for post-issuance cases (Q-05-T17; SPEC-711 AC-18; A-07's release; DEC-5828).
PROTECTED (red: a released report is reopened).

- **Reopen for reissue** (`post_issuance.reissue`: the EP, fresh MFA) on a case decided "Revise and
  reissue": a new dual-dated draft of the report (`audit_report_versions` with `dual_date` today and
  `reissue_of_release_id` the original release), the report's current version moved to it, under
  the `post_issuance` archived-write kind; AUD-23 g reads it live.
- **Reissue release** goes through A-07's release transaction unchanged: the release records kind
  `reissue` (with `reissue_of_id`) when the released version is a reissue draft.
- **Notify users** stays a manual step: recorded as an audit event, nothing is sent.
- **Intake**: `post_issuance_source` is an INB-01 destination listing the client's open cases; filing
  writes the document on the archived engagement only as the case's source
  (`post_issuance_sources`), with no other write to the locked work item.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, authorise

TARGET: Final = "post_issuance_event"
DESTINATION: Final = "post_issuance_source"


class NotRevising(DomainConflict):
    code = "post_issuance_not_revising"
    message = "Only a case decided Revise and reissue reopens the report."


async def reopen_for_reissue(ctx: AuthContext, work_item_id: UUID, case_id: UUID) -> tuple[UUID, UUID]:
    """Answers (the original release, the new draft version)."""
    from abacus.modules.assurance.record_auth import fresh_mfa_at
    from abacus.modules.engagements.api import get_ref, work_item_engagement

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    from dataclasses import replace

    await authorise(ctx, "post_issuance.reissue", replace(ref.resource(), work_item_id=work_item_id))
    fresh_mfa_at(ctx)
    async with tenant_session(ctx.tenant) as session:
        case = (await session.execute(
            text("SELECT status, decision FROM post_issuance_events WHERE id = :c AND work_item_id = :w"),
            {"c": case_id, "w": work_item_id},
        )).first()  # fmt: skip
        report = (await session.execute(text(
            "SELECT r.id, v.id AS version_id, v.version_no, v.choices, v.paragraphs, v.report_date, "
            "v.city, v.content_hash, (SELECT x.id FROM report_releases x WHERE x.work_item_id = :w "
            "AND x.kind = 'original') AS release_id FROM audit_reports r JOIN audit_report_versions v "
            "ON v.id = r.current_version_id WHERE r.work_item_id = :w"
        ), {"w": work_item_id})).first()  # fmt: skip
    if case is None:
        raise NotFound(TARGET)
    if case.decision != "revise_and_reissue":
        raise NotRevising(facts={"decision": str(case.decision)})
    if report is None or report.release_id is None:
        raise NotFound("report_release")
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        version_id = cast(UUID, await tx.session.scalar(text(
            "INSERT INTO audit_report_versions (tenant_id, engagement_id, work_item_id, report_id, "
            "version_no, choices, paragraphs, report_date, city, dual_date, reissue_of_release_id, "
            "content_hash, created_by) VALUES (:t, :e, :w, :r, :n, :choices, :paras, :rd, :city, "
            ":dual, :rel, :hash, :u) RETURNING id"
        ), {
            "t": ctx.tenant_id, "e": engagement_id, "w": work_item_id, "r": report.id,
            "n": int(report.version_no) + 1, "choices": report.choices, "paras": report.paragraphs,
            "rd": report.report_date, "city": report.city, "dual": date.today(),
            "rel": report.release_id, "hash": report.content_hash, "u": ctx.user_id,
        }))  # fmt: skip
        await tx.session.execute(
            text("UPDATE audit_reports SET current_version_id = :v WHERE id = :r"),
            {"v": version_id, "r": report.id},
        )
        tx.record(
            "post_issuance.reissue_opened", target=Target(TARGET, case_id),
            after=Ref(version=version_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )  # fmt: skip
    return cast(UUID, report.release_id), version_id


async def record_notify_users(ctx: AuthContext, work_item_id: UUID, case_id: UUID) -> None:
    """Notify users is a person's step outside Accrued; only the record of it is written."""
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        tx.record("post_issuance.users_notified_manually", target=Target(TARGET, case_id),
                  scope=Scope(work_item_id=work_item_id))  # fmt: skip


# --- INB-01: a document filed only as a case's source -------------------------------------------


async def _nodes(ctx: AuthContext, client_id: UUID, parent: UUID | None) -> Sequence[object]:
    from abacus.modules.communications.api import IntakeNode
    from abacus.modules.engagements.api import engagement_hold_facts

    if parent is not None:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(text(
            "SELECT id, ref, engagement_id FROM post_issuance_events WHERE status IN "
            "('under_evaluation', 'reissue_in_progress') ORDER BY ref"
        ))).all()  # fmt: skip
    out = []
    for case_id, ref, engagement_id in rows:
        facts = await engagement_hold_facts(ctx.tenant, engagement_id)
        if facts is not None and facts.client_id == client_id:
            out.append(IntakeNode(DESTINATION, case_id, f"{ref} · post-issuance source"))
    return out


async def _place(tenant: TenantContext, tx: UnitOfWork, case_id: UUID) -> object:
    from abacus.modules.communications.api import Placement as IntakePlacement
    from abacus.modules.engagements.api import engagement_hold_facts

    row = (await tx.session.execute(
        text("SELECT engagement_id, work_item_id FROM post_issuance_events WHERE id = :c"), {"c": case_id}
    )).first()  # fmt: skip
    if row is None:
        raise NotFound(TARGET)
    facts = await engagement_hold_facts(tenant, row.engagement_id)
    if facts is None:
        raise NotFound(TARGET)
    await tx.allow_archived_write("post_issuance")
    return IntakePlacement(row.engagement_id, row.work_item_id, facts.client_id)


async def _after_file(tx: UnitOfWork, case_id: UUID, evidence_version_id: UUID) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO post_issuance_sources (tenant_id, case_id, evidence_version_id, filed_from, "
            "created_by) VALUES (:t, :c, :v, 'intake', :by) ON CONFLICT DO NOTHING"
        ),
        {"t": tx.tenant.tenant_id, "c": case_id, "v": evidence_version_id, "by": tx.tenant.actor_id},
    )
    tx.record("post_issuance.source_filed", target=Target(TARGET, case_id), after=Ref(version=evidence_version_id))


def register() -> None:
    from abacus.modules.communications.api import IntakeDestination, register_intake_destination

    register_intake_destination(IntakeDestination(DESTINATION, _nodes, _place, _after_file))  # type: ignore[arg-type]


__all__ = ["DESTINATION", "NotRevising", "record_notify_users", "register", "reopen_for_reissue"]
