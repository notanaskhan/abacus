"""The audit's gate providers (A-04-T43; F-03-T13's slots; DEC-2057). PROTECTED (red).

Every assurance gate an engagement's lifecycle reads is registered here through
`engagements.register_gate_provider`, over facts its owner computes:

- **G4** planning complete: A-04-T18's `g4_facts` (materiality stands, the register is the
  partner's at an unchanged hash, nothing proposed), with its blockers.
- **G5** review complete (A-06-T15, DEC-2215): met only when every registered reviewable on the
  engagement has each of its required levels (the owner's facts carry K-02's
  `required_review_levels`) signed on its current content and not stale, and no open or
  responded review note remains. Blockers name the objects: `unsigned:<type>:<id>:L<n>`,
  `stale:<type>:<id>:L<n>`, `review_note:<id>`. A provider that fails leaves G5 unmet
  (`review_unavailable`), never met. It replaces the review module's SPEC-313 provider.

- **G6 to G9** (A-07-T15, DEC-2415; F9): on a firm with `assurance_release_mode = external`, the
  SPEC-314 and record-mode providers stay in force, unchanged. On `in_app`, G6 reads `not_required`
  when no EQR is assigned or a concurrence; G7 a signed letter dated as of the report; G8 a release
  row; G9 a locked archive, each with live blockers. Compilation and preparation skip G6 and G7
  (gate_policy.PLATFORM). A failing provider is unmet.

A change to this file is a red diff: it is named in `docs/architecture/protected-paths.md` and
needs the security review.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.archive_gate import g9
from abacus.modules.assurance.completion import g6, g7
from abacus.modules.assurance.planning_gate import g4_facts
from abacus.modules.assurance.release import g8, release_mode
from abacus.modules.engagements.api import (
    GateFact,
    assurance_item_id,
    engagement_type_of,
    register_gate_provider,
    replace_gate_provider,
    required_gates,
)
from abacus.modules.identity.api import team_of
from abacus.modules.review.api import (
    GateSource,
    OpenGate,
    open_notes,
    register_gate_source,
    reviewable_facts,
    reviewables_of,
    sign_off_states,
)

GateProvider = Callable[[TenantContext, UUID], Awaitable[GateFact]]
OpenFor = Callable[[TenantContext, UUID | None], Awaitable[list[OpenGate]]]


async def g5_blockers(tenant: TenantContext, engagement_id: UUID) -> list[str]:
    reviewables = await reviewables_of(tenant, engagement_id)
    if not reviewables:
        return ["no_reviewables"]
    blockers: list[str] = []
    # L5 is the EQR's level: required only where the engagement has an EQR on its team. The
    # firm's review_levels standard names L5 for every engagement, so one without an EQR could
    # never meet G5 (S35 follow-up, DEC-3306: Granite Peak's release). Read once, when needed.
    has_eqr: bool | None = None
    for r in reviewables:
        facts = await reviewable_facts(tenant, r.target_type, r.target_id)
        states = await sign_off_states(
            tenant, r.target_type, [r.target_id], {r.target_id: facts.content_hash}
        )
        by_level = {s.level: s for s in states[r.target_id]}
        for level in facts.required_levels:
            if level == 5:
                if has_eqr is None:
                    team = await team_of(tenant.tenant_id, engagement_id)
                    has_eqr = any(role == "eqr_reviewer" for _u, role in team)
                if not has_eqr:
                    continue
            state = by_level.get(level)
            if state is None or state.signed_by is None:
                blockers.append(f"unsigned:{r.target_type}:{r.target_id}:L{level}")
            elif state.stale:
                blockers.append(f"stale:{r.target_type}:{r.target_id}:L{level}")
    blockers.extend(
        f"review_note:{note_id}" for note_id, _ in await open_notes(tenant, engagement_id)
    )
    return blockers


async def g5_facts(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    try:
        blockers = await g5_blockers(tenant, engagement_id)
    except Exception:  # a provider that fails leaves the gate unmet, never met
        return GateFact(met=False, blockers=("review_unavailable",))
    return GateFact(met=not blockers, blockers=tuple(blockers))


def _not_required(engagement_type: str | None, gate: str) -> bool:
    """Per-type policy (F9): a gate the platform doesn't require of this family is met."""
    return engagement_type is not None and gate not in required_gates(engagement_type)


