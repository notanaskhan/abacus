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
from abacus.modules.review.api import decided_cards, open_note_counts

_ROUTES: Final = "/firm/audits/{wi}?tab="


def _link(work_item_id: UUID, tab: str) -> str:
    return _ROUTES.format(wi=work_item_id) + tab


async def _scalar(tenant: TenantContext, sql: str, work_item_id: UUID) -> object:
    async with tenant_session(tenant) as session:
        return await session.scalar(text(sql), {"wi": work_item_id})


async def _engagement(tenant: TenantContext, work_item_id: UUID) -> UUID | None:
    found = await _scalar(
        tenant, "SELECT engagement_id FROM work_items WHERE id = :wi", work_item_id
    )
    return found if isinstance(found, UUID) else None


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
    state = await _scalar(
        tenant,
        "SELECT management_approval FROM statement_documents WHERE work_item_id = :wi "
        "ORDER BY updated_at DESC LIMIT 1",
        work_item_id,
    )
    link = _link(work_item_id, "statements")
    if state == "approved_by_management":
        return ItemFact("done", "Approved by management", link)
    return ItemFact("open", "Sent for approval" if state == "sent_for_approval" else None, link)


async def fs_final(tenant: TenantContext, work_item_id: UUID) -> ItemFact:
    status = await _scalar(
        tenant,
        "SELECT status FROM statement_documents WHERE work_item_id = :wi "
        "ORDER BY updated_at DESC LIMIT 1",
        work_item_id,
    )
    link = _link(work_item_id, "statements")
    if status in ("final", "signed_off"):
        return ItemFact("done", "Final", link)
    return ItemFact("open", None, link)


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
    ):
        register_completion_fact(key, provider)


__all__ = ["register_completion_facts"]
