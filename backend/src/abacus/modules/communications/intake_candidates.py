"""INB-02's destination candidates from the matcher's intake mode (N-01-T22 follow-up;
N-01 §3.4, §6; DEC-1287).

communications may not import agents (ADR-008), so agents fills a slot at import
(`register_intake_candidates`): for some attachments, the latest intake run's shown proposals as
(kind, id, confidence, match id). Unregistered, every card has none (fail closed).

- **Cards** (`card_candidates`): a card names a candidate only if the reader may file there now
  (the picker's folders under `inbox.triage`, and the open requests the reader can read on the
  client's engagements; walls apply, closed requests are left out), with its label as the
  path. A proposal never reveals a destination the reader cannot file to.
- **`ambiguous_candidates`** (`on_intake_recorded`, on `inbox_match.intake_recorded`): when the
  top two shown proposals are within 5 points and the top is below 90, the flag joins the
  attachment's latest flag run (`block_bulk`), once. Bulk filing then refuses the card until a
  person picks.

The matcher proposes; a person files (I-AGENT-NEVER). Nothing here files, ignores or holds.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.communications.intake_matching import intake_folder_destinations
from abacus.modules.communications.triage_flags import CHECKER_VERSION, ambiguous
from abacus.modules.engagements.api import work_item_index
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests.api import request_items_for

_ACTOR: Final = "communications.intake_candidates"
_OPEN_REQUEST: Final = frozenset({"draft", "requested", "uploaded", "returned"})  # take a file


@dataclass(frozen=True)
class IntakeCandidate:
    """One shown intake proposal, best first."""

    kind: str
    id: UUID
    confidence: Decimal  # 0..1, as the matcher said
    match_id: UUID


CandidateSource = Callable[
    [TenantContext, Sequence[UUID]], Awaitable[dict[UUID, list[IntakeCandidate]]]
]
_source: CandidateSource | None = None


def register_intake_candidates(source: CandidateSource | None) -> None:
    """agents' reader of its intake proposals; None removes it."""
    global _source
    _source = source


async def intake_candidates(
    tenant: TenantContext, attachment_ids: Sequence[UUID]
) -> dict[UUID, list[IntakeCandidate]]:
    if _source is None or not attachment_ids:
        return {}
    return await _source(tenant, attachment_ids)


def _score(c: IntakeCandidate) -> int:
    return int((c.confidence * 100).to_integral_value())


@dataclass(frozen=True)
class CardCandidate:
    kind: str
    id: UUID
    label: str
    confidence: float
    match_id: UUID


async def _labels(ctx: AuthContext, client_id: UUID) -> dict[tuple[str, UUID], str]:
    """What the reader may file the client's attachment to now, by (kind, id): the picker's
    folders and the open requests the reader can read on the client's engagements."""
    found: dict[tuple[str, UUID], str] = {}
    try:
        for folder in await intake_folder_destinations(ctx, client_id):
            found[(folder.kind, folder.id)] = folder.label
    except (Forbidden, NotFound):
        return {}  # the reader may not triage this client: nothing is theirs to offer
    items = work_item_index()
    async with tenant_session(ctx.tenant) as session:
        engagements = sorted(
            {
                r.engagement_id
                for r in (
                    await session.execute(
                        items.select()
                        .with_only_columns(items.c.engagement_id)
                        .where(items.c.client_id == client_id)
                    )
                ).all()
                if r.engagement_id is not None
            }
        )
    for engagement_id in engagements:
        try:
            requests = await request_items_for(ctx, engagement_id)
        except (Forbidden, NotFound):
            continue  # walled off or not theirs to read: none of its requests is named
        for r in requests:
            if r.status in _OPEN_REQUEST:
                found[("request", r.id)] = r.description
    return found


async def card_candidates(
    ctx: AuthContext, attachment_ids: Sequence[UUID]
) -> dict[UUID, list[CardCandidate]]:
    """Each card's candidates the reader may file to, best first."""
    proposed = await intake_candidates(ctx.tenant, attachment_ids)
    if not proposed:
        return {}
    async with tenant_session(ctx.tenant) as session:
        clients = {
            r.id: r.client_id
            for r in (
                await session.execute(
                    text("SELECT id, client_id FROM inbox_attachments WHERE id = ANY(:ids)"),
                    {"ids": list(proposed)},
                )
            ).all()
        }
    labels: dict[UUID, dict[tuple[str, UUID], str]] = {}
    out: dict[UUID, list[CardCandidate]] = {}
    for attachment_id, candidates in proposed.items():
        client_id = clients.get(attachment_id)
        if client_id is None:
            continue
        if client_id not in labels:
            labels[client_id] = await _labels(ctx, client_id)
        offered = labels[client_id]
        out[attachment_id] = [
            CardCandidate(c.kind, c.id, offered[(c.kind, c.id)], float(c.confidence), c.match_id)
            for c in candidates
            if (c.kind, c.id) in offered
        ]
    return out


async def on_intake_recorded(event: OutboxEvent) -> None:
    """`inbox_match.intake_recorded`: raise `ambiguous_candidates` on the latest flag run when
    the top two shown proposals are too close to call."""
    tenant = TenantContext(event.tenant_id, "system", _ACTOR)
    attachment_id = UUID(str(event.payload["attachment_id"]))
    candidates = (await intake_candidates(tenant, [attachment_id])).get(attachment_id, [])
    pair = ambiguous([_score(c) for c in candidates])
    if pair is None:
        return
    async with uow(tenant) as tx:
        run_no = await tx.session.scalar(
            text("SELECT max(run_no) FROM inbox_attachment_flags WHERE attachment_id = :id"),
            {"id": attachment_id},
        )
        added = (
            await tx.session.execute(
                text(
                    "INSERT INTO inbox_attachment_flags (tenant_id, attachment_id, run_no, kind, "
                    "severity, facts, checker_version) VALUES (:tenant, :attachment, :run, "
                    "'ambiguous_candidates', 'block_bulk', CAST(:facts AS jsonb), :checker) "
                    "ON CONFLICT (tenant_id, attachment_id, run_no, kind) DO NOTHING RETURNING id"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "attachment": attachment_id,
                    "run": int(run_no or 1),
                    "facts": json.dumps({"top": pair[0], "second": pair[1]}, sort_keys=True),
                    "checker": CHECKER_VERSION,
                },
            )
        ).first() is not None
        tx.record(
            "inbox_attachment.flagged",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(run_no=int(run_no or 1), flags=1 if added else 0),
        )