async def _in_app_facts(tenant: TenantContext, engagement_id: UUID) -> Mapping[str, object] | None:
    """Each in-app gate's facts in one read of this module's tables, or None with no work item."""
    item = await assurance_item_id(tenant, engagement_id)
    if item is None:
        return None
    engagement_type = await engagement_type_of(tenant, engagement_id)
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT q.status AS eqr_status,
                           q.eqr_user_id,
                           l.status AS letter_status,
                           (SELECT count(*) > 0 FROM report_releases r
                             WHERE r.work_item_id = :item AND r.kind = 'original') AS released,
                           a.status AS archive_status
                      FROM (SELECT 1) one
                      LEFT JOIN eqr_reviews q ON q.work_item_id = :item
                      LEFT JOIN representation_letters l ON l.work_item_id = :item
                      LEFT JOIN archives a ON a.work_item_id = :item
                    """
                    ),
                    {"item": item},
                )
            )
            .mappings()
            .one()
        )
    return {"engagement_type": engagement_type, **dict(row)}


async def _eqr_on_team(tenant: TenantContext, engagement_id: UUID) -> bool:
    """ENG-05 assigned an EQR: someone on the team holds `eqr_reviewer`."""
    team = await team_of(tenant.tenant_id, engagement_id)
    return any(role == "eqr_reviewer" for _member, role in team)


async def in_app_g6(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    facts = await _in_app_facts(tenant, engagement_id)
    if facts is None:
        return GateFact(met=False, blockers=("no_work_item",))
    if _not_required(cast(str | None, facts["engagement_type"]), "G6"):
        return GateFact(met=True)
    if facts["eqr_status"] == "concurred":
        return GateFact(met=True)
    if facts["eqr_user_id"] is None:
        # EQR-required comes from the ENG-05 assignment. An EQR on the team whose review hasn't
        # opened yet (eligibility pending, or no checklist template: it fails closed) still owes a
        # concurrence, so G6 stays unmet until one exists (A-07-T21; DEC-2817).
        if await _eqr_on_team(tenant, engagement_id):
            return GateFact(met=False, blockers=("eqr_not_concurred",))
        return GateFact(met=True)
    return GateFact(met=False, blockers=("eqr_not_concurred",))


async def in_app_g7(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    facts = await _in_app_facts(tenant, engagement_id)
    if facts is None:
        return GateFact(met=False, blockers=("no_work_item",))
    if _not_required(cast(str | None, facts["engagement_type"]), "G7"):
        return GateFact(met=True)
    status = facts["letter_status"]
    if status is None:
        return GateFact(met=False, blockers=("no_rep_letter",))
    if status == "date_mismatch":
        return GateFact(met=False, blockers=("rep_letter_date_mismatch",))
    if status != "signed":
        return GateFact(met=False, blockers=("rep_letter_not_signed",))
    return GateFact(met=True)


async def in_app_g8(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    facts = await _in_app_facts(tenant, engagement_id)
    if facts is None:
        return GateFact(met=False, blockers=("no_work_item",))
    return (
        GateFact(met=True)
        if facts["released"]
        else GateFact(met=False, blockers=("not_released",))
    )


async def in_app_g9(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    facts = await _in_app_facts(tenant, engagement_id)
    if facts is None:
        return GateFact(met=False, blockers=("no_work_item",))
    if facts["archive_status"] == "locked":
        return GateFact(met=True)
    return GateFact(met=False, blockers=("not_locked",))


def _by_mode(in_app: GateProvider, external: GateProvider) -> GateProvider:
    """External firms keep what they had, exactly (F9). A provider that fails is unmet, not met."""

    async def provider(tenant: TenantContext, engagement_id: UUID) -> GateFact:
        chosen = in_app if await release_mode(tenant) == "in_app" else external
        try:
            return await chosen(tenant, engagement_id)
        except Exception:
            return GateFact(met=False, blockers=("gate_unavailable",))

    return provider


def register() -> None:
    register_gate_provider("G4", g4_facts)
    replace_gate_provider("G5", g5_facts)
    register_gate_provider("G6", _by_mode(in_app_g6, g6))
    register_gate_provider("G7", _by_mode(in_app_g7, g7))
    register_gate_provider("G8", _by_mode(in_app_g8, g8))
    register_gate_provider("G9", _by_mode(in_app_g9, g9))
    register_completion_gates()


# --- C13: what waits on a person, in_app firms only (F9). Each row has its reserved person or
# role, and `visible()` walls it on the projection's read. ---------------------------------------

_EVENTS: Final = frozenset(
    {"eqr.concurred", "rep_letter.approved", "governance_communication.sent"}
    | {"report.released", "archive.locked", "archive_addition.decided"}
)
_OPEN: Final[dict[str, TextClause]] = {
    "eqr_concurrence_due": text(
        "SELECT id, engagement_id, work_item_id, eqr_user_id AS assignee, NULL AS role "
        "FROM eqr_reviews WHERE status = 'in_progress' "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR engagement_id = :engagement_id)"
    ),
    "rep_letter_approval": text(
        "SELECT id, engagement_id, work_item_id, NULL::uuid AS assignee, "
        "'engagement_partner' AS role FROM representation_letters "
        "WHERE status = 'awaiting_partner_approval' "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR engagement_id = :engagement_id)"
    ),
    "governance_comm_approval": text(
        "SELECT id, engagement_id, work_item_id, NULL::uuid AS assignee, "
        "'engagement_partner' AS role FROM governance_communications "
        "WHERE status = 'awaiting_ep_approval' "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR engagement_id = :engagement_id)"
    ),
    "report_release_due": text(
        "SELECT id, engagement_id, work_item_id, NULL::uuid AS assignee, "
        "'engagement_partner' AS role FROM audit_reports WHERE status = 'approved' "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR engagement_id = :engagement_id)"
    ),
    "archive_lock_due": text(
        "SELECT id, engagement_id, work_item_id, NULL::uuid AS assignee, 'manager' AS role "
        "FROM archives WHERE status = 'assembling' "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR engagement_id = :engagement_id)"
    ),
    "archive_addition_approval": text(
        "SELECT a.id, a.engagement_id, a.work_item_id, NULL::uuid AS assignee, "
        "'engagement_partner' AS role FROM archive_additions a "
        "WHERE NOT EXISTS (SELECT 1 FROM archive_addition_decisions d "
        "WHERE d.addition_id = a.id) "
        "AND (CAST(:engagement_id AS uuid) IS NULL OR a.engagement_id = :engagement_id)"
    ),
}


def _open_for(subject: str) -> OpenFor:
    query = _OPEN[subject]

    async def open_for(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
        if await release_mode(tenant) != "in_app":
            return []
        async with tenant_session(tenant) as session:
            rows = (await session.execute(query, {"engagement_id": engagement_id})).all()
        return [
            OpenGate(
                r.id,
                r.engagement_id,
                assignee_user_id=r.assignee,
                role=r.role,
                work_item_id=r.work_item_id,
            )
            for r in rows
        ]

    open_for.__qualname__ = f"open_for_{subject}"
    return open_for


_KINDS: Final[dict[str, str]] = {
    "eqr_concurrence_due": "final_approval",
    "rep_letter_approval": "final_approval",
    "governance_comm_approval": "send",
    "report_release_due": "release",
    "archive_lock_due": "final_approval",
    "archive_addition_approval": "final_approval",
}


def register_completion_gates() -> None:
    for subject, kind in _KINDS.items():
        register_gate_source(GateSource(subject, kind, "review.read", _EVENTS, _open_for(subject)))
