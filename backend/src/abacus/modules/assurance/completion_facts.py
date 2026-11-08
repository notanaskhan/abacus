"""The completion items assurance answers itself (A-07-T22; DEC-2806): facts from its own tables
and from the review module's API, never a status a person typed. Each provider returns an
`ItemFact` (status, a code-worded evidence line, the screen that clears it).

Registered by `assurance.api` at import. Items whose facts another module owns (sign-off
coverage, the disclosure checklist, the Form 5500 tie, supplemental schedules, the certification,
the filing plan) register from that module; until they do, the projector shows them open with
"Not yet derived".
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.completion_projector import ItemFact, register_completion_fact
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.reporting.api import checklist_counts, statement_state
from abacus.modules.review.api import decided_cards, open_note_counts

_ROUTES: Final = "/firm/audits/{wi}?tab="


def _link(work_item_id: UUID, tab: str) -> str:
    return _ROUTES.format(wi=work_item_id) + tab


async def _scalar(tenant: TenantContext, sql: str, work_item_id: UUID) -> object:
    async with tenant_session(tenant) as session:
        return await session.scalar(text(sql), {"wi": work_item_id})


async def _engagement(tenant: TenantContext, work_item_id: UUID) -> UUID | None:
    return await work_item_engagement(tenant, work_item_id)


async def subsequent_events(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'performed') "
                    "AS done FROM subsequent_event_procedures WHERE work_item_id = :wi"
                ),
                {"wi": work_item_id},
            )
        ).one()
    total, done = int(row.total), int(row.done)
    if total and done == total:
        return ItemFact(
            "done", f"{done} of {total} procedures performed", _link(work_item_id, "se")
        )
    return ItemFact(
        "partial" if done else "open",
        f"{done} of {total} procedures performed",
        _link(work_item_id, "se"),
    )


async def rep_letter(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    status = await _scalar(
        tenant,
        "SELECT status FROM representation_letters WHERE work_item_id = :wi "
        "ORDER BY updated_at DESC LIMIT 1",
        work_item_id,
    )
    link = f"/firm/audits/{work_item_id}/letters/representation"
    if status == "signed":
        return ItemFact("done", "Signed and dated as of the report", link)
    return ItemFact("open", None if status is None else f"Letter {status}", link)


async def legal_letter(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    status = await _scalar(
        tenant,
        "SELECT status FROM legal_letters WHERE work_item_id = :wi "
        "ORDER BY updated_at DESC LIMIT 1",
        work_item_id,
    )
    link = _link(work_item_id, "legal")
    if status == "received":
        return ItemFact("done", "Legal letter received", link)
    if status == "not_applicable":
        return ItemFact("done", "Not applicable, with its basis", link)
    return ItemFact("open", "Requested" if status == "requested" else None, link)


async def going_concern(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """Done once the EP's `going_concern` card is decided (the decision is the EP's, never ours);
    the card's state is read through `review.api`, never its tables."""
    card = await _scalar(
        tenant,
        "SELECT decision_card_id FROM going_concern_evaluations WHERE work_item_id = :wi",
        work_item_id,
    )
    engagement_id = await _engagement(tenant, work_item_id)
    link = _link(work_item_id, "gc")
    if isinstance(card, UUID) and engagement_id is not None:
        decided = {c.card_id for c in await decided_cards(tenant, engagement_id)}
        if card in decided:
            return ItemFact("done", "Concluded by the engagement partner", link)
    return ItemFact("open", "Reserved to the engagement partner", link)


