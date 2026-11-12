"""The session workflow's turn activity (P-10-T43; SPEC-647 §3.7; DEC-4301).

`workbench.session.turn` reads the person's item (a message or an answer), runs its turn's run
inline through `agents.api.run_session_turn` (read-only), and appends what the turn produced as
insert-only items on the session's own sequence, in one unit of work with one audit event:

- `agent_blocks`: the verified answer (parts that failed provenance read "Unsupported");
- `question`: the turn asked; the session reads `awaiting_answer` and the workflow keeps it open;
- `plan`: the turn proposed writes; exactly one child run is written for it (AC-S4) and named on
  the item, and the workflow starts that child's `AgentRunWorkflow`;
- `notice`: no capability or engagement to run the turn on, or the turn failed (its code).

The session's `client_scope` gains every client the turn read (AC-S3). Each produced item records
`turn_of` (the person's item seq), so a retried activity finds the turn already recorded and
answers the same result without running it again.
"""

from __future__ import annotations

import json
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import TurnOutcome, open_plan_child_run, run_session_turn
from abacus.modules.workbench.session_workflow import TurnDone

_READER: Final = "session-turn"
_ITEM_OF = text(
    "SELECT kind, payload, run_id FROM session_items WHERE session_id = :id AND seq = :seq"
)
_RECORDED = text(
    "SELECT seq, kind, run_id FROM session_items WHERE session_id = :id "
    "AND payload->>'turn_of' = :turn ORDER BY seq"
)
_LOCK = text("SELECT item_seq FROM workbench_sessions WHERE id = :id FOR UPDATE")
_ITEM = text(
    "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, run_id, actor_kind, "
    "actor_id, classification) VALUES (:t, :s, :seq, :kind, CAST(:payload AS jsonb), :run, "
    ":actor_kind, :actor, :class)"
)
_BUMP = text(
    "UPDATE workbench_sessions SET item_seq = :seq, last_item_at = clock_timestamp(), "
    "state = :state, client_scope = ARRAY(SELECT DISTINCT unnest(client_scope || "
    "CAST(:clients AS uuid[]))) WHERE id = :id"
)
_STATE_OF: Final = {
    "completed": "live",
    "needs_input": "awaiting_answer",
    "plan_proposed": "awaiting_answer",
    "failed": "live",
}


def _tenant(tenant_id: str, session_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"{_READER}:{session_id}")


def _done_from(rows: list[tuple[int, str, UUID | None]]) -> TurnDone:
    asked = next((seq for seq, kind, _ in rows if kind == "question"), 0)
    child = next((run for _, kind, run in rows if kind == "plan" and run is not None), None)
    return TurnDone(asked=asked, child_run_id=str(child) if child is not None else None)


async def _request(
    tenant: TenantContext, session_id: UUID, kind: str, payload: dict[str, object]
) -> str:
    """The turn's first user text: the message, or the open question and its answer."""
    body = str(payload.get("body", ""))
    if kind != "answer":
        return body
    async with tenant_session(tenant) as session:
        asked = (
            await session.execute(
                _ITEM_OF, {"id": session_id, "seq": int(str(payload.get("answers_seq", 0)))}
            )
        ).first()
    question = cast(dict[str, object], asked.payload).get("question") if asked else None
    text_of = cast(dict[str, object], question).get("text") if isinstance(question, dict) else None
    return f"Question: {text_of}\nAnswer: {body}" if text_of else body


def _items(
    outcome: TurnOutcome, turn: int, child: UUID | None
) -> list[tuple[str, dict[str, object], UUID | None]]:
    if outcome.status == "completed":
        blocks = outcome.blocks or {"version": 1, "parts": []}
        return [
            (
                "agent_blocks",
                {
                    "v": 1,
                    "turn_of": str(turn),
                    "blocks": blocks,
                    "unsupported": outcome.unsupported,
                },
                None,
            )
        ]
    if outcome.status == "needs_input":
        return [
            ("question", {"v": 1, "turn_of": str(turn), "question": outcome.question or {}}, None)
        ]
    if outcome.status == "plan_proposed":
        steps = [
            {"key": s.get("key"), "label": s.get("label"), "writes": s.get("writes")}
            for s in outcome.plan
        ]
        return [("plan", {"v": 1, "turn_of": str(turn), "steps": steps}, child)]
    return [
        ("notice", {"v": 1, "turn_of": str(turn), "code": outcome.failure or "turn_failed"}, None)
    ]


@activity.defn(name="workbench.session.turn")
async def session_turn_activity(tenant_id: str, session_id: str, kind: str, seq: int) -> TurnDone:
    tenant = _tenant(tenant_id, session_id)
    sid = UUID(session_id)
    async with tenant_session(tenant) as session:
        recorded = (await session.execute(_RECORDED, {"id": sid, "turn": str(seq)})).all()
        if recorded:
            return _done_from([(int(r.seq), r.kind, r.run_id) for r in recorded])
        item = (await session.execute(_ITEM_OF, {"id": sid, "seq": seq})).first()
    if item is None:
        return TurnDone()
    payload = cast(dict[str, object], item.payload)
    child: UUID | None = None
    if item.run_id is None:
        # No run was opened: no capability, or availability refused it (consent_7216, paused, …).
        outcome = TurnOutcome(
            "failed", failure=str(payload.get("blocked") or "capability_unavailable")
        )
    else:
        request = await _request(tenant, sid, "answer" if kind == "answer" else "message", payload)
        outcome = await run_session_turn(UUID(tenant_id), item.run_id, request)
        if outcome.status == "plan_proposed" and outcome.plan:
            child = await open_plan_child_run(UUID(tenant_id), item.run_id, outcome.plan)
        elif outcome.status == "plan_proposed":
            outcome = TurnOutcome(
                "failed", failure="empty_plan", client_scope=outcome.client_scope
            )
    produced = _items(outcome, seq, child)
    written: list[tuple[int, str, UUID | None]] = []
    async with uow(tenant) as tx:
        last = int(cast(int, await tx.session.scalar(_LOCK, {"id": sid})))
        for kind_of, body, run in produced:
            last += 1
            await tx.session.execute(
                _ITEM,
                {
                    "t": UUID(tenant_id),
                    "s": sid,
                    "seq": last,
                    "kind": kind_of,
                    "payload": json.dumps(body, default=str),
                    "run": run if run is not None else item.run_id,
                    "actor_kind": "agent" if kind_of != "notice" else "system",
                    "actor": "accrued_agent" if kind_of != "notice" else "workbench",
                    "class": "confidential",
                },
            )
            written.append((last, kind_of, run))
        await tx.session.execute(
            _BUMP,
            {
                "seq": last,
                "state": _STATE_OF.get(outcome.status, "live"),
                "clients": [UUID(c) for c in outcome.client_scope],
                "id": sid,
            },
        )
        tx.record(
            "session.turn_recorded",
            target=Target("workbench_session", sid),
            after=Ref(seq=last, turn=seq),
        )
    return _done_from(written)


SESSION_ACTIVITIES: Final = (session_turn_activity,)
