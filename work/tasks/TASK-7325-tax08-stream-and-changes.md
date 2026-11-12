---
id: TASK-7325
title: "TAX-08 partials: the session's live thread on the tab's stream; the child run's changes under its plan"
spec: SPEC-649
acceptance_criteria: [AC-6]  # §3.6 Assistant
risk_zone: amber
status: in-review
branch: s37-tax08-stream
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T37
---

## Objective
TASK-7323's flagged partials. The drawer polled the session snapshot because the session stream
answered 501, and the child run's proposed change had no card in the drawer.

## Plan (amber)
- Backend, `workbench/session_events.py`:
  - `SessionItemsChanged` (`session.items_changed`: `session_id`, `seq`) is emitted in the same
    unit of work that writes items: the person's message or answer (`sessions.post_message`) and
    a turn's items (`session_activities.session_turn_activity`).
  - The realtime invalidation maps it to `session:<id>`. It is registered in
    `notifications.realtime.register`, beside the core ones, because the relay's `INVALIDATIONS`
    is composed at notifications' import. The same order bug hid DEC-4318's `sign_off.went_stale`
    and `issue.assigned` (registered at tax's import) whenever notifications imported first, so
    those two are registered there too (same values; tax's registration is guarded).
  - The `session` topic is open only to `sessions.readable_in_full`: the same checks as
    `get_session`, and a locked or omitted session reads False.
  - No item body travels on the stream; the subscriber refetches the snapshot. This uses
    `GET /v1/events` (P-10-T27), not a second stream, so the per-session `…/events` route stays
    501.
- Web, `app-core/realtime.ts`: the tab's one stream now carries the union of every mounted
  surface's topics (`want`/`unwant`). Before, topics replaced each other, so a drawer would have
  dropped the workspace's `engagement:` topic and stopped the stream when it closed.
  `useRealtimeStream` registers each surface's topics.
- Web, `screens/TAX-08/live.tsx`:
  - `session:<id>` invalidates that session's snapshot (`getSession` at its path). The poll runs
    only when the tab has no live stream.
  - Under a plan, the child run's proposals (`GET /v1/agent-runs/{id}/trace/writes`) are listed. A
    waiting one offers "Approve adjustments…" (TAX-08: "→ SHL-10 confirmation"), which opens
    SHL-10's `ApproveSheet` in place so the drawer stays open; the person decides there. A decided
    one reads "✓ Approved by …" or "Rejected by …".
- Rollback: revert. The event stops being emitted and the drawer polls again.

## Tests
- `tests/unit/workbench/test_t7325_session_topic.py`: the event carries identifiers only, maps to
  `session:<id>`, and the topic is open only to a full reader (never a client, never a malformed
  id).
- `apps/web/src/app-core/realtime.test.ts`: a drawer adds its topic beside the page's, leaving
  removes only its own, the last one leaving stops the stream, and the same union reopens nothing.
- `apps/web/src/screens/TAX-08/live.test.tsx`:
  - a `session:` invalidate refetches only that session's snapshot;
  - a waiting change opens SHL-10 in place and decides nothing by itself;
  - a decided change names who decided and offers nothing to press.

- Found by the run: `test_t04t37_tax_assistant`'s agents-off test counted every
  `workbench_sessions` row and failed after `test_p10t43_sessions` (6 rows). It now compares the
  count before and after, as it already did for usage.
- `tests/unit/notifications/test_catalogue.py`'s pinned invalidation set gains
  `session.items_changed`, and it now passes whichever module imports first.
- Verified:
  - backend unit, security and contract suites (23,853 passed; the failures were the known
    WeasyPrint and run-alone ones);
  - the session and assistant integration tests, run together;
  - vitest 3,783 passed;
  - pyright, banned patterns, docs and the import contracts. The OpenAPI file is unchanged.

## Partial
- "Request consent…" (SPEC-649 AC-6.8). The §7216 consent templates wait on counsel's approved
  text (F-09-T119, deferred), and CLI-05's own "Request consent…" is still disabled. No surface
  drafts the C7 envelope yet.
- The drawer's change list opens SHL-10 rather than drawing TAX-08's full inline ApprovalCard
  (the diff table, reasoning, source row). The handoff routes "Approve adjustments" to SHL-10's
  confirmation, and drawing the card inline would duplicate SHL-10's decision logic.
- Copy not in the handoff: "Open plan", "Back to the thread", "No threads on this return yet."
  (TAX-08 has no plan or history artboard), and "Rejected by …". These need a design pass.

## Progress log
- `2026-11-12` — Built (S37 follow-ups, round 2).
