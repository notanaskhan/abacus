"""Today questions (I-02-T14; I-02 §3.7, §6.2; SPEC-654; `docs/contracts/today.md`; DEC-60,
DEC-4932). Amber here; the turn runs on `agents`' session workflow v2 (red).

`POST /v1/me/today/questions {text, brief_id}` appends a person's question to their **Today
session for the day**: one `workbench_session` per viewer per day, titled and chipped
"Today · Mon Sep 14", with context kind `today_brief` (`context_refs` holds
`{kind: today_brief, id: <date>}`, no migration). It is created on the first question and listed in
WB-01 under Mine (Q4).

- **Context.** On creation the session gains one `context_added` item of kind `today_brief`: the
  chip and the brief's summary lines, written by code from the assembled brief (counts, cells, each
  card's gates with their code context lines) plus the day's briefing ids for citations. No model
  text is copied into context (I-02 §6.2).
- **Read only, whatever `workbench.plans` says.** The turn is offered only read and compute tools
  (every inline turn is), and a Today session's turn never plans: a request to act ("Approve the
  four sign-offs") gets the read-only notice pointing to SHL-12, and no proposal or plan row is
  written (INV-1; `session_turn_v2`).
- **Availability first** (DF-04): `workbench.assistant`'s firm-level readiness (pause, AI policy)
  before anything is written; unavailable answers 409 `capability_unavailable {reason}` and no
  session, item or run is written.
- **Idempotency.** The same `Idempotency-Key` answers the same item (`post_message`'s rule).
- **Audit** `today_brief.question_asked` with the session and item ids only, never the question
  (DEC-60). The text is Restricted on the item and never logged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import firm_capability_blocked, today_context
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.workbench.sessions import CapabilityUnavailable, Posted, post_message

TODAY_KIND: Final = "today_brief"
ASSISTANT: Final = "workbench.assistant"
READ_ONLY_NOTICE: Final = "today_read_only"  # the turn's notice: act on SHL-12, not here


class BriefNotCurrent(DomainConflict):
    """The question names a brief that is not the viewer's brief for today."""

    code = "brief_not_current"


@dataclass(frozen=True)
class TodayAsked:
    session_id: UUID
    item_id: UUID


def today_ref(day: date) -> dict[str, str]:
    return {"kind": TODAY_KIND, "id": day.isoformat()}


def is_today_session(refs: list[dict[str, str]] | object) -> bool:
    return isinstance(refs, list) and any(
        isinstance(r, dict) and cast(dict[str, object], r).get("kind") == TODAY_KIND
        for r in cast(list[object], refs)
    )


_MINE: Final = text(
    "SELECT id FROM workbench_sessions WHERE owner_user_id = :me AND deleted_at IS NULL "
    "AND context_refs @> CAST(:ref AS jsonb) ORDER BY created_at LIMIT 1"
)


async def _today_session(ctx: AuthContext, day: date, chip: str, lines: tuple[str, ...],
                         briefing_ids: tuple[UUID, ...]) -> UUID:  # fmt: skip
    """The viewer's Today session for `day`, created (with its context item) on first use."""
    ref = today_ref(day)
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(_MINE, {"me": ctx.user_id, "ref": json.dumps([ref])})
    if found is not None:
        return cast(UUID, found)
    await authorise(ctx, "session.create", Resource.firm(ctx.tenant_id))
    refs = [ref, {"kind": "capability", "id": ASSISTANT}]
    context = {
        "v": 1,
        "kind": TODAY_KIND,
        "chip_label": chip,
        "summary_lines": list(lines),
        "briefing_ids": [str(b) for b in briefing_ids],
    }
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"today_session:{ctx.user_id}:{day.isoformat()}"},
        )
        again = await tx.session.scalar(_MINE, {"me": ctx.user_id, "ref": json.dumps([ref])})
        if again is not None:
            return cast(UUID, again)
        session_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO workbench_sessions (tenant_id, title, title_source, "
                    "owner_user_id, origin, context_refs, client_scope, item_seq) VALUES (:t, "
                    ":title, 'manual', :me, 'manual', CAST(:refs AS jsonb), '{}', 1) "
                    "RETURNING id"
                ),
                {"t": ctx.tenant_id, "title": chip, "me": ctx.user_id, "refs": json.dumps(refs)},
            ),
        )
        await tx.session.execute(
            text(
                "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, "
                "actor_kind, actor_id, classification) VALUES (:t, :s, 1, 'context_added', "
                "CAST(:payload AS jsonb), 'system', 'workbench', 'confidential')"
            ),
            {"t": ctx.tenant_id, "s": session_id, "payload": json.dumps(context)},
        )
        tx.record(
            "session.created",
            target=Target("workbench_session", session_id),
            after=Ref(owner=ctx.user_id),
        )
    return session_id


async def post_question(
    ctx: AuthContext, body: str, brief_id: UUID, idempotency_key: str
) -> TodayAsked:
    """The question route's service (module docstring). The route checked the matrix
    (`briefing.ask`) and both flags. The brief is read through agents' Today slot, which
    practice fills (workbench may not import practice; ADR-008)."""
    blocked = await firm_capability_blocked(ctx, ASSISTANT)
    if blocked is not None:
        raise CapabilityUnavailable(facts={"reason": blocked})
    day = await today_context(ctx)
    if day.brief_id is not None and day.brief_id != brief_id:
        raise BriefNotCurrent(facts={"brief_id": str(day.brief_id)})
    if day.brief_id is None:
        raise NotFound("daily_briefing")  # nothing built yet today: the composer waits
    session_id = await _today_session(
        ctx, day.brief_date, day.chip_label, day.lines, day.briefing_ids
    )
    posted: Posted = await post_message(ctx, session_id, body, idempotency_key)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "today_brief.question_asked",
            target=Target("workbench_session", session_id),
            after=Ref(session=session_id, item=posted.item_id),
        )
    return TodayAsked(session_id, posted.item_id)


__all__ = [
    "ASSISTANT",
    "READ_ONLY_NOTICE",
    "TODAY_KIND",
    "BriefNotCurrent",
    "TodayAsked",
    "is_today_session",
    "post_question",
    "today_ref",
]