async def eqr(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    status = await _scalar(
        tenant,
        "SELECT status FROM eqr_reviews WHERE work_item_id = :wi ORDER BY updated_at DESC LIMIT 1",
        work_item_id,
    )
    link = f"/firm/audits/{work_item_id}/eqr"
    if status is None:
        return ItemFact("done", "No engagement quality review required", link)
    if status == "concurred":
        return ItemFact("done", "Concurred", link)
    return ItemFact("open", "EQR in progress", link)


async def _governance(
    tenant: TenantContext, work_item_id: UUID, kind: str, none_needed: str
) -> ItemFact:
    async with tenant_session(tenant) as session:
        statuses = list(
            (
                await session.execute(
                    text(
                        "SELECT status FROM governance_communications "
                        "WHERE work_item_id = :wi AND kind = :k"
                    ),
                    {"wi": work_item_id, "k": kind},
                )
            ).scalars()
        )
    link = f"/firm/audits/{work_item_id}/letters/governance"
    if not statuses:
        return ItemFact("done", none_needed, link)
    if all(s in ("sent", "acknowledged") for s in statuses):
        return ItemFact("done", "Sent", link)
    return ItemFact("open", None, link)


async def tcwg_260(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    found = await _governance(tenant, work_item_id, "completion_260", "Not yet drafted")
    # AU-C 260's completion letter is always owed: none drafted is open, not "none needed".
    return (
        found
        if found.evidence_text != "Not yet drafted"
        else ItemFact("open", None, found.link_target)
    )


async def sd_mw_265(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    return await _governance(
        tenant, work_item_id, "sd_mw_265", "No significant deficiency or material weakness"
    )


async def findings(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    left = await _scalar(
        tenant,
        "SELECT count(*) FROM audit_findings WHERE work_item_id = :wi "
        "AND route = 'under_evaluation'",
        work_item_id,
    )
    n = int(str(left or 0))
    link = _link(work_item_id, "findings")
    if n == 0:
        return ItemFact("done", "Every finding dispositioned", link)
    return ItemFact("open", f"{n} under evaluation", link)


async def review_notes(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    engagement_id = await _engagement(tenant, work_item_id)
    counts = {} if engagement_id is None else await open_note_counts(tenant, engagement_id)
    n = sum(counts.values())
    link = _link(work_item_id, "notes")
    if n == 0:
        return ItemFact("done", "No open review notes", link)
    return ItemFact("open", f"{n} open", link)


async def mgmt_approval(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    found = await statement_state(tenant, work_item_id)
    state = None if found is None else found[1]
    link = _link(work_item_id, "statements")
    if state == "approved_by_management":
        return ItemFact("done", "Approved by management", link)
    return ItemFact("open", "Sent for approval" if state == "sent_for_approval" else None, link)


async def fs_final(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    found = await statement_state(tenant, work_item_id)
    status = None if found is None else found[0]
    link = _link(work_item_id, "statements")
    if status in ("final", "signed_off"):
        return ItemFact("done", "Final", link)
    return ItemFact("open", None, link)


# --- S31 close (A-07-T22): the facts the projector still lacked -------------------------------


async def sign_offs(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """Current when no workpaper changed after its sign-off (the AUD-17 matrix's footer)."""
    from abacus.modules.assurance.review_matrix import matrix

    engagement_id = await _engagement(tenant, work_item_id)
    link = _link(work_item_id, "sign-offs")
    if engagement_id is None:
        return ItemFact("open", None, link)
    changed = (await matrix(tenant, engagement_id)).footer.changed_after_sign_off
    if changed == 0:
        return ItemFact("done", "No workpaper changed after sign-off", link)
    return ItemFact("open", f"{changed} changed after sign-off", link)


async def sum_evaluated(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """Done once the EP's SUM conclusion card is decided (the decision is the EP's, never ours)."""
    from abacus.modules.assurance.completion_decisions import SUM_KIND

    engagement_id = await _engagement(tenant, work_item_id)
    link = _link(work_item_id, "misstatements")
    if engagement_id is not None and any(
        c.kind == SUM_KIND for c in await decided_cards(tenant, engagement_id)
    ):
        return ItemFact("done", "Concluded by the engagement partner", link)
    return ItemFact("open", "Reserved to the engagement partner", link)


async def disclosure_checklist(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    found = await checklist_counts(tenant, work_item_id)
    link = _link(work_item_id, "statements")
    if found is None:
        return ItemFact("open", None, link)
    answered, total = found
    if total > 0 and answered == total:
        return ItemFact("done", f"{answered} of {total} answered", link)
    return ItemFact("open", f"{answered} of {total} answered", link)


_TIE = text(
    """
    SELECT d.status,
           (SELECT count(*) FROM ebp_form5500_lines l
             WHERE l.draft_id = d.id AND l.classification = 'inconsistent') AS lines_off,
           (SELECT count(*) FROM ebp_part_iv_answers a
             WHERE a.draft_id = d.id AND a.result = 'inconsistent') AS answers_off
      FROM ebp_form5500_drafts d
     WHERE d.work_item_id = :wi AND d.status <> 'superseded'
     ORDER BY d.created_at DESC LIMIT 1
    """
)


async def form5500_tie(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """EBP-07: the draft is tied by code, nothing inconsistent (reconciling items documented)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_TIE, {"wi": work_item_id})).first()
    link = f"/firm/audits/{work_item_id}?section=ebp_07"
    if row is None:
        return ItemFact("open", "Draft Form 5500 not received", link)
    off = int(row.lines_off) + int(row.answers_off)
    if row.status == "tied" and off == 0:
        return ItemFact("done", "Ties, or differs only by documented reconciling items", link)
    return ItemFact("open", f"{off} inconsistent" if off else None, link)


async def certification(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """EBP-06: every point of the limited-scope certification evaluated by a person."""
    from abacus.modules.assurance.ebp_investments import points

    found = await points(tenant, work_item_id)
    link = f"/firm/audits/{work_item_id}?section=ebp_06"
    if not found:
        return ItemFact("open", None, link)
    left = sum(1 for p in found if p.answer != "evaluated")
    if left == 0:
        return ItemFact("done", f"{len(found)} of {len(found)} points evaluated", link)
    return ItemFact("open", f"{len(found) - left} of {len(found)} points evaluated", link)


_FOUR_A = text(
    """
    SELECT a.result FROM ebp_part_iv_answers a JOIN ebp_form5500_drafts d ON d.id = a.draft_id
     WHERE d.work_item_id = :wi AND d.status <> 'superseded' AND a.question = '4a'
     ORDER BY d.created_at DESC LIMIT 1
    """
)


async def schedules(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    """EBP-07 (DEC-2820): the 4i schedule ties to the draft's line 1c investments, and Part IV
    4a agrees with the late remittances that make up the 4a schedule."""
    from abacus.modules.assurance.ebp_form5500 import schedule_4i_facts

    found = await schedule_4i_facts(tenant, work_item_id)
    async with tenant_session(tenant) as session:
        four_a = await session.scalar(_FOUR_A, {"wi": work_item_id})
    link = f"/firm/audits/{work_item_id}?section=ebp_07&tab=schedules"
    if found.ties and four_a == "consistent":
        return ItemFact("done", "4i ties to the draft; 4a agrees with the late remittances", link)
    if not found.ties:
        return ItemFact("open", "4i does not tie to the draft", link)
    return ItemFact("open", "4a not consistent with the late remittances", link)


def register_completion_facts() -> None:
    """Once, from `assurance.api`."""
    for key, provider in (
        ("subsequent_events", subsequent_events),
        ("rep_letter", rep_letter),
        ("legal_letter", legal_letter),
        ("going_concern", going_concern),
        ("eqr", eqr),
        ("tcwg_260", tcwg_260),
        ("sd_mw_265", sd_mw_265),
        ("findings", findings),
        ("review_notes", review_notes),
        ("mgmt_approval", mgmt_approval),
        ("fs_final", fs_final),
        # S31 close: the rest the template names (`filing` stays a person's: no in-app fact).
        ("sign_offs", sign_offs),
        ("sum", sum_evaluated),
        ("disclosure_checklist", disclosure_checklist),
        ("form5500_tie", form5500_tie),
        ("certification", certification),
        ("schedules", schedules),
    ):
        register_completion_fact(key, provider)


__all__ = ["register_completion_facts"]
